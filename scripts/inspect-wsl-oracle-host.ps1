[CmdletBinding()]
param(
    [string]$OutputRoot
)

# M6b.2-d read-only Windows/WSL host preflight.
# Safety contract:
# - does not call wsl --install or wsl --update;
# - does not enable/disable Windows optional features;
# - does not download packages or query the online distribution catalog;
# - does not restart Windows;
# - does not read or export BitLocker recovery passwords;
# - writes evidence only below logs/host (or the explicitly selected output root).
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repositoryRoot 'logs\host'
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $repositoryRoot $OutputRoot
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputDir = Join-Path $OutputRoot $runId
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

function Get-ErrorRecord {
    param(
        [Parameter(Mandatory = $true)]
        [System.Management.Automation.ErrorRecord]$Record
    )

    return [ordered]@{
        Type = $Record.Exception.GetType().FullName
        Message = $Record.Exception.Message
        FullyQualifiedErrorId = $Record.FullyQualifiedErrorId
    }
}

function Invoke-ReadOnlyProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [ValidateRange(1, 30)]
        [int]$TimeoutSeconds = 10
    )

    $stdoutPath = Join-Path $outputDir "$Name.stdout.txt"
    $stderrPath = Join-Path $outputDir "$Name.stderr.txt"
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = ($Arguments -join ' ')
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    # wsl.exe emits redirected console text as UTF-16LE on this host.
    # Declare the encoding before Start() so Chinese diagnostics remain intact.
    $startInfo.StandardOutputEncoding = [System.Text.Encoding]::Unicode
    $startInfo.StandardErrorEncoding = [System.Text.Encoding]::Unicode

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $started = $false
    try {
        $started = $process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $completed = $process.WaitForExit($TimeoutSeconds * 1000)
        if (-not $completed) {
            $process.Kill()
            $process.WaitForExit()
        }

        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $stdout | Set-Content -LiteralPath $stdoutPath -Encoding UTF8
        $stderr | Set-Content -LiteralPath $stderrPath -Encoding UTF8

        return [ordered]@{
            Name = $Name
            FilePath = $FilePath
            Arguments = $Arguments
            Started = $started
            CompletedWithinTimeout = $completed
            ExitCode = if ($completed) { $process.ExitCode } else { $null }
            StdoutFile = $stdoutPath
            StderrFile = $stderrPath
            Error = $null
        }
    }
    catch {
        return [ordered]@{
            Name = $Name
            FilePath = $FilePath
            Arguments = $Arguments
            Started = $started
            CompletedWithinTimeout = $false
            ExitCode = $null
            StdoutFile = $null
            StderrFile = $null
            Error = Get-ErrorRecord -Record $_
        }
    }
    finally {
        $process.Dispose()
    }
}

function Get-OptionalFeatureRecord {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FeatureName
    )

    try {
        $feature = Get-WindowsOptionalFeature -Online -FeatureName $FeatureName -ErrorAction Stop
        return [ordered]@{
            FeatureName = $feature.FeatureName
            State = $feature.State.ToString()
            RestartRequired = $feature.RestartRequired
            Error = $null
        }
    }
    catch {
        return [ordered]@{
            FeatureName = $FeatureName
            State = $null
            RestartRequired = $null
            Error = Get-ErrorRecord -Record $_
        }
    }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$currentVersion = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$osRegistry = [ordered]@{
    ProductName = $currentVersion.ProductName
    EditionID = $currentVersion.EditionID
    CompositionEditionID = $currentVersion.CompositionEditionID
    DisplayVersion = $currentVersion.DisplayVersion
    ReleaseId = $currentVersion.ReleaseId
    CurrentBuild = $currentVersion.CurrentBuild
    CurrentBuildNumber = $currentVersion.CurrentBuildNumber
    UBR = $currentVersion.UBR
    BuildLabEx = $currentVersion.BuildLabEx
    InstallationType = $currentVersion.InstallationType
}

$firmwareRegistrySource = 'HKLM:\HARDWARE\DESCRIPTION\System\BIOS'
$firmwareRegistryValue = Get-ItemProperty -LiteralPath $firmwareRegistrySource
$firmwareRegistry = [ordered]@{
    RegistryPath = $firmwareRegistrySource
    BaseBoardManufacturer = $firmwareRegistryValue.BaseBoardManufacturer
    BaseBoardProduct = $firmwareRegistryValue.BaseBoardProduct
    BaseBoardVersion = $firmwareRegistryValue.BaseBoardVersion
    BIOSVendor = $firmwareRegistryValue.BIOSVendor
    BIOSVersion = $firmwareRegistryValue.BIOSVersion
    BIOSReleaseDate = $firmwareRegistryValue.BIOSReleaseDate
    SystemManufacturer = $firmwareRegistryValue.SystemManufacturer
    SystemProductName = $firmwareRegistryValue.SystemProductName
    SystemVersion = $firmwareRegistryValue.SystemVersion
}

$processor = [ordered]@{
    Records = @()
    Error = $null
}
try {
    $processor.Records = @(
        Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop |
            Select-Object Name, Manufacturer, Architecture,
                VirtualizationFirmwareEnabled, VMMonitorModeExtensions,
                SecondLevelAddressTranslationExtensions
    )
}
catch {
    $processor.Error = Get-ErrorRecord -Record $_
}

$computerSystem = [ordered]@{
    Record = $null
    Error = $null
}
try {
    $computerSystem.Record = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop |
        Select-Object Manufacturer, Model, SystemType, HypervisorPresent
}
catch {
    $computerSystem.Error = Get-ErrorRecord -Record $_
}

$systemDriveEncryption = [ordered]@{
    MountPoint = $env:SystemDrive
    Record = $null
    Error = $null
    RecoveryKeyMaterialRead = $false
    RecoveryKeyAvailabilityVerified = $false
}
try {
    $bitLockerVolume = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
    $protectorTypes = @(
        $bitLockerVolume.KeyProtector |
            ForEach-Object { $_.KeyProtectorType.ToString() } |
            Sort-Object -Unique
    )
    $systemDriveEncryption.Record = [ordered]@{
        VolumeType = $bitLockerVolume.VolumeType.ToString()
        VolumeStatus = $bitLockerVolume.VolumeStatus.ToString()
        ProtectionStatus = $bitLockerVolume.ProtectionStatus.ToString()
        EncryptionMethod = $bitLockerVolume.EncryptionMethod.ToString()
        EncryptionPercentage = $bitLockerVolume.EncryptionPercentage
        LockStatus = $bitLockerVolume.LockStatus.ToString()
        AutoUnlockEnabled = $bitLockerVolume.AutoUnlockEnabled
        KeyProtectorTypes = $protectorTypes
    }
}
catch {
    $systemDriveEncryption.Error = Get-ErrorRecord -Record $_
}

$wslCommand = Get-Command wsl.exe -ErrorAction SilentlyContinue
$wslProbes = @()
if ($null -ne $wslCommand) {
    $wslPath = $wslCommand.Source
    $wslProbes += Invoke-ReadOnlyProcess -FilePath $wslPath -Arguments @('--version') -Name 'wsl-version'
    $wslProbes += Invoke-ReadOnlyProcess -FilePath $wslPath -Arguments @('--status') -Name 'wsl-status'
    $wslProbes += Invoke-ReadOnlyProcess -FilePath $wslPath -Arguments @('--list', '--verbose') -Name 'wsl-list-verbose'
}
else {
    $wslPath = $null
}

$report = [ordered]@{
    SchemaVersion = 2
    CollectedAt = (Get-Date).ToString('o')
    Safety = [ordered]@{
        ReadOnlyInspection = $true
        NetworkCatalogQueried = $false
        WindowsFeaturesChanged = $false
        WslInstallOrUpdateCalled = $false
        RestartCalled = $false
        DeviceAccessed = $false
        FirmwareImageAccessed = $false
        BitLockerRecoveryKeyMaterialRead = $false
    }
    Host = [ordered]@{
        ComputerName = $env:COMPUTERNAME
        UserName = $identity.Name
        IsAdministrator = $isAdministrator
        Is64BitOperatingSystem = [Environment]::Is64BitOperatingSystem
        Is64BitProcess = [Environment]::Is64BitProcess
        ProcessArchitecture = [Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString()
        OSArchitecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
        PowerShell = [ordered]@{
            Version = $PSVersionTable.PSVersion.ToString()
            PSEdition = $PSVersionTable.PSEdition
            CLRVersion = $PSVersionTable.CLRVersion.ToString()
        }
        Registry = $osRegistry
        FirmwareRegistry = $firmwareRegistry
        Processor = $processor
        ComputerSystem = $computerSystem
        SystemDriveEncryption = $systemDriveEncryption
    }
    OptionalFeatures = @(
        Get-OptionalFeatureRecord -FeatureName 'Microsoft-Windows-Subsystem-Linux'
        Get-OptionalFeatureRecord -FeatureName 'VirtualMachinePlatform'
    )
    Wsl = [ordered]@{
        CommandPath = $wslPath
        Probes = $wslProbes
        OnlineDistributionListQueried = $false
    }
    InterpretationRules = @(
        'A failed optional-feature or CIM query means unknown, not disabled or unsupported.',
        'Registry ProductName is recorded verbatim and must not override build/display-version evidence.',
        'Presence of wsl.exe does not prove that WSL features or a Linux distribution are installed.',
        'BitLocker protector types are not recovery passwords; recovery-key availability requires separate user confirmation.',
        'This report does not authorize installation, download, update, restart, or fixture generation.'
    )
}

$reportPath = Join-Path $outputDir 'wsl-oracle-host-preflight.json'
$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding UTF8

$hashLines = Get-ChildItem -LiteralPath $outputDir -File |
    Where-Object { $_.Name -ne 'SHA256SUMS.txt' } |
    ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        # Keep the evidence bundle relocatable. The manifest is stored beside
        # these files, so a basename is sufficient and survives directory moves.
        "{0}  {1}" -f $hash.Hash, $_.Name
    }
$hashLines | Set-Content -LiteralPath (Join-Path $outputDir 'SHA256SUMS.txt') -Encoding UTF8

Write-Output "Read-only WSL oracle host evidence written to: $outputDir"
Write-Output "Administrator: $isAdministrator"
if (-not $isAdministrator) {
    Write-Warning 'Optional-feature and virtualization fields may remain unknown. Re-run this same read-only script from an elevated PowerShell only after reviewing it.'
}
