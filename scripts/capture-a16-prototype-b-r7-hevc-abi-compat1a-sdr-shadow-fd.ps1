[CmdletBinding()]
param(
    [ValidateSet(
        'BootGate', 'ReviewBootGate', 'PrepareMedia', 'ConfirmMediaReady',
        'AVCPre', 'AVCLive', 'AVCPost', 'ReviewAVC',
        'HEVCPre', 'HEVCLive', 'HEVCPost', 'ReviewHEVC',
        'InteractionPost', 'AVCRegressionPre', 'AVCRegressionLive',
        'AVCRegressionPost', 'Final'
    )]
    [string]$Phase = 'BootGate',

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$DeviceIp,

    [string]$AdbExecutable = 'C:\platform-tools\adb.exe',
    [string]$SessionRoot,
    [string]$VlcApk,
    [string]$AvcFixture,
    [string]$HevcFixture,
    [switch]$ConfirmBootGatePass,
    [switch]$ConfirmMediaReady,
    [switch]$ConfirmAvcPass,
    [switch]$ConfirmHevcPass,
    [switch]$ClearLogcat,
    [switch]$SelfTest
)

# PowerShell 7. Formal playback is manual only. The explicit PrepareMedia phase performs VLC's
# first activity launch, but never starts media or sends player input.
$ErrorActionPreference = 'Stop'
$Candidate = 'a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd'
$CandidateSha256 = '9E9592BF420F40A386BC347B027A85B2F9ED0A44DDB132BDBAB9882905F75722'
$DeviceMediaDirectory = '/sdcard/Movies/UBOX10-COMPAT1A'

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
        '(?im)\binput\s+keyevent\b'
    )) {
        if ($Source -match $Forbidden) { throw "unsafe automatic action: $Forbidden" }
    }
    $Boot = $Source.IndexOf("'BootGate'")
    $Prepare = $Source.IndexOf("'PrepareMedia'")
    $Avc = $Source.IndexOf("'AVCPre'")
    if ($Boot -lt 0 -or $Prepare -le $Boot -or $Avc -le $Prepare) {
        throw 'workflow order is not BootGate -> PrepareMedia -> AVCPre'
    }
    Write-Output 'R7 compat1a BootGate-first capture safety self-test: PASS'
}

if ($SelfTest) {
    Invoke-SafetySelfTest
    exit 0
}
if ([string]::IsNullOrWhiteSpace($DeviceIp)) {
    throw '-DeviceIp is required; pass the device current LAN IP explicitly.'
}
if (-not (Test-Path -LiteralPath $AdbExecutable -PathType Leaf)) {
    throw "ADB executable not found: $AdbExecutable"
}
$DeviceEndpoint = "${DeviceIp}:7896"

if ($Phase -eq 'BootGate') {
    if ([string]::IsNullOrWhiteSpace($SessionRoot)) {
        $Downloads = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
        $SessionRoot = Join-Path $Downloads (
            'UBOX10-compat1a-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
    }
    New-Item -ItemType Directory -Path $SessionRoot -Force | Out-Null
} else {
    if ([string]::IsNullOrWhiteSpace($SessionRoot) -or
        -not (Test-Path -LiteralPath $SessionRoot -PathType Container)) {
        throw 'Every phase after BootGate requires the exact existing -SessionRoot printed by BootGate.'
    }
}

$BootCaptured = Join-Path $SessionRoot 'STATE-BOOTGATE-CAPTURED.txt'
$BootPassed = Join-Path $SessionRoot 'STATE-BOOTGATE-REVIEWED-PASS.txt'
$MediaReady = Join-Path $SessionRoot 'STATE-MEDIA-READY.txt'
$AvcPreCaptured = Join-Path $SessionRoot 'STATE-AVC-PRE-CAPTURED.txt'
$AvcPostCaptured = Join-Path $SessionRoot 'STATE-AVC-POST-CAPTURED.txt'
$AvcPassed = Join-Path $SessionRoot 'STATE-AVC-REVIEWED-PASS.txt'
$HevcPreCaptured = Join-Path $SessionRoot 'STATE-HEVC-PRE-CAPTURED.txt'
$HevcPostCaptured = Join-Path $SessionRoot 'STATE-HEVC-POST-CAPTURED.txt'
$HevcPassed = Join-Path $SessionRoot 'STATE-HEVC-REVIEWED-PASS.txt'
$InteractionCaptured = Join-Path $SessionRoot 'STATE-INTERACTION-POST-CAPTURED.txt'
$AvcRegressionPreCaptured = Join-Path $SessionRoot 'STATE-AVC-REGRESSION-PRE-CAPTURED.txt'
$AvcRegressionPostCaptured = Join-Path $SessionRoot 'STATE-AVC-REGRESSION-POST-CAPTURED.txt'
$Timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$CaptureRoot = Join-Path $SessionRoot ("$Timestamp-$($Phase.ToLowerInvariant())")
New-Item -ItemType Directory -Path $CaptureRoot -Force | Out-Null

function Require-State {
    param([string]$Path, [string]$Message)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw $Message }
}

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
        'date; uptime; cat /proc/sys/kernel/random/boot_id; getprop ro.build.id; getprop ro.build.version.sdk; getprop ro.zygote; getprop ro.product.cpu.abilist; getprop ro.product.cpu.abilist32; getprop ro.product.cpu.abilist64; getprop sys.boot_completed; getprop init.svc.surfaceflinger; getprop init.svc.zygote; getprop init.svc.zygote64; getprop init.svc.vendor.gralloc-2-0; getprop init.svc.vendor.hwcomposer-2-2'
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
    if ((Read-Host "Type $Token to clear logcat after the saved pre-window") -cne $Token) {
        throw 'Logcat clear cancelled.'
    }
    & $AdbExecutable -s $DeviceEndpoint logcat -b all -c
    if ($LASTEXITCODE -ne 0) { throw 'logcat clear failed' }
    Write-Utf8NoBom (Join-Path $CaptureRoot 'logcat-cleared.txt') `
        "phase=$Phase`ncleared_utc=$([DateTime]::UtcNow.ToString('o'))`npstore_cleared=false`ntombstones_cleared=false`n"
}

function Save-LiveLog {
    param([string]$Name, [string]$Instruction)
    Write-Host $Instruction
    & $AdbExecutable -s $DeviceEndpoint logcat -b all -v threadtime 2>&1 |
        Tee-Object -FilePath (Join-Path $CaptureRoot $Name)
}

function Confirm-RemoteFileSize {
    param([string]$LocalPath, [string]$RemotePath, [string]$Label)
    $LocalSize = (Get-Item -LiteralPath $LocalPath).Length
    $RemoteSizeText = (& $AdbExecutable -s $DeviceEndpoint shell stat -c %s $RemotePath 2>&1 |
        Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $RemoteSizeText -notmatch '^\d+$') {
        throw "$Label remote size query failed: $RemoteSizeText"
    }
    $RemoteSize = [Int64]$RemoteSizeText
    if ($RemoteSize -ne $LocalSize) {
        throw "$Label transfer size mismatch: host=$LocalSize device=$RemoteSize"
    }
    return "$Label host_size=$LocalSize device_size=$RemoteSize remote=$RemotePath"
}

$Manifest = @"
candidate=$Candidate
candidate_sha256=$CandidateSha256
phase=$Phase
captured_utc=$([DateTime]::UtcNow.ToString('o'))
device_endpoint=$DeviceEndpoint
session_root=$SessionRoot
playback=MANUAL_ONLY
automatic_reboot=false
automatic_playback=false
unsupported_tests=Main10,HDR,AFBC,protected,4K
instrumentation=UBOX_R7_DIAG1,UBOX_R7_DIAG3,UBOX_R7_COMPAT1
workflow=BOOTGATE_FIRST_THEN_VLC_AND_MEDIA_PREP_THEN_FORMAL_VIDEO
"@
Write-Utf8NoBom (Join-Path $CaptureRoot 'capture-manifest.txt') $Manifest

if ($Phase -notin @('ReviewBootGate', 'ConfirmMediaReady', 'ReviewAVC', 'ReviewHEVC') -and
    -not (Test-Adb)) {
    throw 'ADB unavailable; no reboot was attempted.'
}

switch ($Phase) {
    'BootGate' {
        Save-QuickState
        Write-Utf8NoBom $BootCaptured "captured_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host "BootGate captured. SessionRoot: $SessionRoot"
        Write-Host 'STOP. Review BootGate. Do not install VLC, copy media, or play anything yet.'
    }
    'ReviewBootGate' {
        Require-State $BootCaptured 'BootGate has not been captured.'
        if (-not $ConfirmBootGatePass) { throw 'Review evidence, then pass -ConfirmBootGatePass.' }
        Write-Utf8NoBom $BootPassed "reviewed_pass_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'BootGate PASS recorded. PrepareMedia is now permitted.'
    }
    'PrepareMedia' {
        Require-State $BootPassed 'BootGate has not been explicitly reviewed PASS. STOP.'
        foreach ($Item in @($VlcApk, $AvcFixture, $HevcFixture)) {
            if ([string]::IsNullOrWhiteSpace($Item) -or -not (Test-Path -LiteralPath $Item -PathType Leaf)) {
                throw 'PrepareMedia requires valid -VlcApk, -AvcFixture, and -HevcFixture paths.'
            }
        }
        & $AdbExecutable -s $DeviceEndpoint install -r $VlcApk
        if ($LASTEXITCODE -ne 0) { throw 'VLC install failed.' }
        Save-Shell 'vlc-package.txt' 'pm path org.videolan.vlc; dumpsys package org.videolan.vlc | head -n 40'
        & $AdbExecutable -s $DeviceEndpoint shell mkdir -p $DeviceMediaDirectory
        & $AdbExecutable -s $DeviceEndpoint push $AvcFixture "$DeviceMediaDirectory/diag1a-avc-aac-1080p30.mp4"
        if ($LASTEXITCODE -ne 0) { throw 'AVC fixture transfer failed.' }
        & $AdbExecutable -s $DeviceEndpoint push $HevcFixture "$DeviceMediaDirectory/diag1a-hevc-aac-1080p30.mp4"
        if ($LASTEXITCODE -ne 0) { throw 'HEVC fixture transfer failed.' }
        $AvcSizeProof = Confirm-RemoteFileSize $AvcFixture `
            "$DeviceMediaDirectory/diag1a-avc-aac-1080p30.mp4" 'AVC'
        $HevcSizeProof = Confirm-RemoteFileSize $HevcFixture `
            "$DeviceMediaDirectory/diag1a-hevc-aac-1080p30.mp4" 'HEVC'
        Write-Utf8NoBom (Join-Path $CaptureRoot 'transfer-size-proof.txt') `
            "$AvcSizeProof`n$HevcSizeProof`n"
        Save-Shell 'transferred-media.txt' `
            "ls -ln $DeviceMediaDirectory; stat $DeviceMediaDirectory/diag1a-avc-aac-1080p30.mp4 $DeviceMediaDirectory/diag1a-hevc-aac-1080p30.mp4"
        & $AdbExecutable -s $DeviceEndpoint shell am start -n org.videolan.vlc/.StartActivity
        if ($LASTEXITCODE -ne 0) {
            throw 'VLC StartActivity failed. Use adb shell cmd package resolve-activity or monkey manually.'
        }
        Write-Host 'Complete VLC onboarding, permissions and media scan. Verify both files are visible.'
        Write-Host 'Do not play AVC or HEVC. Then run ConfirmMediaReady explicitly.'
    }
    'ConfirmMediaReady' {
        Require-State $BootPassed 'BootGate PASS token missing.'
        if (-not $ConfirmMediaReady) { throw 'Pass -ConfirmMediaReady only after VLC first-run setup and scan.' }
        Write-Utf8NoBom $MediaReady "confirmed_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'Media preparation confirmed. AVCPre is now permitted.'
    }
    'AVCPre' {
        Require-State $MediaReady 'VLC install/media transfer/first launch is not confirmed complete. STOP.'
        Save-QuickState; Clear-LogcatExplicitly
        Write-Utf8NoBom $AvcPreCaptured "captured_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'Run AVCLive, then manually play known-good AVC exactly once.'
    }
    'AVCLive' {
        Require-State $AvcPreCaptured 'AVCPre has not been captured. STOP.'
        Save-LiveLog 'avc-live-logcat-all.txt' 'Manually play AVC once; Ctrl+C after picture/audio completes.'
    }
    'AVCPost' {
        Require-State $AvcPreCaptured 'AVCPre has not been captured. STOP.'
        Save-QuickState
        Write-Utf8NoBom $AvcPostCaptured "captured_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'STOP. Review picture, HDMI audio, EGL, BackendTexture and restart evidence.'
    }
    'ReviewAVC' {
        Require-State $AvcPostCaptured 'AVCPost has not been captured. STOP.'
        if (-not $ConfirmAvcPass) { throw 'Pass -ConfirmAvcPass only after AVC review confirms PASS.' }
        Write-Utf8NoBom $AvcPassed "reviewed_pass_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'AVC PASS recorded. One HEVC test is now permitted.'
    }
    'HEVCPre' {
        Require-State $AvcPassed 'AVC has not been explicitly reviewed PASS. STOP.'
        Save-QuickState; Clear-LogcatExplicitly
        Write-Utf8NoBom $HevcPreCaptured "captured_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'Run HEVCLive; manually play exactly one authorized SDR YV12 HEVC fixture.'
    }
    'HEVCLive' {
        Require-State $HevcPreCaptured 'HEVCPre has not been captured. STOP.'
        Save-LiveLog 'hevc-live-logcat-all.txt' 'Manually play HEVC exactly once; Ctrl+C; never auto-repeat.'
    }
    'HEVCPost' {
        Require-State $HevcPreCaptured 'HEVCPre has not been captured. STOP.'
        Save-QuickState
        Write-Utf8NoBom $HevcPostCaptured "captured_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'STOP. Review shadow/view/EGL/BackendTexture and restart evidence. Do not repeat HEVC.'
    }
    'ReviewHEVC' {
        Require-State $HevcPostCaptured 'HEVCPost has not been captured. STOP.'
        if (-not $ConfirmHevcPass) { throw 'Pass -ConfirmHevcPass only after the single HEVC result is stable.' }
        Write-Utf8NoBom $HevcPassed "reviewed_pass_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'HEVC review PASS recorded. Interaction and AVC regression are now permitted.'
    }
    'InteractionPost' {
        Require-State $HevcPassed 'HEVC has not been reviewed stable. STOP.'
        Save-QuickState
        Write-Utf8NoBom $InteractionCaptured "captured_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'Capture after manual pause/resume/seek/back only.'
    }
    'AVCRegressionPre' {
        Require-State $HevcPassed 'HEVC review token missing.'
        Require-State $InteractionCaptured 'InteractionPost has not been captured. STOP.'
        Save-QuickState; Clear-LogcatExplicitly
        Write-Utf8NoBom $AvcRegressionPreCaptured "captured_utc=$([DateTime]::UtcNow.ToString('o'))`n"
        Write-Host 'Run AVCRegressionLive; manually replay AVC exactly once.'
    }
    'AVCRegressionLive' {
        Require-State $AvcRegressionPreCaptured 'AVCRegressionPre has not been captured. STOP.'
        Save-LiveLog 'avc-regression-live-logcat-all.txt' 'Manually replay AVC once; Ctrl+C after completion.'
    }
    'AVCRegressionPost' {
        Require-State $AvcRegressionPreCaptured 'AVCRegressionPre has not been captured. STOP.'
        Save-QuickState
        Write-Utf8NoBom $AvcRegressionPostCaptured "captured_utc=$([DateTime]::UtcNow.ToString('o'))`n"
    }
    'Final' {
        Require-State $AvcRegressionPostCaptured 'AVCRegressionPost has not been captured. STOP.'
        Save-QuickState
    }
}
