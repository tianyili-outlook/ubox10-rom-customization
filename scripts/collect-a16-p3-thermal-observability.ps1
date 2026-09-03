[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+:7896$')]
    [string]$Endpoint,

    [string]$AdbPath = 'C:\platform-tools\adb.exe',

    [ValidateSet('Discovery', 'Sample')]
    [string]$Mode = 'Discovery',

    [ValidateRange(1, 5)]
    [int]$SampleIntervalSeconds = 2,

    [ValidateRange(5, 120)]
    [int]$DurationSeconds = 60,

    [ValidateRange(5, 120)]
    [int]$CommandTimeoutSeconds = 20,

    [string]$OutputBase,

    [switch]$SelfTest
)

# Host-side observer for a future, explicitly authorized P3 thermal capture.
$ErrorActionPreference = 'Stop'
$CollectorVersion = '1'
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$Results = [System.Collections.Generic.List[object]]::new()

function Write-Utf8NoBom {
    param([string]$Path, [AllowEmptyString()][string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, $Utf8NoBom)
}

function ConvertTo-ArgumentLine {
    param([string[]]$Arguments)
    return (($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_.Replace('\', '\\').Replace('"', '\"')) + '"'
        }
        else { $_ }
    }) -join ' ')
}

function Invoke-External {
    param([string]$Executable, [string[]]$Arguments, [int]$TimeoutSeconds)
    $Info = [System.Diagnostics.ProcessStartInfo]::new()
    $Info.FileName = $Executable
    $Info.Arguments = ConvertTo-ArgumentLine $Arguments
    $Info.UseShellExecute = $false
    $Info.CreateNoWindow = $true
    $Info.RedirectStandardOutput = $true
    $Info.RedirectStandardError = $true
    $Info.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $Info.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $Process = [System.Diagnostics.Process]::new()
    $Process.StartInfo = $Info
    if (-not $Process.Start()) { throw "could not start: $Executable" }
    $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
    $StderrTask = $Process.StandardError.ReadToEndAsync()
    $Completed = $Process.WaitForExit($TimeoutSeconds * 1000)
    $TimedOut = -not $Completed
    if ($TimedOut) {
        try { $Process.Kill() } catch { }
    }
    $Process.WaitForExit()
    $Result = [pscustomobject]@{
        ExitCode = if ($TimedOut) { -1 } else { $Process.ExitCode }
        TimedOut = $TimedOut
        Stdout = $StdoutTask.Result
        Stderr = $StderrTask.Result
    }
    $Process.Dispose()
    return $Result
}

function Get-ResultClass {
    param($Result, [int[]]$ExpectedEmptyExitCodes = @())
    if ($Result.TimedOut) { return 'TIMEOUT' }
    if ($Result.Stderr -match '(?i)permission denied|not permitted') {
        return 'PERMISSION_DENIED'
    }
    if ($Result.Stderr -match '(?i)not found|unknown command|no such file or directory') {
        return 'NOT_AVAILABLE'
    }
    if ($Result.ExitCode -in $ExpectedEmptyExitCodes -and
        [string]::IsNullOrWhiteSpace($Result.Stderr)) {
        return 'EMPTY_SUCCESS'
    }
    if ($Result.ExitCode -ne 0) { return 'COMMAND_FAILED' }
    if ([string]::IsNullOrWhiteSpace("$($Result.Stdout)$($Result.Stderr)")) {
        return 'EMPTY_SUCCESS'
    }
    return 'SUCCESS'
}

function Invoke-CapturedCommand {
    param(
        [string]$Name,
        [string]$Category,
        [string[]]$Arguments,
        [int]$TimeoutSeconds,
        [int[]]$ExpectedEmptyExitCodes = @()
    )
    $Directory = Join-Path $EvidenceRoot $Category
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $Started = Get-Date
    $Result = Invoke-External -Executable $AdbPath -Arguments $Arguments `
        -TimeoutSeconds $TimeoutSeconds
    $Ended = Get-Date
    $StdoutPath = Join-Path $Directory "$Name.stdout.txt"
    $StderrPath = Join-Path $Directory "$Name.stderr.txt"
    Write-Utf8NoBom $StdoutPath $Result.Stdout
    Write-Utf8NoBom $StderrPath $Result.Stderr
    $Class = Get-ResultClass $Result $ExpectedEmptyExitCodes
    $Results.Add([ordered]@{
        name = $Name
        category = $Category
        adb_arguments = $Arguments
        started_utc = $Started.ToUniversalTime().ToString('o')
        ended_utc = $Ended.ToUniversalTime().ToString('o')
        duration_seconds = [Math]::Round(($Ended - $Started).TotalSeconds, 3)
        exit_code = $Result.ExitCode
        timed_out = $Result.TimedOut
        expected_empty_exit_codes = @($ExpectedEmptyExitCodes)
        result = $Class
        stdout_file = (Join-Path $Category "$Name.stdout.txt").Replace('\', '/')
        stderr_file = (Join-Path $Category "$Name.stderr.txt").Replace('\', '/')
    })
    Write-Host "[$Category] $Name result=$Class exit=$($Result.ExitCode)"
    return $Result
}

function Invoke-DeviceSpec {
    param($Spec)
    $ExpectedEmpty = if ($Spec.expectedEmptyExitCodes) {
        [int[]]@($Spec.expectedEmptyExitCodes)
    }
    else { @() }
    Invoke-CapturedCommand -Name $Spec.name -Category $Spec.category `
        -Arguments (@('-s', $Endpoint) + @($Spec.args)) `
        -TimeoutSeconds $CommandTimeoutSeconds `
        -ExpectedEmptyExitCodes $ExpectedEmpty | Out-Null
}

function Write-CommandStatus {
    $Status = [ordered]@{
        schema = 1
        collector = 'scripts/collect-a16-p3-thermal-observability.ps1'
        collector_version = $CollectorVersion
        device_contract = 'READ_ONLY'
        endpoint = $Endpoint
        mode = $Mode
        generated_utc = [DateTime]::UtcNow.ToString('o')
        commands = $Results
    }
    Write-Utf8NoBom (Join-Path $EvidenceRoot 'META\COMMAND-STATUS.json') `
        (($Status | ConvertTo-Json -Depth 8) + "`n")
}

function Write-Sha256Manifest {
    $ManifestPath = Join-Path $EvidenceRoot 'META\SHA256SUMS.txt'
    $Lines = Get-ChildItem -LiteralPath $EvidenceRoot -File -Recurse |
        Where-Object { $_.FullName -ne $ManifestPath } |
        Sort-Object FullName |
        ForEach-Object {
            $Relative = ($_.FullName.Substring($EvidenceRoot.Length) -replace '^[\\/]+', '').Replace('\', '/')
            '{0}  {1}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant(), $Relative
        }
    Write-Utf8NoBom $ManifestPath (($Lines -join "`n") + "`n")
}

function Assert-DeviceCommandSafety {
    param([object[]]$Specs)
    $Forbidden = @(
        '(?i)(?:^|\s)(?:reboot|root|unroot|remount|disable-verity|enable-verity)(?:\s|$)',
        '(?i)(?:^|[;\s])(?:su|setprop|stop|start|kill|killall|pkill)(?:\s|$)',
        '(?i)\bsettings\s+(?:put|delete)\b',
        '(?i)\bdevice_config\s+(?:put|delete)\b',
        '(?i)\bsvc\s+(?:wifi|data|power)\b',
        '(?i)\bcmd\s+(?:wifi|connectivity|power|package)\b',
        '(?i)\bpm\s+(?:install|uninstall|disable|enable|clear|grant|revoke)\b',
        '(?i)\bam\s+(?:force-stop|kill|start)\b',
        '(?i)\binput\s+(?:keyevent|tap|swipe|text)\b',
        '(?i)(?:^|[;\s])(?:rm|mv|cp|mkdir|touch|chmod|chown|mount|umount)(?:\s|$)',
        '(?i)\blogcat\b[^;\r\n]*\s-c(?:\s|$)',
        '(?i)(?:>|>>|\btee\b)',
        '(?i)\b(?:monkey|screenrecord|bugreport)\b'
    )
    foreach ($Spec in $Specs) {
        $Command = (@($Spec.args) -join ' ')
        foreach ($Pattern in $Forbidden) {
            if ($Command -match $Pattern) {
                throw "unsafe device command '$($Spec.name)' matched $Pattern"
            }
        }
    }
}

$IdentityCommand = 'printf "BOOT_ID="; cat /proc/sys/kernel/random/boot_id; date; uptime; getprop sys.boot_completed; getprop ro.build.version.release; getprop ro.build.version.sdk; ps -A -o PID,PPID,NAME | grep -E "zygote64|zygote|system_server|surfaceflinger|audioserver|android.hardware.audio.service"'
$ThermalDiscoveryCommand = 'for z in /sys/class/thermal/thermal_zone*; do [ -d "$z" ] || continue; printf "ZONE=%s\n" "$z"; for f in type temp mode policy available_policies; do [ -r "$z/$f" ] && printf "%s=" "$f" && cat "$z/$f"; done; for f in "$z"/trip_point_*_temp "$z"/trip_point_*_type "$z"/trip_point_*_hyst; do [ -r "$f" ] && printf "%s=" "$f" && cat "$f"; done; done'
$CoolingDiscoveryCommand = 'for c in /sys/class/thermal/cooling_device*; do [ -d "$c" ] || continue; printf "COOLING=%s\n" "$c"; for f in type cur_state max_state; do [ -r "$c/$f" ] && printf "%s=" "$f" && cat "$c/$f"; done; done'
$CpuFreqDiscoveryCommand = 'for p in /sys/devices/system/cpu/cpufreq/policy*; do [ -d "$p" ] || continue; printf "CPUFREQ=%s\n" "$p"; for f in affected_cpus related_cpus scaling_cur_freq scaling_min_freq scaling_max_freq cpuinfo_cur_freq cpuinfo_min_freq cpuinfo_max_freq scaling_governor scaling_available_governors scaling_available_frequencies cpuinfo_transition_latency; do [ -r "$p/$f" ] && printf "%s=" "$f" && cat "$p/$f"; done; done'
$DevfreqDiscoveryCommand = 'for d in /sys/class/devfreq/*; do [ -d "$d" ] || continue; printf "DEVFREQ=%s TARGET=%s\n" "$d" "$(readlink -f "$d")"; for f in name governor cur_freq min_freq max_freq available_frequencies trans_stat time_in_state load; do [ -r "$d/$f" ] && printf "%s=" "$f" && cat "$d/$f"; done; done'
$VeDiscoveryCommand = 'for f in /sys/class/cedar_dev/*/ve_info /sys/devices/platform/*cedar*/ve_info /sys/devices/platform/*ve*/ve_info /sys/kernel/debug/clk/*ve*/clk_rate /sys/kernel/debug/clk/*cedar*/clk_rate /sys/kernel/debug/clk/*gpu*/clk_rate; do [ -r "$f" ] && printf "NODE=%s\n" "$f" && cat "$f"; done'
$SampleCommand = 'printf "DEVICE_TIME="; date +%s.%N; for z in /sys/class/thermal/thermal_zone*; do [ -r "$z/type" ] && [ -r "$z/temp" ] && printf "THERMAL path=%s type=%s temp=%s\n" "$z" "$(cat "$z/type")" "$(cat "$z/temp")"; done; for c in /sys/class/thermal/cooling_device*; do [ -r "$c/type" ] && [ -r "$c/cur_state" ] && printf "COOLING path=%s type=%s state=%s\n" "$c" "$(cat "$c/type")" "$(cat "$c/cur_state")"; done; for p in /sys/devices/system/cpu/cpufreq/policy*; do [ -r "$p/scaling_cur_freq" ] && printf "CPUFREQ path=%s cur=%s\n" "$p" "$(cat "$p/scaling_cur_freq")"; done; for d in /sys/class/devfreq/*; do [ -r "$d/cur_freq" ] && printf "DEVFREQ path=%s cur=%s\n" "$d" "$(cat "$d/cur_freq")"; done'

$DiscoverySpecs = @(
    [ordered]@{ name='identity'; category='10-Identity'; args=@('shell', $IdentityCommand) },
    [ordered]@{ name='thermal-zones'; category='20-Thermal'; args=@('shell', $ThermalDiscoveryCommand) },
    [ordered]@{ name='cooling-devices'; category='20-Thermal'; args=@('shell', $CoolingDiscoveryCommand) },
    [ordered]@{ name='cpufreq'; category='30-Frequency'; args=@('shell', $CpuFreqDiscoveryCommand) },
    [ordered]@{ name='devfreq'; category='30-Frequency'; args=@('shell', $DevfreqDiscoveryCommand) },
    [ordered]@{ name='ve-gpu-readable-nodes'; category='30-Frequency'; args=@('shell', $VeDiscoveryCommand) },
    [ordered]@{ name='thermal-log'; category='40-Logs'; expectedEmptyExitCodes=@(1); args=@('shell', 'logcat -b all -d -v threadtime | grep -Ei "thermal|thrott|overheat|critical temperature"') }
)
$AllDeviceSpecs = @($DiscoverySpecs) + @(
    [ordered]@{ name='sample'; category='50-Samples'; args=@('shell', $SampleCommand) }
)
Assert-DeviceCommandSafety $AllDeviceSpecs

if ($SelfTest) {
    Write-Output "P3 thermal observer executable command safety: PASS ($($AllDeviceSpecs.Count) read-only specs)"
    exit 0
}

if (-not (Test-Path -LiteralPath $AdbPath -PathType Leaf)) {
    throw "adb.exe not found: $AdbPath"
}
if ([string]::IsNullOrWhiteSpace($OutputBase)) {
    $OutputBase = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
}
$OutputBase = [System.IO.Path]::GetFullPath($OutputBase)
$RunId = [DateTime]::Now.ToString('yyyyMMdd-HHmmss')
$EvidenceRoot = Join-Path $OutputBase "UBOX10-A16-P3-THERMAL-$RunId"
foreach ($Directory in @('00-Host', '01-ADB-Entry', 'META')) {
    New-Item -ItemType Directory -Path (Join-Path $EvidenceRoot $Directory) -Force | Out-Null
}
Write-Host "P3 thermal evidence root: $EvidenceRoot"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$GitRevision = try { (& git -C $RepositoryRoot rev-parse HEAD 2>$null | Out-String).Trim() } catch { 'NOT_AVAILABLE' }
$HostMetadata = @"
collector=scripts/collect-a16-p3-thermal-observability.ps1
collector_version=$CollectorVersion
collector_git_revision=$GitRevision
host_started_utc=$([DateTime]::UtcNow.ToString('o'))
endpoint=$Endpoint
mode=$Mode
sample_interval_seconds=$SampleIntervalSeconds
duration_seconds=$DurationSeconds
device_contract=READ_ONLY
playback_control=NONE_MANUAL_EXTERNAL_ONLY
automated_abort_or_power_action=NONE
"@
Write-Utf8NoBom (Join-Path $EvidenceRoot '00-Host\COLLECTOR.txt') $HostMetadata

Invoke-CapturedCommand -Name 'adb-version' -Category '00-Host' `
    -Arguments @('version') -TimeoutSeconds 15 | Out-Null
Invoke-CapturedCommand -Name 'adb-connect' -Category '01-ADB-Entry' `
    -Arguments @('connect', $Endpoint) -TimeoutSeconds 20 | Out-Null
$State = Invoke-CapturedCommand -Name 'adb-get-state' -Category '01-ADB-Entry' `
    -Arguments @('-s', $Endpoint, 'get-state') -TimeoutSeconds 15
if ($State.ExitCode -ne 0 -or $State.Stdout.Trim() -ne 'device') {
    Write-CommandStatus
    Write-Sha256Manifest
    throw "ADB endpoint is not ready; evidence root preserved: $EvidenceRoot"
}

foreach ($Spec in $DiscoverySpecs) { Invoke-DeviceSpec $Spec }
if ($Mode -eq 'Sample') {
    $Started = [DateTime]::UtcNow
    $Deadline = $Started.AddSeconds($DurationSeconds)
    $Index = 0
    while ([DateTime]::UtcNow -lt $Deadline) {
        $Spec = [ordered]@{
            name = ('sample-{0:d4}' -f $Index)
            category = '50-Samples'
            args = @('shell', $SampleCommand)
        }
        Invoke-DeviceSpec $Spec
        $Index++
        if ([DateTime]::UtcNow -lt $Deadline) {
            Start-Sleep -Seconds $SampleIntervalSeconds
        }
    }
    $PostSpec = [ordered]@{
        name = 'identity-post'
        category = '60-Post'
        args = @('shell', $IdentityCommand)
    }
    Invoke-DeviceSpec $PostSpec
}

$Summary = @"
status=COLLECTION_COMPLETE_ANALYSIS_PENDING
device_contract=READ_ONLY
mode=$Mode
endpoint=$Endpoint
sample_interval_seconds=$SampleIntervalSeconds
duration_seconds=$DurationSeconds
playback_control=NONE_MANUAL_EXTERNAL_ONLY
no_automated_abort_or_power_action=true
"@
Write-Utf8NoBom (Join-Path $EvidenceRoot 'COLLECTION-SUMMARY.txt') $Summary
Write-CommandStatus
Write-Sha256Manifest
$Failures = @($Results | Where-Object { $_.result -notin @('SUCCESS', 'EMPTY_SUCCESS') }).Count
Write-Host "P3 thermal evidence root complete: $EvidenceRoot"
Write-Host "Commands=$($Results.Count) non-success=$Failures. Failures are preserved, not hidden."
Write-Host 'No device state or media playback was controlled by this observer.'
