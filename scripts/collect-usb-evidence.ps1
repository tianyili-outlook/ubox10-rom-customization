[CmdletBinding()]
param(
    [string]$OutputRoot = 'logs/device',
    [switch]$ProbeFastboot,
    [ValidateRange(5, 60)]
    [int]$TimeoutSeconds = 15
)

# M6a read-only host evidence collector.
# It does not install drivers and, unless -ProbeFastboot is supplied, does not
# invoke any command against the connected device.
$ErrorActionPreference = 'Stop'
$targetPrefix = 'USB\VID_1F3A&PID_1010'
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputDir = Join-Path $OutputRoot $runId
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [object]$Content
    )

    $Content | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Invoke-FastbootProbe {
    param(
        [Parameter(Mandatory = $true)] [string]$FastbootPath,
        [Parameter(Mandatory = $true)] [string[]]$Arguments,
        [Parameter(Mandatory = $true)] [string]$Name
    )

    $stdoutPath = Join-Path $outputDir "$Name.stdout.txt"
    $stderrPath = Join-Path $outputDir "$Name.stderr.txt"
    # Do not use Start-Process redirection here. Some Windows environments
    # expose both PATH and Path in the inherited process environment, which
    # makes Start-Process fail before fastboot is launched.
    # Arguments are fixed literals selected by this script (devices/getvar).
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FastbootPath
    $startInfo.Arguments = ($Arguments -join ' ')
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    [void]$process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $completed = $process.WaitForExit($TimeoutSeconds * 1000)
    if (-not $completed) {
        $process.Kill()
        $process.WaitForExit()
    }
    $stdoutTask.GetAwaiter().GetResult() | Set-Content -LiteralPath $stdoutPath -Encoding UTF8
    $stderrTask.GetAwaiter().GetResult() | Set-Content -LiteralPath $stderrPath -Encoding UTF8

    return [pscustomobject]@{
        Name = $Name
        Arguments = $Arguments
        CompletedWithinTimeout = $completed
        ExitCode = if ($completed) { $process.ExitCode } else { $null }
        Stdout = $stdoutPath
        Stderr = $stderrPath
    }
}

$record = [ordered]@{
    SchemaVersion = 1
    CollectedAt = (Get-Date).ToString('o')
    TargetPrefix = $targetPrefix
    ComputerName = $env:COMPUTERNAME
    PnpCollectionError = $null
    Devices = @()
    Fastboot = [ordered]@{
        Path = $null
        VersionOutput = $null
        ProbeRequested = [bool]$ProbeFastboot
        Probes = @()
    }
}

try {
    $devices = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "$targetPrefix*" })
    foreach ($device in $devices) {
        $properties = @()
        $propertyError = $null
        try {
            $properties = @(Get-PnpDeviceProperty -InstanceId $device.InstanceId | ForEach-Object {
                [pscustomobject]@{
                    KeyName = $_.KeyName
                    Type = $_.Type
                    Data = $_.Data
                }
            })
        }
        catch {
            $propertyError = $_.Exception.Message
        }

        $record.Devices += [pscustomobject]@{
            Status = $device.Status
            Class = $device.Class
            FriendlyName = $device.FriendlyName
            InstanceId = $device.InstanceId
            Problem = $device.Problem
            PropertyCollectionError = $propertyError
            Properties = $properties
        }
    }
}
catch {
    $record.PnpCollectionError = $_.Exception.Message
}

$fastbootCandidate = Join-Path $PSScriptRoot '..\tools\platform-tools\fastboot.exe'
if (Test-Path -LiteralPath $fastbootCandidate -PathType Leaf) {
    $fastbootPath = (Resolve-Path -LiteralPath $fastbootCandidate).Path
    $record.Fastboot.Path = $fastbootPath
    $versionPath = Join-Path $outputDir 'fastboot.version.txt'
    try {
        & $fastbootPath --version 2>&1 | Set-Content -LiteralPath $versionPath -Encoding UTF8
        $record.Fastboot.VersionOutput = $versionPath
    }
    catch {
        $record.Fastboot.VersionOutput = "ERROR: $($_.Exception.Message)"
    }

    if ($ProbeFastboot) {
        $devicesProbe = Invoke-FastbootProbe -FastbootPath $fastbootPath -Arguments @('devices') -Name 'fastboot-devices'
        $record.Fastboot.Probes += $devicesProbe

        # Only query a device variable after fastboot devices produced a serial line.
        $devicesOutput = if (Test-Path -LiteralPath $devicesProbe.Stdout) {
            (Get-Content -Raw -LiteralPath $devicesProbe.Stdout).Trim()
        } else {
            ''
        }
        if ($devicesProbe.CompletedWithinTimeout -and -not [string]::IsNullOrWhiteSpace($devicesOutput)) {
            $record.Fastboot.Probes += Invoke-FastbootProbe -FastbootPath $fastbootPath -Arguments @('getvar', 'version') -Name 'fastboot-getvar-version'
        }
    }
}
else {
    $record.Fastboot.VersionOutput = "NOT FOUND: $fastbootCandidate"
}

$jsonPath = Join-Path $outputDir 'usb-evidence.json'
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$hashLines = Get-ChildItem -LiteralPath $outputDir -File |
    ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        "{0}  {1}" -f $hash.Hash, $hash.Path
    }
Write-Utf8File -Path (Join-Path $outputDir 'SHA256SUMS.txt') -Content $hashLines

Write-Output "Read-only evidence written to: $outputDir"
if ($record.PnpCollectionError) {
    Write-Warning "PnP collection did not complete: $($record.PnpCollectionError)"
}
if ($record.Devices.Count -eq 0) {
    Write-Warning "No present device matched $targetPrefix. Preserve this result together with Device Manager screenshots."
}
