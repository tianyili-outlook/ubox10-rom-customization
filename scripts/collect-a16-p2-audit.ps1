[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+:7896$')]
    [string]$Endpoint,

    [string]$AdbPath = 'C:\platform-tools\adb.exe',

    [string]$OutputBase,

    [ValidateRange(0, 3600)]
    [int]$SteadyStateWaitSeconds = 180,

    [ValidateRange(5, 600)]
    [int]$CommandTimeoutSeconds = 60,

    [switch]$FinalizeOnly,

    [string]$EvidenceRoot,

    [string]$UartLogPath,

    [switch]$SelfTest
)

# UBOX10 Android 16 P2 one-shot boot/runtime audit collector.
# Every Android command below is observational. UART is captured independently.
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

function Protect-EvidenceText {
    param([AllowEmptyString()][string]$Text)
    if ($null -eq $Text) { return '' }
    $Value = $Text.Replace([char]0, "`n")
    $Value = [regex]::Replace($Value,
        '(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])',
        '<REDACTED-MAC>')
    $Value = [regex]::Replace($Value,
        '(?i)\b[A-Z0-9._%+-]+@[A-Z][A-Z0-9.-]*\.[A-Z]{2,}\b',
        '<REDACTED-EMAIL>')
    $Value = [regex]::Replace($Value,
        '(?i)(\bSSID\s*[:=]\s*)(?:"[^"\r\n]*"|[^\s,\r\n]+)',
        '$1<REDACTED-SSID>')
    $Value = [regex]::Replace($Value,
        '(?im)^([^\r\n]*(?:password|passwd|passphrase|psk|token|cookie|credential|private.key|secret)\s*[:=]\s*).+$',
        '$1<REDACTED-SECRET>')
    $Value = [regex]::Replace($Value,
        '(?im)^(\s*\[(?:ro\.)?(?:boot\.)?serialno\]\s*:\s*)\[[^\]]*\](\s*)$',
        '$1[<REDACTED-SERIAL>]$2')
    return $Value
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
    Write-Utf8NoBom $StdoutPath (Protect-EvidenceText $Result.Stdout)
    Write-Utf8NoBom $StderrPath (Protect-EvidenceText $Result.Stderr)
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
    $Timeout = if ($Spec.timeout) { [int]$Spec.timeout } else { $CommandTimeoutSeconds }
    $ExpectedEmpty = if ($Spec.expectedEmptyExitCodes) {
        [int[]]@($Spec.expectedEmptyExitCodes)
    }
    else { @() }
    Invoke-CapturedCommand -Name $Spec.name -Category $Spec.category `
        -Arguments (@('-s', $Endpoint) + @($Spec.args)) -TimeoutSeconds $Timeout `
        -ExpectedEmptyExitCodes $ExpectedEmpty | Out-Null
}

function Write-CommandStatus {
    $Status = [ordered]@{
        schema = 1
        collector = 'scripts/collect-a16-p2-audit.ps1'
        collector_version = $CollectorVersion
        read_only_device_contract = $true
        endpoint = $Endpoint
        generated_utc = [DateTime]::UtcNow.ToString('o')
        commands = $Results
    }
    Write-Utf8NoBom (Join-Path $EvidenceRoot 'META\COMMAND-STATUS.json') `
        (($Status | ConvertTo-Json -Depth 8) + "`n")
}

function Write-Sha256Manifest {
    New-Item -ItemType Directory -Path (Join-Path $EvidenceRoot 'META') -Force | Out-Null
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
        '(?i)\bsvc\s+(?:wifi|data|power)\b',
        '(?i)\bcmd\s+(?:wifi|connectivity|power|package)\b',
        '(?i)\bpm\s+(?:install|uninstall|disable|enable|clear|grant|revoke)\b',
        '(?i)\bam\s+(?:force-stop|kill|start)\b',
        '(?i)\binput\s+(?:keyevent|tap|swipe|text)\b',
        '(?i)(?:^|[;\s])(?:rm|mv|cp|mkdir|touch|chmod|chown|umount)(?:\s|$)',
        '(?i)\blogcat\b[^;\r\n]*\s-c(?:\s|$)',
        '(?i)(?:^|[;\s])mount\s+[^|;]+',
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

$T0Specs = @(
    [ordered]@{ name='critical-state'; category='10-BootSnapshot-T0'; timeout=15; args=@('shell', 'date; uptime; printf "BOOT_ID="; cat /proc/sys/kernel/random/boot_id; getprop sys.boot_completed; getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.zygote; getprop ro.product.cpu.abilist; getenforce; ps -A -o PID,PPID,NAME | grep -E "zygote|system_server|surfaceflinger|audioserver|android.hardware.audio.service"') },
    [ordered]@{ name='logcat-all-early'; category='10-BootSnapshot-T0'; timeout=90; args=@('logcat', '-b', 'all', '-d', '-v', 'threadtime') },
    [ordered]@{ name='logcat-crash-early'; category='10-BootSnapshot-T0'; timeout=30; args=@('logcat', '-b', 'crash', '-d', '-v', 'threadtime') },
    [ordered]@{ name='properties'; category='20-System'; timeout=20; args=@('shell', 'getprop') },
    [ordered]@{ name='process-census'; category='20-System'; timeout=20; args=@('shell', 'ps -A -o USER,PID,PPID,ELAPSED,NAME') },
    [ordered]@{ name='init-services'; category='20-System'; timeout=15; args=@('shell', 'getprop | grep "\[init.svc"') },
    [ordered]@{ name='service-list'; category='20-System'; timeout=30; args=@('shell', 'service list') },
    [ordered]@{ name='dumpsys-list'; category='20-System'; timeout=30; args=@('shell', 'dumpsys -l') },
    [ordered]@{ name='kernel-runtime'; category='20-System'; timeout=15; args=@('shell', 'cat /proc/cmdline; cat /proc/version; cat /proc/meminfo; cat /proc/uptime; cat /proc/modules') },
    [ordered]@{ name='dmesg'; category='20-System'; timeout=45; args=@('shell', 'dmesg') },
    [ordered]@{ name='pstore'; category='20-System'; timeout=30; args=@('shell', 'ls -la /sys/fs/pstore; for f in /sys/fs/pstore/*; do test -f "$f" && echo "===== $f =====" && cat "$f"; done') },
    [ordered]@{ name='lshal'; category='30-HAL-VINTF'; timeout=60; args=@('shell', 'lshal') },
    [ordered]@{ name='treble-vndk-properties'; category='30-HAL-VINTF'; timeout=15; args=@('shell', 'getprop ro.treble.enabled; getprop ro.vndk.version; getprop ro.vendor.vndk.version; getprop ro.product.first_api_level; getprop ro.vendor.api_level') },
    [ordered]@{ name='vintf-file-list'; category='30-HAL-VINTF'; timeout=30; args=@('shell', 'find /system/etc/vintf /system/system_ext/etc/vintf /vendor/etc/vintf /product/etc/vintf -type f -print') },
    [ordered]@{ name='tombstones-anr-list'; category='30-Crash-Restart'; timeout=20; args=@('shell', 'ls -la /data/tombstones; ls -la /data/anr') },
    [ordered]@{ name='dropbox-crash-metadata'; category='30-Crash-Restart'; timeout=60; args=@('shell', 'dumpsys dropbox --print SYSTEM_TOMBSTONE') },
    [ordered]@{ name='selinux-state'; category='40-SELinux'; timeout=15; args=@('shell', 'getenforce; getprop ro.boot.selinux; getprop ro.build.selinux; ps -AZ') },
    [ordered]@{ name='selinux-logcat-avc'; category='40-SELinux'; timeout=45; expectedEmptyExitCodes=@(1); args=@('shell', 'logcat -b all -d -v threadtime | grep -i "avc:.*denied"') },
    [ordered]@{ name='surfaceflinger'; category='50-Display'; timeout=120; args=@('shell', 'dumpsys SurfaceFlinger') },
    [ordered]@{ name='display'; category='50-Display'; timeout=90; args=@('shell', 'dumpsys display') },
    [ordered]@{ name='wm-state'; category='50-Display'; timeout=15; args=@('shell', 'wm size; wm density; getprop ro.hardware.egl; getprop ro.board.platform') },
    [ordered]@{ name='audio-flinger'; category='60-Audio-Media'; timeout=90; args=@('shell', 'dumpsys media.audio_flinger') },
    [ordered]@{ name='audio-policy'; category='60-Audio-Media'; timeout=90; args=@('shell', 'dumpsys media.audio_policy') },
    [ordered]@{ name='media-codec'; category='60-Audio-Media'; timeout=90; args=@('shell', 'dumpsys media.codec') },
    [ordered]@{ name='media-services'; category='60-Audio-Media'; timeout=30; args=@('shell', 'service list | grep -Ei "media|audio|codec"; ps -A -o PID,PPID,ELAPSED,NAME | grep -Ei "media|audio|codec|OMX|cedar"') },
    [ordered]@{ name='wifi'; category='70-Network'; timeout=120; args=@('shell', 'dumpsys wifi') },
    [ordered]@{ name='connectivity'; category='70-Network'; timeout=90; args=@('shell', 'dumpsys connectivity') },
    [ordered]@{ name='ip-state'; category='70-Network'; timeout=20; args=@('shell', 'ip addr; ip route; getprop | grep -Ei "dns|dhcp|wifi|network"') },
    [ordered]@{ name='power'; category='80-Power-Thermal'; timeout=90; args=@('shell', 'dumpsys power') },
    [ordered]@{ name='battery'; category='80-Power-Thermal'; timeout=45; args=@('shell', 'dumpsys battery') },
    [ordered]@{ name='thermal'; category='80-Power-Thermal'; timeout=60; args=@('shell', 'dumpsys thermalservice') },
    [ordered]@{ name='wakeup-sources'; category='80-Power-Thermal'; timeout=30; args=@('shell', 'cat /sys/kernel/debug/wakeup_sources; cat /proc/wakelocks') },
    [ordered]@{ name='filesystems'; category='90-Storage-Packages'; timeout=30; args=@('shell', 'df -h; cat /proc/mounts; mount') },
    [ordered]@{ name='storage'; category='90-Storage-Packages'; timeout=60; args=@('shell', 'dumpsys mount; dumpsys vold') },
    [ordered]@{ name='packages'; category='90-Storage-Packages'; timeout=60; args=@('shell', 'pm list packages; pm list features; pm list libraries') }
)

$T1Specs = @(
    [ordered]@{ name='critical-state'; category='A0-SteadyState-T1'; timeout=15; args=@('shell', 'date; uptime; printf "BOOT_ID="; cat /proc/sys/kernel/random/boot_id; getprop sys.boot_completed; getenforce; ps -A -o PID,PPID,NAME | grep -E "zygote|system_server|surfaceflinger|audioserver|android.hardware.audio.service"') },
    [ordered]@{ name='process-census'; category='A0-SteadyState-T1'; timeout=20; args=@('shell', 'ps -A -o USER,PID,PPID,ELAPSED,NAME') },
    [ordered]@{ name='init-services'; category='A0-SteadyState-T1'; timeout=15; args=@('shell', 'getprop | grep "\[init.svc"') },
    [ordered]@{ name='lshal'; category='A0-SteadyState-T1'; timeout=60; args=@('shell', 'lshal') },
    [ordered]@{ name='tombstones-anr-list'; category='A0-SteadyState-T1'; timeout=20; args=@('shell', 'ls -la /data/tombstones; ls -la /data/anr') },
    [ordered]@{ name='selinux-logcat-avc'; category='A0-SteadyState-T1'; timeout=45; expectedEmptyExitCodes=@(1); args=@('shell', 'logcat -b all -d -v threadtime | grep -i "avc:.*denied"') },
    [ordered]@{ name='audio-flinger'; category='A0-SteadyState-T1'; timeout=90; args=@('shell', 'dumpsys media.audio_flinger') },
    [ordered]@{ name='surfaceflinger'; category='A0-SteadyState-T1'; timeout=120; args=@('shell', 'dumpsys SurfaceFlinger') },
    [ordered]@{ name='logcat-all'; category='B0-Final'; timeout=120; args=@('logcat', '-b', 'all', '-d', '-v', 'threadtime') },
    [ordered]@{ name='logcat-crash'; category='B0-Final'; timeout=30; args=@('logcat', '-b', 'crash', '-d', '-v', 'threadtime') }
)

$AllDeviceSpecs = @($T0Specs) + @($T1Specs)
Assert-DeviceCommandSafety $AllDeviceSpecs

if ($SelfTest) {
    Write-Output "P2 collector executable command safety: PASS ($($AllDeviceSpecs.Count) read-only specs)"
    exit 0
}

if ($FinalizeOnly) {
    if ([string]::IsNullOrWhiteSpace($EvidenceRoot) -or
        -not (Test-Path -LiteralPath $EvidenceRoot -PathType Container)) {
        throw '-FinalizeOnly requires an existing host-side -EvidenceRoot.'
    }
    $EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
    if (-not [string]::IsNullOrWhiteSpace($UartLogPath)) {
        if (-not (Test-Path -LiteralPath $UartLogPath -PathType Leaf)) {
            throw "UART logfile not found: $UartLogPath"
        }
        $HostDirectory = Join-Path $EvidenceRoot '00-Host'
        New-Item -ItemType Directory -Path $HostDirectory -Force | Out-Null
        $Destination = Join-Path $HostDirectory 'UART-passive.log'
        $UartHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $UartLogPath).Hash
        if (Test-Path -LiteralPath $Destination -PathType Leaf) {
            $ExistingHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash
            if ($ExistingHash -ne $UartHash) {
                throw 'Refusing to overwrite UART-passive.log with different content.'
            }
        }
        else {
            Copy-Item -LiteralPath $UartLogPath -Destination $Destination
        }
        Write-Utf8NoBom (Join-Path $HostDirectory 'UART-METADATA.txt') `
            "capture=PASSIVE_EXTERNAL`nsha256=$UartHash`ncommands_entered=false`n"
        $SummaryPath = Join-Path $EvidenceRoot 'COLLECTION-SUMMARY.txt'
        if (Test-Path -LiteralPath $SummaryPath -PathType Leaf) {
            $ExistingSummary = Get-Content -LiteralPath $SummaryPath -Raw
            if ($ExistingSummary -notmatch '(?m)^finalized_uart_included=true$') {
                Write-Utf8NoBom $SummaryPath `
                    ($ExistingSummary + "finalized_uart_included=true`n")
            }
        }
    }
    Write-Sha256Manifest
    Write-Host "P2 evidence finalized without ADB/device access: $EvidenceRoot"
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Endpoint)) {
    throw '-Endpoint is required, for example 192.168.x.x:7896.'
}
if (-not (Test-Path -LiteralPath $AdbPath -PathType Leaf)) {
    throw "adb.exe not found: $AdbPath"
}
if ([string]::IsNullOrWhiteSpace($OutputBase)) {
    $OutputBase = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
}
$OutputBase = [System.IO.Path]::GetFullPath($OutputBase)
$RunId = [DateTime]::Now.ToString('yyyyMMdd-HHmmss')
$EvidenceRoot = Join-Path $OutputBase "UBOX10-A16-P2-AUDIT-$RunId"
foreach ($Directory in @('00-Host', '01-ADB-Entry', 'META')) {
    New-Item -ItemType Directory -Path (Join-Path $EvidenceRoot $Directory) -Force | Out-Null
}
Write-Host "P2 evidence root: $EvidenceRoot"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$GitRevision = try { (& git -C $RepositoryRoot rev-parse HEAD 2>$null | Out-String).Trim() } catch { 'NOT_AVAILABLE' }
$HostMetadata = @"
collector=scripts/collect-a16-p2-audit.ps1
collector_version=$CollectorVersion
collector_git_revision=$GitRevision
host_started_utc=$([DateTime]::UtcNow.ToString('o'))
endpoint=$Endpoint
steady_state_wait_seconds=$SteadyStateWaitSeconds
command_timeout_seconds=$CommandTimeoutSeconds
device_contract=READ_ONLY
uart_control=NONE_EXTERNAL_PASSIVE_CAPTURE_ONLY
"@
Write-Utf8NoBom (Join-Path $EvidenceRoot '00-Host\COLLECTOR.txt') $HostMetadata

$AdbVersion = Invoke-CapturedCommand -Name 'adb-version' -Category '00-Host' `
    -Arguments @('version') -TimeoutSeconds 15
$AdbDevices = Invoke-CapturedCommand -Name 'adb-devices' -Category '01-ADB-Entry' `
    -Arguments @('devices', '-l') -TimeoutSeconds 15
$Connect = Invoke-CapturedCommand -Name 'adb-connect' -Category '01-ADB-Entry' `
    -Arguments @('connect', $Endpoint) -TimeoutSeconds 20
$State = Invoke-CapturedCommand -Name 'adb-get-state' -Category '01-ADB-Entry' `
    -Arguments @('-s', $Endpoint, 'get-state') -TimeoutSeconds 15
if ($State.ExitCode -ne 0 -or $State.Stdout.Trim() -ne 'device') {
    Write-CommandStatus
    Write-Sha256Manifest
    throw "ADB endpoint is not ready; evidence root preserved: $EvidenceRoot"
}

foreach ($Spec in $T0Specs) { Invoke-DeviceSpec $Spec }
$WaitStart = [DateTime]::UtcNow
New-Item -ItemType Directory -Path (Join-Path $EvidenceRoot 'A0-SteadyState-T1') -Force |
    Out-Null
Write-Utf8NoBom (Join-Path $EvidenceRoot 'A0-SteadyState-T1\IDLE-WINDOW.txt') `
    "started_utc=$($WaitStart.ToString('o'))`nseconds=$SteadyStateWaitSeconds`nworkload=NONE`n"
Write-Host "Idle steady-state wait: $SteadyStateWaitSeconds seconds. Do not touch the device."
Start-Sleep -Seconds $SteadyStateWaitSeconds
foreach ($Spec in $T1Specs) { Invoke-DeviceSpec $Spec }

$T0Critical = Get-Content -LiteralPath (Join-Path $EvidenceRoot '10-BootSnapshot-T0\critical-state.stdout.txt')
$T1Critical = Get-Content -LiteralPath (Join-Path $EvidenceRoot 'A0-SteadyState-T1\critical-state.stdout.txt')
$BootIdPattern = '(?i)^BOOT_ID=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
$CriticalProcessPattern = '^\s*[0-9]+\s+[0-9]+\s+(?:zygote64|zygote|system_server|surfaceflinger|audioserver|android\.hardware\.audio\.service)\s*$'
$T0Comparable = @($T0Critical | Where-Object {
    $_ -match $BootIdPattern -or $_ -match $CriticalProcessPattern
})
$T1Comparable = @($T1Critical | Where-Object {
    $_ -match $BootIdPattern -or $_ -match $CriticalProcessPattern
})
$Difference = Compare-Object -ReferenceObject $T0Comparable -DifferenceObject $T1Comparable |
    Out-String -Width 240
$Comparison = "T0/T1 boot-id and critical-process textual diff (empty means identical):`n$Difference"
Write-Utf8NoBom (Join-Path $EvidenceRoot 'B0-Final\critical-pid-diff.txt') $Comparison

$Summary = @"
status=COLLECTION_COMPLETE_ANALYSIS_PENDING
device_contract=READ_ONLY
endpoint=$Endpoint
t0_commands=$($T0Specs.Count)
t1_commands=$($T1Specs.Count)
steady_state_wait_seconds=$SteadyStateWaitSeconds
uart_included=false
next=STOP_PRESERVE_EVIDENCE_ADD_PASSIVE_UART_WITH_FINALIZEONLY_THEN_ANALYZE_SEPARATELY
no_automated_pass_fail=true
"@
Write-Utf8NoBom (Join-Path $EvidenceRoot 'COLLECTION-SUMMARY.txt') $Summary
Write-CommandStatus
Write-Sha256Manifest
$Failures = @($Results | Where-Object { $_.result -notin @('SUCCESS', 'EMPTY_SUCCESS') }).Count
Write-Host "P2 evidence root complete: $EvidenceRoot"
Write-Host "Commands=$($Results.Count) non-success=$Failures. Failures are preserved, not hidden."
Write-Host 'No device state was changed. No automated audit verdict was produced.'
