[CmdletBinding()]
param(
    [string]$OutputRoot = 'logs/device',
    [ValidateRange(5, 60)]
    [int]$TimeoutSeconds = 15,
    [string[]]$Variables = @(
        'product',
        'secure',
        'is-userspace',
        'slot-count',
        'current-slot',
        'has-slot:boot',
        'has-slot:vendor_boot',
        'has-slot:vbmeta',
        'has-slot:super'
    )
)

# M6a Fastboot read-only whitelist collector.
# It never sends any state-changing Fastboot command.
$ErrorActionPreference = 'Stop'
$allowedVariables = @(
    'product',
    'secure',
    'is-userspace',
    'slot-count',
    'current-slot',
    'has-slot:boot',
    'has-slot:vendor_boot',
    'has-slot:vbmeta',
    'has-slot:super'
)

foreach ($variable in $Variables) {
    if ($variable -notin $allowedVariables) {
        throw "Refusing non-whitelisted Fastboot variable: $variable"
    }
}
if ($Variables.Count -eq 0) {
    throw 'At least one whitelisted variable is required.'
}

$fastbootCandidate = Join-Path $PSScriptRoot '..\tools\platform-tools\fastboot.exe'
if (-not (Test-Path -LiteralPath $fastbootCandidate -PathType Leaf)) {
    throw "fastboot.exe not found: $fastbootCandidate"
}
$fastbootPath = (Resolve-Path -LiteralPath $fastbootCandidate).Path
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputDir = Join-Path $OutputRoot $runId
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

function Invoke-FastbootReadOnly {
    param(
        [Parameter(Mandatory = $true)] [string[]]$Arguments,
        [Parameter(Mandatory = $true)] [string]$Name
    )

    $stdoutPath = Join-Path $outputDir "$Name.stdout.txt"
    $stderrPath = Join-Path $outputDir "$Name.stderr.txt"
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $fastbootPath
    # Arguments are created only from the fixed devices/getvar whitelist above.
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
    FastbootPath = $fastbootPath
    TimeoutSeconds = $TimeoutSeconds
    RequestedVariables = $Variables
    DeviceEnumeration = $null
    Queries = @()
}

$devices = Invoke-FastbootReadOnly -Arguments @('devices') -Name 'fastboot-devices'
$record.DeviceEnumeration = $devices
$deviceOutput = (Get-Content -Raw -LiteralPath $devices.Stdout).Trim()
if (-not $devices.CompletedWithinTimeout -or [string]::IsNullOrWhiteSpace($deviceOutput) -or
    $deviceOutput -notmatch '(?m)^\S+\s+fastboot\s*$') {
    $recordPath = Join-Path $outputDir 'fastboot-readonly-vars.json'
    $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $recordPath -Encoding UTF8
    throw "Fastboot device enumeration did not produce a serial and fastboot state. Evidence retained at: $outputDir"
}

foreach ($variable in $Variables) {
    $safeName = $variable -replace '[^A-Za-z0-9._-]', '_'
    $record.Queries += Invoke-FastbootReadOnly -Arguments @('getvar', $variable) -Name "fastboot-getvar-$safeName"
}

$recordPath = Join-Path $outputDir 'fastboot-readonly-vars.json'
$record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $recordPath -Encoding UTF8
$hashLines = Get-ChildItem -LiteralPath $outputDir -File |
    Where-Object { $_.Name -ne 'SHA256SUMS.txt' } |
    ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        "{0}  {1}" -f $hash.Hash, $hash.Path
    }
$hashLines | Set-Content -LiteralPath (Join-Path $outputDir 'SHA256SUMS.txt') -Encoding UTF8

Write-Output "Read-only Fastboot variables written to: $outputDir"
