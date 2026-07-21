[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [ValidateSet('Inspect', 'Apply', 'Rollback')]
    [string]$Action = 'Inspect',
    [string]$OutputRoot = 'logs/device',
    [string]$BackupFile,
    [switch]$IUnderstandThisChangesWindowsHostBinding
)

# M6a controlled Windows-host diagnostic. Default action is read-only.
# It never invokes fastboot, installs/uninstalls a driver, or writes to the device.
$ErrorActionPreference = 'Stop'
$targetPrefix = 'USB\VID_1F3A&PID_1010'
$expectedGuid = '{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}'
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputDir = Join-Path $OutputRoot $runId

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [object]$Value
    )

    $Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-SingleTargetDevice {
    $devices = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "$targetPrefix*" })
    if ($devices.Count -ne 1) {
        throw "Expected exactly one present $targetPrefix device; found $($devices.Count). Disconnect duplicates or stop."
    }
    return $devices[0]
}

function Get-DeviceParametersPath {
    param([Parameter(Mandatory = $true)] [string]$InstanceId)

    return "HKLM:\SYSTEM\CurrentControlSet\Enum\$InstanceId\Device Parameters"
}

function Get-CurrentGuids {
    param([Parameter(Mandatory = $true)] [string]$RegistryPath)

    $value = Get-ItemPropertyValue -LiteralPath $RegistryPath -Name 'DeviceInterfaceGUIDs' -ErrorAction Stop
    return @($value | ForEach-Object { [string]$_ })
}

function Test-SequenceEqual {
    param(
        [Parameter(Mandatory = $true)] [string[]]$Left,
        [Parameter(Mandatory = $true)] [string[]]$Right
    )

    if ($Left.Count -ne $Right.Count) { return $false }
    for ($index = 0; $index -lt $Left.Count; $index++) {
        if ($Left[$index] -cne $Right[$index]) { return $false }
    }
    return $true
}

function Write-DirectoryHashes {
    param([Parameter(Mandatory = $true)] [string]$Directory)

    $lines = Get-ChildItem -LiteralPath $Directory -File |
        Where-Object { $_.Name -ne 'SHA256SUMS.txt' } |
        ForEach-Object {
            $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
            "{0}  {1}" -f $hash.Hash, $hash.Path
        }
    $lines | Set-Content -LiteralPath (Join-Path $Directory 'SHA256SUMS.txt') -Encoding UTF8
}

if ($Action -in @('Apply', 'Rollback')) {
    if (-not $IUnderstandThisChangesWindowsHostBinding) {
        throw 'Refusing host change: add -IUnderstandThisChangesWindowsHostBinding after reviewing docs/U1_FASTBOOT_HOST_BINDING_TRIAL.md.'
    }
    if (-not (Test-Administrator)) {
        throw 'Apply/Rollback requires an elevated Administrator PowerShell session.'
    }
}

$device = Get-SingleTargetDevice
$registryPath = Get-DeviceParametersPath -InstanceId $device.InstanceId
if (-not (Test-Path -LiteralPath $registryPath -PathType Container)) {
    throw "Device Parameters registry key was not found: $registryPath"
}
$currentGuids = Get-CurrentGuids -RegistryPath $registryPath

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$inspectRecord = [ordered]@{
    SchemaVersion = 1
    CollectedAt = (Get-Date).ToString('o')
    Action = $Action
    TargetPrefix = $targetPrefix
    ExpectedGuid = $expectedGuid
    Device = [ordered]@{
        InstanceId = $device.InstanceId
        FriendlyName = $device.FriendlyName
        Status = $device.Status
        Problem = $device.Problem
    }
    RegistryPath = $registryPath
    CurrentDeviceInterfaceGUIDs = $currentGuids
    ExpectedGuidPresent = [bool]($currentGuids -contains $expectedGuid)
    Changed = $false
}

if ($Action -eq 'Apply') {
    $backup = [ordered]@{
        SchemaVersion = 1
        BackedUpAt = (Get-Date).ToString('o')
        InstanceId = $device.InstanceId
        RegistryPath = $registryPath
        DeviceInterfaceGUIDs = $currentGuids
        ExpectedGuid = $expectedGuid
    }
    $backupPath = Join-Path $outputDir 'guid-backup.json'
    Write-JsonFile -Path $backupPath -Value $backup

    $newGuids = @($currentGuids)
    if ($newGuids -notcontains $expectedGuid) {
        $newGuids += $expectedGuid
    }

    if ($PSCmdlet.ShouldProcess($registryPath, "Append Android USB interface GUID $expectedGuid")) {
        try {
            Set-ItemProperty -LiteralPath $registryPath -Name 'DeviceInterfaceGUIDs' -Value $newGuids -ErrorAction Stop
            $writtenGuids = Get-CurrentGuids -RegistryPath $registryPath
            foreach ($originalGuid in $currentGuids) {
                if ($writtenGuids -notcontains $originalGuid) {
                    throw "Safety failure: existing GUID disappeared after write: $originalGuid"
                }
            }
            if ($writtenGuids -notcontains $expectedGuid) {
                throw "Safety failure: expected GUID was not present after write: $expectedGuid"
            }
        }
        catch {
            $applyError = $_.Exception.Message
            $automaticRollbackError = $null
            try {
                Set-ItemProperty -LiteralPath $registryPath -Name 'DeviceInterfaceGUIDs' -Value $currentGuids -ErrorAction Stop
                $rollbackGuids = Get-CurrentGuids -RegistryPath $registryPath
                if (-not (Test-SequenceEqual -Left $rollbackGuids -Right $currentGuids)) {
                    throw 'Automatic rollback did not reproduce the original GUID list exactly.'
                }
            }
            catch {
                $automaticRollbackError = $_.Exception.Message
            }
            $inspectRecord.ApplyError = $applyError
            $inspectRecord.AutomaticRollbackAttempted = $true
            $inspectRecord.AutomaticRollbackSucceeded = [string]::IsNullOrWhiteSpace($automaticRollbackError)
            $inspectRecord.AutomaticRollbackError = $automaticRollbackError
            Write-JsonFile -Path (Join-Path $outputDir 'fastboot-interface-guid.json') -Value $inspectRecord
            Write-DirectoryHashes -Directory $outputDir
            if ($automaticRollbackError) {
                throw "Apply failed: $applyError Automatic rollback also failed: $automaticRollbackError Backup retained at: $backupPath"
            }
            throw "Apply failed and the original GUID list was automatically restored: $applyError Backup retained at: $backupPath"
        }
        $inspectRecord.CurrentDeviceInterfaceGUIDs = $writtenGuids
        $inspectRecord.ExpectedGuidPresent = $true
        $inspectRecord.Changed = $true
        $inspectRecord.BackupFile = (Resolve-Path -LiteralPath $backupPath).Path
    }
}
elseif ($Action -eq 'Rollback') {
    if ([string]::IsNullOrWhiteSpace($BackupFile)) {
        throw 'Rollback requires -BackupFile pointing to guid-backup.json from this script.'
    }
    if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) {
        throw "Backup file not found: $BackupFile"
    }

    $backup = Get-Content -Raw -LiteralPath $BackupFile | ConvertFrom-Json
    if ($backup.InstanceId -cne $device.InstanceId) {
        throw "Refusing rollback: backup instance '$($backup.InstanceId)' does not equal current instance '$($device.InstanceId)'."
    }
    if ($backup.RegistryPath -cne $registryPath) {
        throw 'Refusing rollback: backup registry path does not match the current target.'
    }
    $originalGuids = @($backup.DeviceInterfaceGUIDs | ForEach-Object { [string]$_ })
    if ($originalGuids.Count -eq 0) {
        throw 'Refusing rollback: backup has no DeviceInterfaceGUIDs.'
    }

    if ($PSCmdlet.ShouldProcess($registryPath, 'Restore DeviceInterfaceGUIDs from verified backup')) {
        Set-ItemProperty -LiteralPath $registryPath -Name 'DeviceInterfaceGUIDs' -Value $originalGuids -ErrorAction Stop
        $writtenGuids = Get-CurrentGuids -RegistryPath $registryPath
        if (-not (Test-SequenceEqual -Left $writtenGuids -Right $originalGuids)) {
            throw 'Safety failure: restored GUID list did not exactly match the backup.'
        }
        $inspectRecord.CurrentDeviceInterfaceGUIDs = $writtenGuids
        $inspectRecord.ExpectedGuidPresent = [bool]($writtenGuids -contains $expectedGuid)
        $inspectRecord.Changed = $true
        $inspectRecord.BackupFile = (Resolve-Path -LiteralPath $BackupFile).Path
    }
}

$recordPath = Join-Path $outputDir 'fastboot-interface-guid.json'
Write-JsonFile -Path $recordPath -Value $inspectRecord
Write-DirectoryHashes -Directory $outputDir

Write-Output "Action: $Action"
Write-Output "Evidence: $outputDir"
Write-Output "Instance: $($device.InstanceId)"
Write-Output "ExpectedGuidPresent: $($inspectRecord.ExpectedGuidPresent)"
if ($Action -eq 'Apply' -and $inspectRecord.Changed) {
    Write-Output 'GUID appended. Physically unplug and reconnect the device before only running fastboot devices.'
}
if ($Action -eq 'Rollback' -and $inspectRecord.Changed) {
    Write-Output 'Original GUID list restored. Physically unplug and reconnect the device.'
}
