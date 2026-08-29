[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._:\[\]-]+$')]
    [string]$DeviceEndpoint,

    [ValidateRange(1, 65535)]
    [int]$Port = 7896,

    [ValidateSet('Baseline', 'AVCPre', 'AVCPost', 'HEVCPre', 'HEVCPostRestart', 'Final')]
    [string]$Phase = 'Baseline',

    [string]$OutputRoot,

    [string]$AdbExecutable,

    [ValidateRange(30, 1800)]
    [int]$AdbReturnTimeoutSeconds = 600,

    [switch]$ClearLogcat,

    [switch]$NoConnect,

    [switch]$SelfTest
)

# Paired r7-diag1 evidence collector for Windows PowerShell 7.
# Invoke one phase at a time. Playback remains a deliberate manual action.
$ErrorActionPreference = 'Stop'
$Candidate = 'a16-prototype-b-r7-diag1'
$CandidateSha256 = 'A68E7BD75D9819794BE22E9E05BE76969B2883DF8965DC277482E8C99231C6A4'
$Prefix = 'UBOX_R7_DIAG1'

$CoreCommands = [ordered]@{
    'identity-and-abi.txt' = 'getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.build.id; getprop ro.build.version.security_patch; getprop ro.zygote; getprop ro.product.cpu.abilist; getprop ro.product.cpu.abilist64; getprop ro.product.cpu.abilist32; uname -a'
    'uptime-and-boot-id.txt' = 'date; uptime; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id; getprop ro.runtime.firstboot; getprop sys.boot_completed; getprop dev.bootcomplete'
    'core-processes.txt' = "ps -A -o USER,PID,PPID,ELAPSED,NAME | grep -E 'zygote|surfaceflinger|system_server|media|codec|extractor|audioserver|android.hardware.audio'"
    'core-services.txt' = 'service list; getprop init.svc.surfaceflinger; getprop init.svc.zygote; getprop init.svc.zygote_secondary; getprop init.svc.audioserver; getprop init.svc.media.swcodec'
    'properties.txt' = 'getprop'
    'surfaceflinger.txt' = 'dumpsys SurfaceFlinger'
    'surfaceflinger-layers.txt' = 'dumpsys SurfaceFlinger --list'
    'media-codec.txt' = 'dumpsys media.codec'
    'media-extractor.txt' = 'dumpsys media.extractor'
    'audioflinger.txt' = 'dumpsys media.audio_flinger'
    'tombstone-list.txt' = 'ls -la /data/tombstones 2>&1; for f in /data/tombstones/*; do test -f "$f" && echo "--- $f" && stat "$f"; done 2>&1'
    'pstore-list.txt' = 'ls -la /sys/fs/pstore 2>&1'
}

$LogCommands = [ordered]@{
    'logcat-all.txt' = 'logcat -b all -d -v threadtime'
    'logcat-crash.txt' = 'logcat -b crash -d -v threadtime'
    'diag1-lines.txt' = "logcat -b all -d -v threadtime | grep '$Prefix'"
    'media-codec-lines.txt' = "logcat -b all -d -v threadtime | grep -Ei 'MediaCodec|ACodec|CCodec|OMX|codec2|Cedar|VE|decoder|video/avc|video/hevc' | tail -n 12000"
    'renderengine-lines.txt' = "logcat -b all -d -v threadtime | grep -Ei 'SurfaceFlinger|RenderEngine|Ganesh|Skia|EGL|GLES|GraphicBuffer|AHardwareBuffer|valid texture' | tail -n 12000"
    'gralloc-hwc-lines.txt' = "logcat -b all -d -v threadtime | grep -Ei 'gralloc|mapper|HWC|hwcomposer|composition|YV12|32315659|AFBC' | tail -n 12000"
    'restart-crash-lines.txt' = "logcat -b all -d -v threadtime | grep -Ei 'Fatal signal|SIGABRT|SIGSEGV|tombstone|surfaceflinger|zygote|system_server|service.*restart|boot_progress' | tail -n 12000"
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [AllowEmptyString()][Parameter(Mandatory = $true)][string]$Text
    )
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

function Resolve-Target {
    if ($DeviceEndpoint.StartsWith('[')) {
        if ($DeviceEndpoint -match '^\[[^]]+\]:[0-9]+$') { return $DeviceEndpoint }
        return "${DeviceEndpoint}:$Port"
    }
    if ($DeviceEndpoint -match '^[^:]+:[0-9]+$') { return $DeviceEndpoint }
    return "${DeviceEndpoint}:$Port"
}

function Get-AllDeviceCommands {
    return @($CoreCommands.Values) + @($LogCommands.Values)
}

function Invoke-SafetySelfTest {
    $forbidden = @(
        '(?i)(^|[;&| ]+)reboot([;&| ]|$)',
        '(?i)(^|[;&| ]+)(?:setprop|remount|mount|umount)([;&| ]|$)',
        '(?i)settings\s+put',
        '(?i)svc\s+',
        '(?i)wm\s+(?:size|density)',
        '(?i)(?:persist\.disp|vendor\.sys\.disp)',
        '(?i)rm\s+',
        '(?i)pm\s+(?:install|uninstall|grant|revoke)'
    )
    foreach ($command in Get-AllDeviceCommands) {
        foreach ($pattern in $forbidden) {
            if ($command -match $pattern) {
                throw "diag1 safety self-test rejected command: $command"
            }
        }
    }
    if ((Get-AllDeviceCommands) -match 'logcat\s+-c') {
        throw 'logcat clearing must remain an explicit host-side Pre-phase action'
    }
    Write-Output 'R7-diag1 paired capture safety self-test: PASS'
}

if ($SelfTest) {
    Invoke-SafetySelfTest
    exit 0
}

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($AdbExecutable)) {
    $BundledAdb = Join-Path $RepositoryRoot 'tools\platform-tools\adb.exe'
    if (Test-Path -LiteralPath $BundledAdb -PathType Leaf) {
        $AdbPath = $BundledAdb
    }
    else {
        $AdbCommand = Get-Command adb -ErrorAction SilentlyContinue
        if ($null -eq $AdbCommand) { throw 'ADB not found; use -AdbExecutable.' }
        $AdbPath = $AdbCommand.Source
    }
}
else {
    $AdbPath = $AdbExecutable
}
if (-not (Test-Path -LiteralPath $AdbPath -PathType Leaf)) {
    throw "ADB executable not found: $AdbPath"
}

$Target = Resolve-Target
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $Downloads = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
    $OutputRoot = Join-Path $Downloads 'UBOX10-r7-diag1-paired'
}
$Timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$CaptureRoot = Join-Path $OutputRoot ("$Timestamp-$($Phase.ToLowerInvariant())")
New-Item -ItemType Directory -Path $CaptureRoot -Force | Out-Null

function Connect-Device {
    if (-not $NoConnect) {
        & $AdbPath connect $Target | Out-Null
    }
    & $AdbPath -s $Target get-state | Out-Null
    return $LASTEXITCODE -eq 0
}

function Wait-ForAdbReturn {
    $Deadline = [DateTime]::UtcNow.AddSeconds($AdbReturnTimeoutSeconds)
    do {
        if (Connect-Device) { return }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $Deadline)
    throw "ADB did not return within $AdbReturnTimeoutSeconds seconds. Do not reboot; retain existing evidence."
}

function Invoke-AdbCapture {
    param(
        [Parameter(Mandatory = $true)][string]$FileName,
        [Parameter(Mandatory = $true)][string]$Command
    )
    $Output = & $AdbPath -s $Target shell $Command 2>&1 | Out-String
    $ExitCode = $LASTEXITCODE
    $Body = @"
candidate=$Candidate
candidate_sha256=$CandidateSha256
phase=$Phase
captured_utc=$([DateTime]::UtcNow.ToString('o'))
device_endpoint=<REDACTED>
command=$Command
exit_code=$ExitCode

$Output
"@
    Write-Utf8NoBom -Path (Join-Path $CaptureRoot $FileName) -Text $Body
}

function Invoke-CommandGroup {
    param([Parameter(Mandatory = $true)]$Group)
    foreach ($Entry in $Group.GetEnumerator()) {
        Invoke-AdbCapture -FileName $Entry.Key -Command $Entry.Value
    }
}

function Capture-Tombstones {
    $Destination = Join-Path $CaptureRoot 'tombstones'
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $Output = & $AdbPath -s $Target pull /data/tombstones $Destination 2>&1 | Out-String
    Write-Utf8NoBom -Path (Join-Path $CaptureRoot 'tombstone-pull.txt') -Text $Output
}

function Capture-Window {
    Invoke-CommandGroup $CoreCommands
    Invoke-CommandGroup $LogCommands
    Capture-Tombstones
}

function Clear-LogcatIfRequested {
    if (-not $ClearLogcat) {
        Write-Host 'Logcat was NOT cleared. Add -ClearLogcat only to AVCPre or HEVCPre for a clean playback window.'
        return
    }
    if ($Phase -notin @('AVCPre', 'HEVCPre')) {
        throw '-ClearLogcat is permitted only in AVCPre or HEVCPre; never clear after a failure.'
    }
    $Confirmation = Read-Host "Type CLEAR-$Phase to clear logcat now, after the pre-capture"
    if ($Confirmation -cne "CLEAR-$Phase") {
        throw 'Logcat clear cancelled; evidence already captured remains on disk.'
    }
    $Output = & $AdbPath -s $Target logcat -b all -c 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "ADB logcat clear failed: $Output" }
    Write-Utf8NoBom -Path (Join-Path $CaptureRoot 'logcat-clear-record.txt') -Text @"
candidate=$Candidate
phase=$Phase
cleared_utc=$([DateTime]::UtcNow.ToString('o'))
scope=logcat buffers only
pstore_cleared=false
tombstones_cleared=false
"@
}

$Manifest = @"
candidate=$Candidate
candidate_sha256=$CandidateSha256
phase=$Phase
captured_utc=$([DateTime]::UtcNow.ToString('o'))
device_endpoint=<REDACTED>
adb_tcp_default_port=$Port
instrumentation_prefix=$Prefix
physical_playback=MANUAL_ONE_FIXTURE_ONE_TIME
automatic_reboot=false
automatic_hdmi_or_wm_change=false
"@
Write-Utf8NoBom -Path (Join-Path $CaptureRoot 'capture-manifest.txt') -Text $Manifest

if ($Phase -eq 'HEVCPostRestart') {
    Write-Host 'Waiting for ADB to return after the possible SurfaceFlinger/framework userspace restart.'
    Wait-ForAdbReturn
}
elseif (-not (Connect-Device)) {
    throw 'ADB device is unavailable. Do not reboot automatically.'
}

switch ($Phase) {
    'Baseline' {
        Capture-Window
        Write-Host 'Baseline captured. Next invoke AVCPre; playback is not started by this script.'
    }
    'AVCPre' {
        Capture-Window
        Clear-LogcatIfRequested
        Write-Host 'Now play the known-good H.264 fixture exactly once and visually confirm video/audio; then invoke AVCPost.'
    }
    'AVCPost' {
        Capture-Window
        Write-Host 'AVC post-window captured. Next invoke HEVCPre.'
    }
    'HEVCPre' {
        Capture-Window
        Clear-LogcatIfRequested
        Write-Host 'Now launch the known HEVC fixture exactly once. Do not loop it. If ADB drops, wait for userspace recovery, then invoke HEVCPostRestart.'
    }
    'HEVCPostRestart' {
        Capture-Window
        Write-Host 'HEVC recovery window captured without rebooting or changing display state.'
    }
    'Final' {
        Capture-Window
        Write-Host 'Final paired diagnostic window captured.'
    }
}

Write-Host "R7-diag1 $Phase capture complete: $CaptureRoot"
