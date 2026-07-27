[CmdletBinding()]
param(
    [string]$OutputRoot
)

# H2c read-only compatibility preflight.
# Safety contract:
# - does not enable or disable Windows optional features;
# - does not call wsl --install, wsl --update, or an online catalog;
# - does not install, remove, start, or stop software/services;
# - does not download packages or restart Windows;
# - does not read or export BitLocker recovery passwords;
# - does not access UBOX10 or firmware images;
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

function Get-OptionalFeatureRecord {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FeatureName
    )

    try {
        $features = @(Get-WindowsOptionalFeature -Online -FeatureName $FeatureName -ErrorAction Stop)
        if ($features.Count -eq 0) {
            return [ordered]@{
                FeatureName = $FeatureName
                Availability = 'NotPresent'
                State = 'NotPresent'
                RestartRequired = $null
                Error = $null
            }
        }
        if ($features.Count -ne 1) {
            throw "Expected one optional-feature record for $FeatureName, received $($features.Count)."
        }
        $feature = $features[0]
        return [ordered]@{
            FeatureName = $feature.FeatureName
            Availability = 'Present'
            State = $feature.State.ToString()
            RestartRequired = $feature.RestartRequired
            Error = $null
        }
    }
    catch {
        return [ordered]@{
            FeatureName = $FeatureName
            Availability = 'Unknown'
            State = $null
            RestartRequired = $null
            Error = Get-ErrorRecord -Record $_
        }
    }
}

function Get-RegistryValueRecord {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    try {
        if (-not (Test-Path -LiteralPath $Path)) {
            return [ordered]@{
                Path = $Path
                Name = $Name
                Present = $false
                Value = $null
                Error = $null
            }
        }

        $item = Get-ItemProperty -LiteralPath $Path -Name $Name -ErrorAction Stop
        return [ordered]@{
            Path = $Path
            Name = $Name
            Present = $true
            Value = $item.$Name
            Error = $null
        }
    }
    catch [System.Management.Automation.PSArgumentException] {
        return [ordered]@{
            Path = $Path
            Name = $Name
            Present = $false
            Value = $null
            Error = $null
        }
    }
    catch {
        return [ordered]@{
            Path = $Path
            Name = $Name
            Present = $null
            Value = $null
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
    DisplayVersion = $currentVersion.DisplayVersion
    CurrentBuild = $currentVersion.CurrentBuild
    UBR = $currentVersion.UBR
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

$deviceGuard = [ordered]@{
    Records = @()
    Error = $null
}
try {
    $deviceGuard.Records = @(
        Get-CimInstance -Namespace 'root\Microsoft\Windows\DeviceGuard' `
            -ClassName Win32_DeviceGuard -ErrorAction Stop |
            Select-Object VirtualizationBasedSecurityStatus,
                SecurityServicesConfigured, SecurityServicesRunning,
                RequiredSecurityProperties, AvailableSecurityProperties,
                CodeIntegrityPolicyEnforcementStatus,
                UsermodeCodeIntegrityPolicyEnforcementStatus
    )
}
catch {
    $deviceGuard.Error = Get-ErrorRecord -Record $_
}

$systemDriveEncryption = [ordered]@{
    MountPoint = $env:SystemDrive
    Record = $null
    Error = $null
    RecoveryKeyMaterialRead = $false
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
        KeyProtectorTypes = $protectorTypes
    }
}
catch {
    $systemDriveEncryption.Error = Get-ErrorRecord -Record $_
}

$featureNames = @(
    'Microsoft-Windows-Subsystem-Linux',
    'VirtualMachinePlatform',
    'Microsoft-Hyper-V-All',
    'HypervisorPlatform',
    'Containers',
    'Containers-DisposableClientVM',
    'Microsoft-Windows-Sandbox'
)
$optionalFeatures = @(
    foreach ($featureName in $featureNames) {
        Get-OptionalFeatureRecord -FeatureName $featureName
    }
)

$softwareNamePattern = '(?i)(VMware|VirtualBox|Docker Desktop|BlueStacks|NoxPlayer|Nox App Player|LDPlayer|MuMu|MEmu|Genymotion|QEMU|Intel.*HAXM|Windows Subsystem for Android|Android Emulator)'
$uninstallRoots = @(
    [ordered]@{
        Scope = 'HKLM-64'
        Path = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    },
    [ordered]@{
        Scope = 'HKLM-32'
        Path = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    },
    [ordered]@{
        Scope = 'HKCU'
        Path = 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    }
)
$installedSoftware = @(
    @(
        foreach ($root in $uninstallRoots) {
            Get-ItemProperty -Path $root.Path -ErrorAction SilentlyContinue |
                Where-Object {
                    -not [string]::IsNullOrWhiteSpace($_.DisplayName) -and
                    $_.DisplayName -match $softwareNamePattern
                } |
                ForEach-Object {
                    [ordered]@{
                        Scope = $root.Scope
                        DisplayName = $_.DisplayName
                        DisplayVersion = $_.DisplayVersion
                        Publisher = $_.Publisher
                    }
                }
        }
    ) | Sort-Object DisplayName, DisplayVersion, Scope
)

$serviceNamePattern = '(?i)(vmware|vbox|virtualbox|docker|com\.docker|bluestacks|nox|ldplayer|mumu|memu|genymotion|qemu|haxm|vmcompute|vmms|hvhost|hns|lxss|wsl)'
$services = [ordered]@{
    Records = @()
    Error = $null
}
try {
    $services.Records = @(
        Get-Service -ErrorAction Stop |
            Where-Object {
                $_.Name -match $serviceNamePattern -or
                $_.DisplayName -match $serviceNamePattern
            } |
            Sort-Object Name |
            ForEach-Object {
                [ordered]@{
                    Name = $_.Name
                    DisplayName = $_.DisplayName
                    Status = $_.Status.ToString()
                    StartType = $_.StartType.ToString()
                }
            }
    )
}
catch {
    $services.Error = Get-ErrorRecord -Record $_
}

$deviceGuardRegistry = @(
    Get-RegistryValueRecord `
        -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard' `
        -Name 'EnableVirtualizationBasedSecurity'
    Get-RegistryValueRecord `
        -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard' `
        -Name 'RequirePlatformSecurityFeatures'
    Get-RegistryValueRecord `
        -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity' `
        -Name 'Enabled'
)

$componentServicingPending = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$windowsUpdatePending = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
$pendingFileRenameRecord = Get-RegistryValueRecord `
    -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' `
    -Name 'PendingFileRenameOperations'
$pendingFileRename = $pendingFileRenameRecord.Present -eq $true
$pendingReboot = [ordered]@{
    ComponentBasedServicing = $componentServicingPending
    WindowsUpdate = $windowsUpdatePending
    PendingFileRenameOperations = $pendingFileRename
    PendingFileRenameQuery = $pendingFileRenameRecord
    AnySignalPresent = [bool](
        $componentServicingPending -or
        $windowsUpdatePending -or
        $pendingFileRename
    )
}

$report = [ordered]@{
    SchemaVersion = 1
    ReportType = 'wsl-h2c-compatibility-preflight'
    CollectedAt = (Get-Date).ToString('o')
    Safety = [ordered]@{
        ReadOnlyInspection = $true
        NetworkQueried = $false
        WindowsFeaturesChanged = $false
        WslInstallOrUpdateCalled = $false
        DistributionCatalogQueried = $false
        SoftwareInstalledOrRemoved = $false
        ServiceStateChanged = $false
        RegistryWritten = $false
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
        PowerShellVersion = $PSVersionTable.PSVersion.ToString()
        Registry = $osRegistry
        Processor = $processor
        ComputerSystem = $computerSystem
        DeviceGuard = $deviceGuard
        DeviceGuardRegistry = $deviceGuardRegistry
        SystemDriveEncryption = $systemDriveEncryption
        PendingReboot = $pendingReboot
    }
    OptionalFeatures = $optionalFeatures
    CompatibilityInventory = [ordered]@{
        NameMatchPattern = $softwareNamePattern
        InstalledSoftware = $installedSoftware
        Services = $services
    }
    InterpretationRules = @(
        'A query error means unknown, not absent, disabled, or compatible.',
        'A software name match is an inventory hit, not proof of incompatibility.',
        'No name match does not prove that no hypervisor-dependent software exists.',
        'Pending reboot signals must be resolved before an H2c Apply experiment.',
        'This report does not authorize Windows feature changes, installation, download, restart, or fixture generation.'
    )
}

$reportPath = Join-Path $outputDir 'wsl-h2c-compatibility-preflight.json'
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding UTF8

$hashLines = Get-ChildItem -LiteralPath $outputDir -File |
    Where-Object { $_.Name -ne 'SHA256SUMS.txt' } |
    Sort-Object Name |
    ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        "{0}  {1}" -f $hash.Hash, $_.Name
    }
$hashLines | Set-Content -LiteralPath (Join-Path $outputDir 'SHA256SUMS.txt') -Encoding UTF8

Write-Output "Read-only H2c compatibility evidence written to: $outputDir"
Write-Output "Administrator: $isAdministrator"
if (-not $isAdministrator) {
    Write-Warning 'Optional-feature, CIM, and BitLocker fields may remain unknown. Re-run this same read-only script from an elevated PowerShell after reviewing the non-admin result.'
}
