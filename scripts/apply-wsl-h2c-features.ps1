[CmdletBinding()]
param(
    [ValidateSet('Inspect', 'Apply')]
    [string]$Mode = 'Inspect',

    [string]$PreflightEvidenceDir,

    [switch]$ConfirmH2cWindowsFeatures,

    [string]$OutputRoot
)

# H2c Windows-feature gate.
# Inspect mode is read-only. Apply mode is deliberately narrow:
# - requires administrator rights, an explicit confirmation switch, and a
#   validated H2c administrator preflight bundle;
# - enables only Microsoft-Windows-Subsystem-Linux and VirtualMachinePlatform;
# - uses -NoRestart and never installs a distribution, downloads content,
#   queries the online distribution catalog, or accesses UBOX10/firmware.
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

$targetFeatures = @(
    'Microsoft-Windows-Subsystem-Linux',
    'VirtualMachinePlatform'
)

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

function Get-PendingRebootRecord {
    $componentServicing = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
    $windowsUpdate = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
    $pendingFileRename = $false
    $pendingFileRenameError = $null
    try {
        $sessionManager = Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name 'PendingFileRenameOperations' -ErrorAction SilentlyContinue
        $pendingFileRename = $null -ne $sessionManager -and $null -ne $sessionManager.PendingFileRenameOperations
    }
    catch {
        $pendingFileRenameError = Get-ErrorRecord -Record $_
    }

    return [ordered]@{
        ComponentBasedServicing = $componentServicing
        WindowsUpdate = $windowsUpdate
        PendingFileRenameOperations = $pendingFileRename
        PendingFileRenameError = $pendingFileRenameError
        AnySignalPresent = [bool]($componentServicing -or $windowsUpdate -or $pendingFileRename)
    }
}

function Test-H2cPreflightEvidence {
    param(
        [string]$EvidenceDirectory
    )

    $result = [ordered]@{
        Provided = -not [string]::IsNullOrWhiteSpace($EvidenceDirectory)
        Directory = $null
        Valid = $false
        ReportSha256 = $null
        Checks = @()
        Error = $null
    }
    if (-not $result.Provided) {
        $result.Error = [ordered]@{
            Type = 'PreflightEvidenceMissing'
            Message = 'Apply mode requires -PreflightEvidenceDir.'
            FullyQualifiedErrorId = 'H2cPreflightEvidenceMissing'
        }
        return $result
    }

    try {
        $resolved = (Resolve-Path -LiteralPath $EvidenceDirectory -ErrorAction Stop).Path
        $result.Directory = $resolved
        $sumPath = Join-Path $resolved 'SHA256SUMS.txt'
        $reportPath = Join-Path $resolved 'wsl-h2c-compatibility-preflight.json'
        if (-not (Test-Path -LiteralPath $sumPath) -or -not (Test-Path -LiteralPath $reportPath)) {
            throw 'Preflight bundle lacks SHA256SUMS.txt or wsl-h2c-compatibility-preflight.json.'
        }

        $sumLines = Get-Content -LiteralPath $sumPath -Encoding UTF8
        foreach ($line in $sumLines) {
            if ($line -notmatch '^([0-9A-Fa-f]{64})  ([^\\/:]+)$') {
                throw "Preflight SHA256SUMS line is not basename-relative: $line"
            }
            $targetPath = Join-Path $resolved $Matches[2]
            if (-not (Test-Path -LiteralPath $targetPath)) {
                throw "Preflight payload is missing: $targetPath"
            }
            $actual = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash
            if ($actual -ne $Matches[1].ToUpperInvariant()) {
                throw "Preflight payload hash mismatch: $targetPath"
            }
        }

        $report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $result.ReportSha256 = (Get-FileHash -LiteralPath $reportPath -Algorithm SHA256).Hash
        $features = @{}
        foreach ($feature in $report.OptionalFeatures) {
            $features[$feature.FeatureName] = $feature
        }
        $cpu = @($report.Host.Processor.Records)[0]
        $checkMap = [ordered]@{
            Schema = ($report.SchemaVersion -eq 1 -and $report.ReportType -eq 'wsl-h2c-compatibility-preflight')
            Administrator = [bool]$report.Host.IsAdministrator
            ReadOnly = [bool]$report.Safety.ReadOnlyInspection
            FirmwareVirtualization = ($cpu.VirtualizationFirmwareEnabled -eq $true)
            WslDisabled = ($features['Microsoft-Windows-Subsystem-Linux'].Availability -eq 'Present' -and $features['Microsoft-Windows-Subsystem-Linux'].State -eq 'Disabled' -and $null -eq $features['Microsoft-Windows-Subsystem-Linux'].Error)
            VmpDisabled = ($features['VirtualMachinePlatform'].Availability -eq 'Present' -and $features['VirtualMachinePlatform'].State -eq 'Disabled' -and $null -eq $features['VirtualMachinePlatform'].Error)
            NoPendingReboot = (-not $report.Host.PendingReboot.AnySignalPresent)
            NoSoftwareMatch = (@($report.CompatibilityInventory.InstalledSoftware).Count -eq 0)
            SystemDriveProtectionOff = ($report.Host.SystemDriveEncryption.Record.ProtectionStatus -eq 'Off' -and -not $report.Host.SystemDriveEncryption.RecoveryKeyMaterialRead)
        }
        $safetyNames = @('NetworkQueried','WindowsFeaturesChanged','WslInstallOrUpdateCalled','DistributionCatalogQueried','SoftwareInstalledOrRemoved','ServiceStateChanged','RegistryWritten','RestartCalled','DeviceAccessed','FirmwareImageAccessed','BitLockerRecoveryKeyMaterialRead')
        $checkMap['NoPriorMutationFlags'] = -not [bool](@($safetyNames | Where-Object { $report.Safety.$_ }).Count)
        $result.Checks = @(
            foreach ($name in $checkMap.Keys) {
                [ordered]@{ Name = $name; Passed = [bool]$checkMap[$name] }
            }
        )
        $result.Valid = -not [bool](@($result.Checks | Where-Object { -not $_.Passed }).Count)
    }
    catch {
        $result.Error = Get-ErrorRecord -Record $_
    }
    return $result
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$preflightValidation = Test-H2cPreflightEvidence -EvidenceDirectory $PreflightEvidenceDir
$liveBefore = @(
    foreach ($featureName in $targetFeatures) {
        Get-OptionalFeatureRecord -FeatureName $featureName
    }
)
$livePendingReboot = Get-PendingRebootRecord

$apply = [ordered]@{
    Requested = ($Mode -eq 'Apply')
    ConfirmationSwitchPresent = [bool]$ConfirmH2cWindowsFeatures
    InvocationStarted = $false
    InvocationCompleted = $false
    Output = @()
    Error = $null
    RefusalReasons = @()
}

if ($Mode -eq 'Apply') {
    if (-not $ConfirmH2cWindowsFeatures) {
        $apply.RefusalReasons += 'Missing -ConfirmH2cWindowsFeatures.'
    }
    if (-not $isAdministrator) {
        $apply.RefusalReasons += 'Administrator rights are required for Apply mode.'
    }
    if (-not $preflightValidation.Valid) {
        $apply.RefusalReasons += 'The supplied H2c preflight bundle did not pass validation.'
    }
    if ($livePendingReboot.AnySignalPresent) {
        $apply.RefusalReasons += 'A live pending-reboot signal is present.'
    }
    foreach ($feature in $liveBefore) {
        if ($feature.Availability -ne 'Present' -or $feature.State -ne 'Disabled' -or $null -ne $feature.Error) {
            $apply.RefusalReasons += "Live feature state is not Present/Disabled: $($feature.FeatureName)."
        }
    }

    if ($apply.RefusalReasons.Count -eq 0) {
        $apply.InvocationStarted = $true
        try {
            $apply.Output = @(
                Enable-WindowsOptionalFeature -Online -FeatureName $targetFeatures -NoRestart -ErrorAction Stop |
                    Select-Object FeatureName, State, RestartNeeded
            )
            $apply.InvocationCompleted = $true
        }
        catch {
            $apply.Error = Get-ErrorRecord -Record $_
        }
    }
}

$liveAfter = @(
    foreach ($featureName in $targetFeatures) {
        Get-OptionalFeatureRecord -FeatureName $featureName
    }
)
$report = [ordered]@{
    SchemaVersion = 1
    ReportType = 'wsl-h2c-feature-gate'
    CollectedAt = (Get-Date).ToString('o')
    Mode = $Mode
    Safety = [ordered]@{
        InspectOnly = ($Mode -eq 'Inspect')
        WindowsFeaturesChangeRequested = ($Mode -eq 'Apply')
        WindowsFeaturesChangeInvocationStarted = $apply.InvocationStarted
        WindowsFeaturesChangeInvocationCompleted = $apply.InvocationCompleted
        WslInstallOrUpdateCalled = $false
        DistributionCatalogQueried = $false
        NetworkQueried = $false
        SoftwareInstalledOrRemoved = $false
        ServiceStateChanged = $false
        RegistryWritten = $false
        RestartCalled = $false
        DeviceAccessed = $false
        FirmwareImageAccessed = $false
    }
    Host = [ordered]@{
        UserName = $identity.Name
        IsAdministrator = $isAdministrator
    }
    TargetFeatures = $targetFeatures
    PreflightValidation = $preflightValidation
    LiveBefore = [ordered]@{
        OptionalFeatures = $liveBefore
        PendingReboot = $livePendingReboot
    }
    Apply = $apply
    LiveAfter = [ordered]@{
        OptionalFeatures = $liveAfter
        PendingReboot = (Get-PendingRebootRecord)
    }
    InterpretationRules = @(
        'Inspect mode does not change Windows features.',
        'Apply mode may enable only the two TargetFeatures and always uses -NoRestart.',
        'A failed Apply invocation can leave feature state partially changed; inspect LiveAfter and stop for review.',
        'This script never installs a Linux distribution, downloads content, queries an online distribution catalog, or restarts Windows.',
        'A successful feature enable is not H2c completion: Windows must reboot, then the read-only post-reboot validation must pass.'
    )
}

$reportPath = Join-Path $outputDir 'wsl-h2c-feature-gate.json'
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding UTF8

$hashLines = Get-ChildItem -LiteralPath $outputDir -File |
    Where-Object { $_.Name -ne 'SHA256SUMS.txt' } |
    Sort-Object Name |
    ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        "{0}  {1}" -f $hash.Hash, $_.Name
    }
$hashLines | Set-Content -LiteralPath (Join-Path $outputDir 'SHA256SUMS.txt') -Encoding UTF8

Write-Output "H2c feature-gate evidence written to: $outputDir"
Write-Output "Mode: $Mode"
Write-Output "Administrator: $isAdministrator"
Write-Output "Preflight valid: $($preflightValidation.Valid)"
if ($Mode -eq 'Apply' -and -not $apply.InvocationCompleted) {
    Write-Warning 'No completed H2c feature change was recorded. Review the evidence bundle before taking any further action.'
    exit 2
}
