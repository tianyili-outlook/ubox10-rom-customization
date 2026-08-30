[CmdletBinding()]
param(
    [ValidateSet('BootGate', 'AVCPre', 'AVCLive', 'AVCPost', 'HEVCPre', 'HEVCLive', 'HEVCPostRestart')]
    [string]$Phase = 'BootGate',

    [ValidatePattern('^[A-Za-z0-9._:\[\]-]+$')]
    [string]$DeviceEndpoint = '192.168.1.9:7896',

    [string]$AdbExecutable = 'C:\platform-tools\adb.exe',

    [string]$OutputRoot,

    [ValidateRange(30, 1800)]
    [int]$AdbReturnTimeoutSeconds = 600,

    [switch]$ClearLogcat,

    [switch]$SelfTest
)

# PowerShell 7, one operator-invoked phase at a time. Playback is always manual.
$ErrorActionPreference = 'Stop'
$Candidate = 'a16-prototype-b-r7-diag3-private-buffer-metadata'
$CandidateSha256 = '385BA2FEDAC0C8726885781693017C7DD4A62D35D50C6494B905D4A2812E958E'

function Write-Utf8NoBom {
    param([string]$Path, [AllowEmptyString()][string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

function Invoke-SafetySelfTest {
    $Source = Get-Content -LiteralPath $PSCommandPath -Raw
    foreach ($Forbidden in @(
        '(?im)^\s*&\s*\$AdbExecutable.*\breboot\b',
        '(?im)\bshell\s+(?:rm|setprop|settings\s+put|wm\s+size|mount|umount)\b',
        '(?im)\b(?:shutdown|poweroff|halt)\b'
    )) {
        if ($Source -match $Forbidden) { throw "unsafe command pattern: $Forbidden" }
    }
    Write-Output 'R7-diag3 paired live-capture safety self-test: PASS'
}

if ($SelfTest) {
    Invoke-SafetySelfTest
    exit 0
}

if (-not (Test-Path -LiteralPath $AdbExecutable -PathType Leaf)) {
    throw "ADB executable not found: $AdbExecutable"
}
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path (Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads') `
        'UBOX10-r7-diag3-private-buffer-metadata'
}
$Timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$CaptureRoot = Join-Path $OutputRoot ("$Timestamp-$($Phase.ToLowerInvariant())")
New-Item -ItemType Directory -Path $CaptureRoot -Force | Out-Null

function Test-Adb {
    & $AdbExecutable connect $DeviceEndpoint | Out-Null
    & $AdbExecutable -s $DeviceEndpoint get-state 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Wait-Adb {
    $Deadline = [DateTime]::UtcNow.AddSeconds($AdbReturnTimeoutSeconds)
    do {
        if (Test-Adb) { return }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $Deadline)
    throw 'ADB did not return. Do not reboot; preserve the live host log and device evidence.'
}

function Save-Shell {
    param([string]$Name, [string]$Command)
    $Text = & $AdbExecutable -s $DeviceEndpoint shell $Command 2>&1 | Out-String
    Write-Utf8NoBom (Join-Path $CaptureRoot $Name) $Text
}

function Save-QuickState {
    Save-Shell 'identity-uptime-services.txt' `
        'date; uptime; cat /proc/sys/kernel/random/boot_id; getprop ro.build.id; getprop ro.build.version.sdk; getprop ro.zygote; getprop ro.product.cpu.abilist; getprop sys.boot_completed; getprop init.svc.surfaceflinger; getprop init.svc.zygote; getprop init.svc.vendor.gralloc-2-0; getprop init.svc.vendor.hwcomposer-2-2'
    Save-Shell 'processes.txt' `
        "ps -A -o USER,PID,PPID,ELAPSED,NAME | grep -E 'zygote|surfaceflinger|system_server|media|codec|OMX|audio'"
    Save-Shell 'diag-lines.txt' `
        "logcat -b all -d -v threadtime | grep -E 'UBOX_R7_DIAG1|UBOX_R7_DIAG3'"
    Save-Shell 'crash-lines.txt' `
        "logcat -b crash -d -v threadtime; logcat -b all -d -v threadtime | grep -Ei 'eglCreateImage|EGL_BAD_ALLOC|valid texture|Fatal signal|SIGABRT|surfaceflinger|SetVideoFbmBufAddress|OMX.allwinner' | tail -n 8000"
    Save-Shell 'tombstones.txt' `
        'ls -la /data/tombstones 2>&1; for f in /data/tombstones/*; do test -f "$f" && stat "$f"; done 2>&1'
}

function Clear-LogcatExplicitly {
    if (-not $ClearLogcat) { return }
    if ($Phase -notin @('AVCPre', 'HEVCPre')) {
        throw '-ClearLogcat is allowed only after AVCPre or HEVCPre capture.'
    }
    $Answer = Read-Host "Type CLEAR-$Phase to clear logcat after the saved pre-window"
    if ($Answer -cne "CLEAR-$Phase") { throw 'Logcat clear cancelled.' }
    & $AdbExecutable -s $DeviceEndpoint logcat -b all -c
    if ($LASTEXITCODE -ne 0) { throw 'logcat clear failed' }
    Write-Utf8NoBom (Join-Path $CaptureRoot 'logcat-cleared.txt') `
        "phase=$Phase`ncleared_utc=$([DateTime]::UtcNow.ToString('o'))`npstore_cleared=false`ntombstones_cleared=false`n"
}

$Manifest = @"
candidate=$Candidate
candidate_sha256=$CandidateSha256
phase=$Phase
captured_utc=$([DateTime]::UtcNow.ToString('o'))
device_endpoint=$DeviceEndpoint
playback=MANUAL_SINGLE_FIXTURE
automatic_reboot=false
instrumentation=UBOX_R7_DIAG1,UBOX_R7_DIAG3
"@
Write-Utf8NoBom (Join-Path $CaptureRoot 'capture-manifest.txt') $Manifest

if ($Phase -eq 'HEVCPostRestart') { Wait-Adb }
elseif (-not (Test-Adb)) { throw 'ADB unavailable; no reboot was attempted.' }

switch ($Phase) {
    'BootGate' {
        Save-QuickState
        Write-Host 'Confirm normal full-screen boot before AVC. No playback was started.'
    }
    'AVCPre' {
        Save-QuickState
        Clear-LogcatExplicitly
        Write-Host 'Next run AVCLive in this terminal, then manually play AVC once from another control path.'
    }
    'AVCLive' {
        $Path = Join-Path $CaptureRoot 'avc-live-logcat-all.txt'
        Write-Host 'Live full logcat is running. Play AVC exactly once; stop with Ctrl+C after playback.'
        & $AdbExecutable -s $DeviceEndpoint logcat -b all -v threadtime 2>&1 | Tee-Object -FilePath $Path
    }
    'AVCPost' {
        Save-QuickState
        Write-Host 'Record visible AVC video/audio result, then proceed to HEVCPre.'
    }
    'HEVCPre' {
        Save-QuickState
        Clear-LogcatExplicitly
        Write-Host 'Next run HEVCLive, then manually start HEVC exactly once. Do not loop or reboot.'
    }
    'HEVCLive' {
        $Path = Join-Path $CaptureRoot 'hevc-live-logcat-all.txt'
        Write-Host 'Live full logcat is running on the PC. Start HEVC once; retain output through ADB loss/recovery.'
        & $AdbExecutable -s $DeviceEndpoint logcat -b all -v threadtime 2>&1 | Tee-Object -FilePath $Path
    }
    'HEVCPostRestart' {
        Save-QuickState
        $Pull = & $AdbExecutable -s $DeviceEndpoint pull /data/tombstones `
            (Join-Path $CaptureRoot 'tombstones') 2>&1 | Out-String
        Write-Utf8NoBom (Join-Path $CaptureRoot 'tombstone-pull.txt') $Pull
        Write-Host 'Post-recovery state captured. Do not clear logs or alter HDMI/wm state.'
    }
}
