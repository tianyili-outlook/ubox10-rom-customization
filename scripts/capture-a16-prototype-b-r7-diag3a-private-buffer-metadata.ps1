[CmdletBinding()]
param(
    [ValidateSet('BootGate', 'AVCPre', 'AVCLive', 'AVCPost')]
    [string]$Phase = 'BootGate',

    [ValidatePattern('^[A-Za-z0-9._:\[\]-]+$')]
    [string]$DeviceEndpoint = '192.168.1.9:7896',

    [string]$AdbExecutable = 'C:\platform-tools\adb.exe',

    [string]$OutputRoot,

    [switch]$ClearLogcat,

    [switch]$SelfTest
)

# PowerShell 7. Playback is manual; diag3a stops after the AVC preservation gate.
$ErrorActionPreference = 'Stop'
$Candidate = 'a16-prototype-b-r7-diag3a-private-buffer-metadata'
$CandidateSha256 = '666099016529032EEB80A49BBDACF1BF4FDC86859D9538B84C8F9660D1F232D9'

function Write-Utf8NoBom {
    param([string]$Path, [AllowEmptyString()][string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

function Invoke-SafetySelfTest {
    $Source = Get-Content -LiteralPath $PSCommandPath -Raw
    foreach ($Forbidden in @(
        '(?im)^\s*&\s*\$AdbExecutable.*\breboot\b',
        '(?im)\bshell\s+(?:rm|setprop|settings\s+put|wm\s+size|mount|umount)\b',
        '(?im)^\s*(?:shutdown|poweroff|halt)(?:\s|$)'
    )) {
        if ($Source -match $Forbidden) { throw "unsafe command/phase pattern: $Forbidden" }
    }
    Write-Output 'R7-diag3a AVC-only capture safety self-test: PASS'
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
        'UBOX10-r7-diag3a-private-buffer-metadata'
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
        'date; uptime; cat /proc/sys/kernel/random/boot_id; getprop ro.build.id; getprop ro.build.version.sdk; getprop ro.zygote; getprop ro.product.cpu.abilist; getprop sys.boot_completed; getprop init.svc.surfaceflinger; getprop init.svc.zygote; getprop init.svc.vendor.gralloc-2-0; getprop init.svc.vendor.hwcomposer-2-2'
    Save-Shell 'processes.txt' `
        "ps -A -o USER,PID,PPID,ELAPSED,NAME | grep -E 'zygote|surfaceflinger|system_server|media|codec|OMX|audio'"
    Save-Shell 'diag-lines.txt' `
        "logcat -b all -d -v threadtime | grep -E 'UBOX_R7_DIAG1|UBOX_R7_DIAG3'"
    Save-Shell 'avc-regression-lines.txt' `
        "logcat -b all -d -v threadtime | grep -Ei 'ubsan: mul-overflow|CodecLooper|SIGABRT|CODEC_PRE_USE|CODEC_POST_FBD|OMX.allwinner.video.decoder.avc|Fatal signal' | tail -n 8000"
    Save-Shell 'crash-buffer.txt' 'logcat -b crash -d -v threadtime'
    Save-Shell 'tombstones.txt' `
        'ls -la /data/tombstones 2>&1; for f in /data/tombstones/*; do test -f "$f" && stat "$f"; done 2>&1'
}

function Clear-LogcatExplicitly {
    if (-not $ClearLogcat) { return }
    if ($Phase -ne 'AVCPre') { throw '-ClearLogcat is allowed only after the saved AVCPre window.' }
    $Answer = Read-Host 'Type CLEAR-AVCPre to clear logcat after the saved pre-window'
    if ($Answer -cne 'CLEAR-AVCPre') { throw 'Logcat clear cancelled.' }
    & $AdbExecutable -s $DeviceEndpoint logcat -b all -c
    if ($LASTEXITCODE -ne 0) { throw 'logcat clear failed' }
    Write-Utf8NoBom (Join-Path $CaptureRoot 'logcat-cleared.txt') `
        "phase=AVCPre`ncleared_utc=$([DateTime]::UtcNow.ToString('o'))`npstore_cleared=false`ntombstones_cleared=false`n"
}

$Manifest = @"
candidate=$Candidate
candidate_sha256=$CandidateSha256
phase=$Phase
captured_utc=$([DateTime]::UtcNow.ToString('o'))
device_endpoint=$DeviceEndpoint
playback=MANUAL_SINGLE_AVC_FIXTURE
automatic_reboot=false
hevc_authorized=false
instrumentation=UBOX_R7_DIAG1,UBOX_R7_DIAG3
"@
Write-Utf8NoBom (Join-Path $CaptureRoot 'capture-manifest.txt') $Manifest
if (-not (Test-Adb)) { throw 'ADB unavailable; no reboot was attempted.' }

switch ($Phase) {
    'BootGate' {
        Save-QuickState
        Write-Host 'Confirm normal full-screen boot. Do not start AVC until BootGate is accepted.'
    }
    'AVCPre' {
        Save-QuickState
        Clear-LogcatExplicitly
        Write-Host 'Next run AVCLive, then manually play the known-good AVC fixture exactly once.'
    }
    'AVCLive' {
        $Path = Join-Path $CaptureRoot 'avc-live-logcat-all.txt'
        Write-Host 'Live full logcat is running. Play AVC once; stop with Ctrl+C after playback.'
        & $AdbExecutable -s $DeviceEndpoint logcat -b all -v threadtime 2>&1 | Tee-Object -FilePath $Path
    }
    'AVCPost' {
        Save-QuickState
        Write-Host 'Record picture/audio result. STOP. Do not run HEVC until AVC preservation is reviewed.'
    }
}
