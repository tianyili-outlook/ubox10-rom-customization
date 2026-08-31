[CmdletBinding()]
param(
    [ValidateSet(
        'BootGate', 'AVCPre', 'AVCLive', 'AVCPost',
        'HEVCPre', 'HEVCLive', 'HEVCPost', 'InteractionPost',
        'AVCRegressionPre', 'AVCRegressionLive', 'AVCRegressionPost', 'Final'
    )]
    [string]$Phase = 'BootGate',

    [ValidatePattern('^[A-Za-z0-9._:\[\]-]+$')]
    [string]$DeviceEndpoint = '192.168.1.9:7896',

    [string]$AdbExecutable = 'C:\platform-tools\adb.exe',

    [string]$OutputRoot,

    [switch]$ClearLogcat,

    [switch]$SelfTest
)

# PowerShell 7. All playback and player interaction are manual and explicitly phased.
$ErrorActionPreference = 'Stop'
$Candidate = 'a16-prototype-b-r7-hevc-abi-compat1-sdr-shadow'
$CandidateSha256 = 'D4FAFE24FE2A743764DA50769FDBD8D6B6C7152646017C3C4F0B09C8FBBEFAAB'

function Write-Utf8NoBom {
    param([string]$Path, [AllowEmptyString()][string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

function Invoke-SafetySelfTest {
    $Source = Get-Content -LiteralPath $PSCommandPath -Raw
    foreach ($Forbidden in @(
        '(?im)^\s*&\s*\$AdbExecutable.*\breboot\b',
        '(?im)\bshell\s+(?:rm|setprop|settings\s+put|wm\s+size|mount|umount)\b',
        '(?im)^\s*(?:shutdown|poweroff|halt)(?:\s|$)',
        '(?im)\b(?:am\s+start|input\s+keyevent)\b'
    )) {
        if ($Source -match $Forbidden) { throw "unsafe automatic action: $Forbidden" }
    }
    Write-Output 'R7 compat1 AVC/HEVC capture safety self-test: PASS'
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
        'UBOX10-r7-hevc-abi-compat1-sdr-shadow'
}
$Timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$CaptureRoot = Join-Path $OutputRoot ("$Timestamp-$($Phase.ToLowerInvariant())")
New-Item -ItemType Directory -Path $CaptureRoot -Force | Out-Null

function Test-Adb {
    & $AdbExecutable connect $DeviceEndpoint | Out-Null
    & $AdbExecutable -s $DeviceEndpoint get-state 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Save-Shell {
    param([string]$Name, [string]$Command)
    $Text = & $AdbExecutable -s $DeviceEndpoint shell $Command 2>&1 | Out-String
    Write-Utf8NoBom (Join-Path $CaptureRoot $Name) $Text
}

function Save-QuickState {
    Save-Shell 'identity-uptime-services.txt' `
        'date; uptime; cat /proc/sys/kernel/random/boot_id; getprop ro.build.id; getprop ro.build.version.sdk; getprop ro.zygote; getprop ro.product.cpu.abilist; getprop ro.product.cpu.abilist32; getprop ro.product.cpu.abilist64; getprop sys.boot_completed; getprop init.svc.surfaceflinger; getprop init.svc.zygote; getprop init.svc.vendor.gralloc-2-0; getprop init.svc.vendor.hwcomposer-2-2'
    Save-Shell 'processes.txt' `
        "ps -A -o USER,PID,PPID,ELAPSED,NAME | grep -E 'zygote|surfaceflinger|system_server|media|codec|OMX|audio'"
    Save-Shell 'diagnostic-lines.txt' `
        "logcat -b all -d -v threadtime | grep -E 'UBOX_R7_DIAG1|UBOX_R7_DIAG3|UBOX_R7_COMPAT1'"
    Save-Shell 'media-render-failure-lines.txt' `
        "logcat -b all -d -v threadtime | grep -Ei 'OMX.allwinner|Cedar|CodecLooper|eglCreateImage|EGL_BAD_ALLOC|BackendTexture|Failed to create a valid texture|surfaceflinger|SIGABRT|Fatal signal' | tail -n 12000"
    Save-Shell 'crash-buffer.txt' 'logcat -b crash -d -v threadtime'
    Save-Shell 'tombstones.txt' `
        'ls -la /data/tombstones 2>&1; for f in /data/tombstones/*; do test -f "$f" && stat "$f"; done 2>&1'
}

function Clear-LogcatExplicitly {
    if (-not $ClearLogcat) { return }
    if ($Phase -notin @('AVCPre', 'HEVCPre', 'AVCRegressionPre')) {
        throw '-ClearLogcat is allowed only after a saved *Pre window.'
    }
    $Token = "CLEAR-$Phase"
    $Answer = Read-Host "Type $Token to clear logcat after the saved pre-window"
    if ($Answer -cne $Token) { throw 'Logcat clear cancelled.' }
    & $AdbExecutable -s $DeviceEndpoint logcat -b all -c
    if ($LASTEXITCODE -ne 0) { throw 'logcat clear failed' }
    Write-Utf8NoBom (Join-Path $CaptureRoot 'logcat-cleared.txt') `
        "phase=$Phase`ncleared_utc=$([DateTime]::UtcNow.ToString('o'))`npstore_cleared=false`ntombstones_cleared=false`n"
}

function Save-LiveLog {
    param([string]$Name, [string]$Instruction)
    $Path = Join-Path $CaptureRoot $Name
    Write-Host $Instruction
    & $AdbExecutable -s $DeviceEndpoint logcat -b all -v threadtime 2>&1 | Tee-Object -FilePath $Path
}

$Manifest = @"
candidate=$Candidate
candidate_sha256=$CandidateSha256
phase=$Phase
captured_utc=$([DateTime]::UtcNow.ToString('o'))
device_endpoint=$DeviceEndpoint
playback=MANUAL_ONLY
automatic_reboot=false
automatic_player_control=false
unsupported_tests=Main10,HDR,AFBC,protected,4K
instrumentation=UBOX_R7_DIAG1,UBOX_R7_DIAG3,UBOX_R7_COMPAT1
"@
Write-Utf8NoBom (Join-Path $CaptureRoot 'capture-manifest.txt') $Manifest
if (-not (Test-Adb)) { throw 'ADB unavailable; no reboot was attempted.' }

switch ($Phase) {
    'BootGate' {
        Save-QuickState
        Write-Host 'Confirm a normal full-screen boot before starting AVC.'
    }
    'AVCPre' {
        Save-QuickState
        Clear-LogcatExplicitly
        Write-Host 'Run AVCLive next, then manually play the known-good AVC fixture once.'
    }
    'AVCLive' {
        Save-LiveLog 'avc-live-logcat-all.txt' `
            'Play the known-good AVC fixture once. Stop capture with Ctrl+C after picture/audio completes.'
    }
    'AVCPost' {
        Save-QuickState
        Write-Host 'Record picture/audio. STOP and review AVC before authorizing HEVCPre.'
    }
    'HEVCPre' {
        Save-QuickState
        Clear-LogcatExplicitly
        Write-Host 'Only after AVC review: run HEVCLive and manually play one SDR YV12 HEVC fixture.'
    }
    'HEVCLive' {
        Save-LiveLog 'hevc-live-logcat-all.txt' `
            'Play exactly one authorized SDR YV12 HEVC fixture. Stop with Ctrl+C; do not test HDR/Main10/4K.'
    }
    'HEVCPost' {
        Save-QuickState
        Write-Host 'Verify compat1 markers, EGL import, BackendTexture, SurfaceFlinger and boot-id continuity.'
    }
    'InteractionPost' {
        Save-QuickState
        Write-Host 'After manual pause/resume/seek/back validation, preserve the resulting state here.'
    }
    'AVCRegressionPre' {
        Save-QuickState
        Clear-LogcatExplicitly
        Write-Host 'Run AVCRegressionLive next; manually replay the AVC control once.'
    }
    'AVCRegressionLive' {
        Save-LiveLog 'avc-regression-live-logcat-all.txt' `
            'Replay the known-good AVC fixture once. Stop capture with Ctrl+C after picture/audio completes.'
    }
    'AVCRegressionPost' {
        Save-QuickState
        Write-Host 'Record final AVC picture/audio regression result.'
    }
    'Final' {
        Save-QuickState
        Write-Host 'Capture complete. Upload all timestamped phase directories together.'
    }
}
