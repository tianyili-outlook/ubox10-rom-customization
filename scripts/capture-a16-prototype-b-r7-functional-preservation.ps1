[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._:-]+$')]
    [string]$Device,

    [ValidateSet('Baseline', 'PostMedia', 'Remote', 'WifiPre', 'WifiPost', 'Final')]
    [string]$Phase = 'Baseline',

    [string]$OutputRoot,

    [string]$AdbExecutable,

    [switch]$NoConnect,

    [switch]$SelfTest
)

# Exact-r7 Gate 3 evidence collector for Windows PowerShell.
#
# Device-side commands are read-only. In particular, this script does not use
# root, remount, push, pull, install, persistent properties, settings writes or
# reboot. Wi-Fi OFF -> ON is deliberately performed through the physical TV UI:
# disabling Wi-Fi from a Wi-Fi ADB session would also remove the only command
# path available to re-enable it.
$ErrorActionPreference = 'Stop'

$Candidate = 'a16-prototype-b-r7'
$CandidateSha256 = 'A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27'

$ArchitectureCommands = [ordered]@{
    'android-identity.txt' = 'getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.build.id; getprop ro.build.version.security_patch; uname -r'
    'mixed-abi.txt' = 'getprop ro.zygote; getprop ro.product.cpu.abilist; getprop ro.product.cpu.abilist64; getprop ro.product.cpu.abilist32'
    'boot-services.txt' = 'getprop sys.boot_completed; getprop dev.bootcomplete; getprop init.svc.zygote; getprop init.svc.zygote_secondary; getprop init.svc.surfaceflinger'
    'process-topology.txt' = "ps -A -o USER,PID,PPID,NAME | grep -E 'zygote|surfaceflinger|system_server'"
    'graphics-properties.txt' = 'getprop ro.hardware.egl; getprop ro.board.platform'
    'surfaceflinger-summary.txt' = "dumpsys SurfaceFlinger | grep -E 'GLES:|EGL|Mali|Display|1920|1080' | head -n 240"
    'mapper-fatal-census.txt' = "logcat -b crash -d -v threadtime | grep -i 'gralloc-mapper'"
}

$CrashCommands = [ordered]@{
    'crash-buffer.txt' = 'logcat -b crash -d -v threadtime'
    'critical-restart-census.txt' = "logcat -d -v threadtime | grep -Ei 'Fatal signal|FATAL EXCEPTION|SIGSEGV|SIGABRT|zygote|system_server|surfaceflinger|mapper|gralloc|Mali|EGL|audioserver|android.hardware.audio.service|media.codec|media.extractor|wifi' | tail -n 3000"
}

$MediaCommands = [ordered]@{
    'media-processes.txt' = "ps -A -o USER,PID,PPID,NAME | grep -Ei 'media|codec|extractor|audio|cedar|omx'"
    'media-codec.txt' = 'dumpsys media.codec'
    'media-extractor.txt' = 'dumpsys media.extractor'
    'audioflinger.txt' = 'dumpsys media.audio_flinger'
    'audio-policy.txt' = 'dumpsys media.audio_policy'
    'surfaceflinger-layers.txt' = 'dumpsys SurfaceFlinger --list'
}

$InputCommands = [ordered]@{
    'input-devices.txt' = 'getevent -pl'
    'remote-linux-events.txt' = 'timeout 90 getevent -lt /dev/input/event0'
    'input-framework.txt' = 'dumpsys input'
    'input-log-census.txt' = "logcat -d -v threadtime | grep -Ei 'InputReader|InputDispatcher|scanCode|keyCode|DPAD|KEYCODE_' | tail -n 2000"
}

$NetworkCommands = [ordered]@{
    'wifi-basic.txt' = "getprop wlan.driver.status; cat /sys/class/net/wlan0/operstate; ip -4 addr show dev wlan0 | sed -E 's#inet [^ ]+#inet <REDACTED-IP>#g; s#link/ether [^ ]+#link/ether <REDACTED-MAC>#g'"
    'internet-ipv4.txt' = 'ping -c 4 8.8.8.8'
    'internet-dns.txt' = 'ping -c 4 www.google.com'
}

$PlatformCommands = [ordered]@{
    'data-package-settings.txt' = "if test -w /data; then echo DATA_WRITABLE; else echo DATA_NOT_WRITABLE; fi; cmd package list packages | wc -l; settings get global device_provisioned"
    'optional-fixtures.txt' = "cat /sys/class/net/eth0/carrier 2>/dev/null || echo ETHERNET_FIXTURE_UNAVAILABLE; sm list-volumes public"
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [AllowEmptyString()][Parameter(Mandatory = $true)][string]$Text
    )
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

function Protect-CaptureText {
    param([AllowEmptyString()][string]$Text)
    if ($null -eq $Text) { return '' }

    $protected = $Text.Replace([char]0, "`n")
    $protected = [regex]::Replace(
        $protected,
        '(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])',
        '<REDACTED-MAC>'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?i)((?<![A-Za-z0-9_])SSID\s*[:=]\s*)(?:"[^"\r\n]*"|[^\s,\r\n]+)',
        '$1<REDACTED-SSID>'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])',
        '<REDACTED-IP>'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?im)^([^\r\n]*(?:password|passwd|passphrase|psk|token|credential|secret)\s*[:=]\s*).+$',
        '$1<REDACTED-SECRET>'
    )
    return $protected
}

function Get-AllDeviceCommands {
    $commands = @()
    foreach ($group in @(
        $ArchitectureCommands,
        $CrashCommands,
        $MediaCommands,
        $InputCommands,
        $NetworkCommands,
        $PlatformCommands
    )) {
        $commands += @($group.Values)
    }
    return $commands
}

function Invoke-SafetySelfTest {
    $forbidden = @(
        '(?i)(^|[;&| ]+)setprop([;&| ]|$)',
        '(?i)(^|[;&| ]+)reboot([;&| ]|$)',
        '(?i)(^|[;&| ]+)remount([;&| ]|$)',
        '(?i)(^|[;&| ]+)su([;&| ]|$)',
        '(?i)settings\s+put',
        '(?i)svc\s+wifi',
        '(?i)pm\s+(?:grant|revoke|install|uninstall)',
        '(?i)(^|[;&| ]+)(?:mount|umount)([;&| ]|$)'
    )
    foreach ($command in Get-AllDeviceCommands) {
        foreach ($pattern in $forbidden) {
            if ($command -match $pattern) {
                throw "Gate 3 safety self-test rejected device command: $command"
            }
        }
    }

    $sample = 'SSID: __REDACTION_TEST_SSID__ 02:00:00:00:00:01 198.51.100.9 credential=__REDACTION_TEST_SECRET__'
    $protected = Protect-CaptureText -Text $sample
    foreach ($secret in @('__REDACTION_TEST_SSID__', '02:00:00:00:00:01', '198.51.100.9', '__REDACTION_TEST_SECRET__')) {
        if ($protected.Contains($secret)) {
            throw "Gate 3 redaction self-test failed: $secret"
        }
    }
    Write-Output 'R7 Gate 3 capture safety/redaction self-test: PASS'
}

if ($SelfTest) {
    Invoke-SafetySelfTest
    exit 0
}

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($AdbExecutable)) {
    $AdbPath = Join-Path $RepositoryRoot 'tools\platform-tools\adb.exe'
}
else {
    $AdbPath = $AdbExecutable
}
if (-not (Test-Path -LiteralPath $AdbPath -PathType Leaf)) {
    throw "ADB executable not found: $AdbPath"
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepositoryRoot 'logs\device\a16-prototype-b-r7-gate3'
}
$Timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$CaptureRoot = Join-Path $OutputRoot ("$Timestamp-$($Phase.ToLowerInvariant())")
New-Item -ItemType Directory -Path $CaptureRoot -Force | Out-Null

function Invoke-AdbCapture {
    param(
        [Parameter(Mandatory = $true)][string]$FileName,
        [Parameter(Mandatory = $true)][string]$Command
    )
    $output = & $AdbPath -s $Device shell $Command 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    $body = @"
candidate=$Candidate
candidate_sha256=$CandidateSha256
phase=$Phase
captured_utc=$([DateTime]::UtcNow.ToString('o'))
device_endpoint=<REDACTED>
command=$Command
exit_code=$exitCode

$(Protect-CaptureText -Text $output)
"@
    Write-Utf8NoBom -Path (Join-Path $CaptureRoot $FileName) -Text $body
}

function Invoke-CommandGroup {
    param([Parameter(Mandatory = $true)]$Group)
    foreach ($entry in $Group.GetEnumerator()) {
        Invoke-AdbCapture -FileName $entry.Key -Command $entry.Value
    }
}

if (-not $NoConnect) {
    & $AdbPath connect $Device | Out-Null
}
& $AdbPath -s $Device get-state | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'ADB device is unavailable. The endpoint is intentionally omitted from tracked evidence.'
}

$manualTemplate = @'
R7 GATE 3 MANUAL OBSERVATIONS

Use only PASS, FAIL, or NOT TESTED - FIXTURE UNAVAILABLE. Add a short observation and timestamp.

MEDIA
H.264 + AAC visible video: ______  audible HDMI audio: ______  hardware decode path proven: ______
HEVC/H.265 + AAC visible video: ______  audible HDMI audio: ______  hardware decode path proven: ______
VP9 visible video: ______  audible HDMI audio if present: ______  hardware decode path proven: ______

REMOTE KEY MATRIX
KEY       LINUX SCAN/KEY       ANDROID KEYCODE       FRAMEWORK/VISIBLE BEHAVIOR       RESULT
UP        ______               ______                __________________________       ______
DOWN      ______               ______                __________________________       ______
LEFT      ______               ______                __________________________       ______
RIGHT     ______               ______                __________________________       ______
OK        ______               ______                __________________________       ______
BACK      ______               ______                __________________________       ______
HOME      ______               ______                __________________________       ______
MENU      ______               ______                __________________________       ______
VOL+      ______               ______                __________________________       ______
VOL-      ______               ______                __________________________       ______
POWER     ______               ______                __________________________       ______

OPTIONAL FIXTURES
USB host/storage: ______
Ethernet: ______

KNOWN BASELINE DEBT SEEN (do not count as a new regression without timestamp proof): ______
NEW CRASH/RESTART AFTER USER ACTIONS: ______
'@
Write-Utf8NoBom -Path (Join-Path $CaptureRoot 'manual-observations.txt') -Text $manualTemplate

$manifest = @"
candidate=$Candidate
candidate_sha256=$CandidateSha256
phase=$Phase
captured_utc=$([DateTime]::UtcNow.ToString('o'))
device_endpoint=<REDACTED>
device_commands=ADB_READ_ONLY
wifi_lifecycle_control=PHYSICAL_TV_UI_ONLY
raw_outputs=SANITIZED_HOST_LOCAL_FILES
"@
Write-Utf8NoBom -Path (Join-Path $CaptureRoot 'capture-manifest.txt') -Text $manifest

switch ($Phase) {
    'Baseline' {
        Invoke-CommandGroup $ArchitectureCommands
        Invoke-CommandGroup $NetworkCommands
        Invoke-CommandGroup $PlatformCommands
        Invoke-CommandGroup $CrashCommands
    }
    'PostMedia' {
        Write-Host 'Play each known-good fixture manually and record visible/audible results in manual-observations.txt.'
        Invoke-CommandGroup $ArchitectureCommands
        Invoke-CommandGroup $MediaCommands
        Invoke-CommandGroup $CrashCommands
    }
    'Remote' {
        Write-Host 'Exercise UP/DOWN/LEFT/RIGHT/OK/BACK/HOME/MENU/VOL+/VOL-/POWER physically.'
        Write-Host 'Record Linux scan/key, Android keycode and visible behavior in manual-observations.txt.'
        Write-Host 'After Enter, a bounded 90-second Linux event capture starts; press the complete matrix then wait.'
        Read-Host 'Press Enter when ready to begin the physical key matrix' | Out-Null
        Invoke-CommandGroup $InputCommands
        Invoke-CommandGroup $CrashCommands
    }
    'WifiPre' {
        Invoke-CommandGroup $NetworkCommands
        Write-Host 'Next, use the physical TV UI/remote to turn Wi-Fi OFF and then ON.'
        Write-Host 'Wireless ADB loss is expected. Do not use this ADB session to disable Wi-Fi.'
        Write-Host 'After reassociation and ADB recovery, rerun this script with -Phase WifiPost.'
    }
    'WifiPost' {
        Invoke-CommandGroup $NetworkCommands
        Invoke-CommandGroup $CrashCommands
    }
    'Final' {
        Invoke-CommandGroup $ArchitectureCommands
        Invoke-CommandGroup $NetworkCommands
        Invoke-CommandGroup $PlatformCommands
        Invoke-CommandGroup $MediaCommands
        Invoke-CommandGroup $CrashCommands
    }
}

Write-Host "Gate 3 $Phase capture complete: $CaptureRoot"
