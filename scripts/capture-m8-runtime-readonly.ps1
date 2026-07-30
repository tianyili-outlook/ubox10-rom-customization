[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._:-]+$')]
    [string]$Device = '192.168.1.8:7896',

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$BaselineLabel = 'test8r2',

    [string]$OutputRoot,

    [string]$AdbExecutable,

    [ValidateRange(1, 65535)]
    [int]$AdbServerPort = 5037,

    [ValidateRange(5, 300)]
    [int]$DefaultTimeoutSeconds = 45,

    [switch]$NoConnect,

    [switch]$UserDataAppsPresent,

    [switch]$CompatibilityOnly,

    [switch]$SelfTest
)

# M8 read-only Android runtime collector.
#
# Device-side operations are limited to read-only property, file, mount and
# service inspection. The script does not use adb root/remount/push/pull/install,
# su, setprop, pm grant, settings put, or any filesystem write on the target.
$ErrorActionPreference = 'Stop'

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [AllowEmptyString()]
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    [System.IO.File]::WriteAllText(
        $Path,
        $Text,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Protect-CaptureText {
    param(
        [AllowEmptyString()]
        [string]$Text
    )

    if ($null -eq $Text) {
        return ''
    }

    $protected = $Text.Replace([char]0, "`n")

    # Network and account identifiers.
    $protected = [regex]::Replace(
        $protected,
        '(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])',
        '<REDACTED-MAC>'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?i)\b[A-Z0-9._%+-]+@[A-Z][A-Z0-9.-]*\.[A-Z]{2,}\b',
        '<REDACTED-EMAIL>'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?i)((?<![A-Za-z0-9_])SSID\s*[:=]\s*)(?:"[^"\r\n]*"|[^\s,\r\n]+)',
        '$1<REDACTED-SSID>'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?i)(\b(?:targetConfigKey|configKey)\s*=\s*)(?:"[^"\r\n]*"[^\s]*|[^\s,\r\n]+)',
        '$1<REDACTED-SSID-CONFIG>'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?i)(\b(?:WNS\s+candidate-|Connect\s+to\s+))"[^"\r\n]*"',
        '$1"<REDACTED-SSID>"'
    )
    $protected = [regex]::Replace(
        $protected,
        '"[^"\r\n]*"(?=\s*(?:WPA(?:2|3)?(?:_[A-Z0-9]+)?|SAE|OWE|WEP|<REDACTED-MAC>))',
        '"<REDACTED-SSID>"'
    )

    $ipv4Pattern = '(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])'
    $protected = [regex]::Replace(
        $protected,
        $ipv4Pattern,
        {
            param($match)
            if ($match.Value -in @('0.0.0.0', '127.0.0.1', '255.255.255.255')) {
                return $match.Value
            }
            return '<REDACTED-IP>'
        }
    )

    # Android/device identifiers. Public interface UUIDs such as the Widevine
    # scheme UUID are intentionally preserved.
    $protected = [regex]::Replace(
        $protected,
        '(?im)^(\s*\[(?:ro\.)?(?:boot\.)?serialno\]\s*:\s*)\[[^\]]*\](\s*)$',
        '$1[<REDACTED-SERIAL>]$2'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?im)^(\s*Serial\s*:\s*).+$',
        '$1<REDACTED-SERIAL>'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?im)^(\s*\[(?:net\.hostname|ro\.boot\.deviceid)\]\s*:\s*)\[[^\]]*\](\s*)$',
        '$1[<REDACTED-DEVICE-ID>]$2'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?im)^(\s*\[persist\.adb\.wifi\.guid\]\s*:\s*)\[[^\]]*\](\s*)$',
        '$1[<REDACTED-DEVICE-ID>]$2'
    )
    $protected = [regex]::Replace(
        $protected,
        '(?im)^([^\r\n]*(?:system\s*id|deviceuniqueid|android[_ ]?id|widevine[_ ]?id|esn)\s*[:=]\s*).+$',
        '$1<REDACTED-DEVICE-ID>'
    )

    # Credentials and session material. This is intentionally broad because
    # reports need component state, not credential values.
    $protected = [regex]::Replace(
        $protected,
        '(?im)^([^\r\n]*(?:password|passwd|passphrase|pre-shared.key|psk|token|cookie|credential|private.key|secret)\s*[:=]\s*).+$',
        '$1<REDACTED-SECRET>'
    )

    # Android's Bluetooth dump can embed a compressed BTSnoop payload even
    # when the surrounding output is described as a summary. Preserve only
    # the fact that the payload existed.
    $protected = [regex]::Replace(
        $protected,
        '(?is)--- BEGIN:BTSNOOP_LOG_SUMMARY[^\r\n]*---.*?--- END:BTSNOOP_LOG_SUMMARY ---',
        '--- BTSNOOP_LOG_SUMMARY: <REDACTED-BINARY-PAYLOAD> ---'
    )

    return $protected
}

function Invoke-RedactionSelfTest {
    $sample = @'
[ro.serialno]: [SERIAL-ABC-123]
[net.hostname]: [android-SERIAL-ABC-123]
[persist.adb.wifi.guid]: [adb-992304568773-EQ99mK]
Serial          : 0123456789abcdef
SSID: "Private Network", BSSID: aa:bb:cc:dd:ee:ff
targetConfigKey="Private Network"WPA_PSK BSSID=null
WNS candidate-"Private Network"
Connect to "Private Network" : aa:bb:cc:dd:ee:ff
0 "Private Network"WPA_PSK last=
address=192.168.1.55
listen=127.0.0.1
email=person@example.com
HAL=android.hardware.graphics.mapper@2.1-impl.so
password: correct-horse-battery-staple
System ID: 12345
scheme=edef8ba9-79d6-4ace-a3c8-27dcd51d21ed
--- BEGIN:BTSNOOP_LOG_SUMMARY (64 bytes in) ---
U2Vuc2l0aXZlIGJsdWV0b290aCB0cmFjZQ==
--- END:BTSNOOP_LOG_SUMMARY ---
'@

    $result = Protect-CaptureText -Text $sample
    $forbidden = @(
        'SERIAL-ABC-123',
        'adb-992304568773-EQ99mK',
        '0123456789abcdef',
        'Private Network',
        'aa:bb:cc:dd:ee:ff',
        '192.168.1.55',
        'person@example.com',
        'correct-horse-battery-staple',
        'System ID: 12345',
        'U2Vuc2l0aXZlIGJsdWV0b290aCB0cmFjZQ=='
    )
    foreach ($value in $forbidden) {
        if ($result.Contains($value)) {
            throw "Redaction self-test failed; value remained: $value"
        }
    }
    if (-not $result.Contains('127.0.0.1')) {
        throw 'Redaction self-test failed; loopback address should be preserved.'
    }
    if (-not $result.Contains('edef8ba9-79d6-4ace-a3c8-27dcd51d21ed')) {
        throw 'Redaction self-test failed; public DRM scheme UUID should be preserved.'
    }
    if (-not $result.Contains('android.hardware.graphics.mapper@2.1-impl.so')) {
        throw 'Redaction self-test failed; HAL filenames must not be treated as email addresses.'
    }

    Write-Output 'M8 runtime capture redaction self-test: PASS'
}

function ConvertTo-ArgumentLine {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $quoted = foreach ($argument in $Arguments) {
        if ($argument -match '[\s"]') {
            '"' + ($argument.Replace('\', '\\').Replace('"', '\"')) + '"'
        }
        else {
            $argument
        }
    }
    return ($quoted -join ' ')
}

function Invoke-AdbClient {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AdbPath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [ValidateRange(1, 600)]
        [int]$TimeoutSeconds = 30
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $AdbPath
    $startInfo.Arguments = ConvertTo-ArgumentLine -Arguments $Arguments
    $startInfo.WorkingDirectory = Split-Path -Parent $AdbPath
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw "Failed to start adb: $AdbPath"
    }

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $completed = $process.WaitForExit($TimeoutSeconds * 1000)
    $timedOut = -not $completed
    if ($timedOut) {
        try {
            $process.Kill()
        }
        catch {
            # The client may have exited between timeout detection and Kill().
        }
    }
    $process.WaitForExit()

    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result
    $exitCode = if ($timedOut) { -1 } else { $process.ExitCode }
    $process.Dispose()

    return [pscustomobject]@{
        ExitCode = $exitCode
        TimedOut = $timedOut
        Stdout = $stdout
        Stderr = $stderr
    }
}

if ($SelfTest) {
    Invoke-RedactionSelfTest
    exit 0
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($AdbExecutable)) {
    $adbPath = Join-Path $repositoryRoot 'tools\platform-tools\adb.exe'
}
elseif ([System.IO.Path]::IsPathRooted($AdbExecutable)) {
    $adbPath = [System.IO.Path]::GetFullPath($AdbExecutable)
}
else {
    $adbPath = [System.IO.Path]::GetFullPath(
        (Join-Path $repositoryRoot $AdbExecutable)
    )
}
if (-not (Test-Path -LiteralPath $adbPath -PathType Leaf)) {
    throw "adb.exe not found at the project-local path: $adbPath"
}
$adbClientPrefix = if ($AdbServerPort -eq 5037) {
    @()
}
else {
    @('-P', $AdbServerPort.ToString())
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repositoryRoot 'logs\device'
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $repositoryRoot $OutputRoot
}

if (-not $NoConnect -and $Device.Contains(':')) {
    $connectResult = Invoke-AdbClient `
        -AdbPath $adbPath `
        -Arguments ($adbClientPrefix + @('connect', $Device)) `
        -TimeoutSeconds 15
    if ($connectResult.ExitCode -ne 0) {
        throw "adb connect failed: $($connectResult.Stderr.Trim())"
    }
}

$stateResult = Invoke-AdbClient `
    -AdbPath $adbPath `
    -Arguments ($adbClientPrefix + @('-s', $Device, 'get-state')) `
    -TimeoutSeconds 10
if ($stateResult.ExitCode -ne 0 -or $stateResult.Stdout.Trim() -ne 'device') {
    throw "ADB device is not ready: $Device"
}

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$captureKind = if ($CompatibilityOnly) { 'compat' } else { 'runtime' }
$outputDir = Join-Path $OutputRoot "$runId-m8-$BaselineLabel-$captureKind"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$commands = @(
    [ordered]@{ Name = 'identity-id'; Category = 'identity'; Timeout = 10; Args = @('shell', 'id') },
    [ordered]@{ Name = 'identity-uname'; Category = 'identity'; Timeout = 10; Args = @('shell', 'uname', '-a') },
    [ordered]@{ Name = 'identity-getprop'; Category = 'identity'; Timeout = 15; Args = @('shell', 'getprop') },
    [ordered]@{ Name = 'identity-cpuinfo'; Category = 'identity'; Timeout = 10; Args = @('shell', 'cat', '/proc/cpuinfo') },
    [ordered]@{ Name = 'identity-meminfo'; Category = 'identity'; Timeout = 10; Args = @('shell', 'cat', '/proc/meminfo') },
    [ordered]@{ Name = 'identity-kernel-version'; Category = 'identity'; Timeout = 10; Args = @('shell', 'cat', '/proc/version') },
    [ordered]@{ Name = 'identity-kernel-cmdline'; Category = 'identity'; Timeout = 10; Args = @('shell', 'cat', '/proc/cmdline') },
    [ordered]@{ Name = 'identity-dtb-model'; Category = 'identity'; Timeout = 10; Args = @('shell', 'cat', '/proc/device-tree/model') },
    [ordered]@{ Name = 'identity-dtb-compatible'; Category = 'identity'; Timeout = 10; Args = @('shell', 'cat', '/proc/device-tree/compatible') },
    [ordered]@{ Name = 'hardware-regulator-names'; Category = 'identity'; Timeout = 10; Args = @('shell', 'grep', '-H', '.', '/sys/class/regulator/regulator.*/name') },
    [ordered]@{ Name = 'security-selinux'; Category = 'security'; Timeout = 10; Args = @('shell', 'getenforce') },

    [ordered]@{ Name = 'storage-partitions'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/proc/partitions') },
    [ordered]@{ Name = 'storage-df'; Category = 'storage'; Timeout = 15; Args = @('shell', 'df', '-h') },
    [ordered]@{ Name = 'storage-mount'; Category = 'storage'; Timeout = 15; Args = @('shell', 'mount') },
    [ordered]@{ Name = 'storage-by-name'; Category = 'storage'; Timeout = 10; Args = @('shell', 'ls', '-la', '/dev/block/by-name') },
    [ordered]@{ Name = 'storage-emmc-size'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/sys/block/mmcblk0/size') },
    [ordered]@{ Name = 'storage-emmc-name-0'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/sys/class/mmc_host/mmc0/mmc0:0001/name') },
    [ordered]@{ Name = 'storage-emmc-name-1'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/sys/class/mmc_host/mmc1/mmc1:0001/name') },
    [ordered]@{ Name = 'storage-emmc-type-0'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/sys/class/mmc_host/mmc0/mmc0:0001/type') },
    [ordered]@{ Name = 'storage-emmc-type-1'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/sys/class/mmc_host/mmc1/mmc1:0001/type') },
    [ordered]@{ Name = 'storage-emmc-manfid'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/sys/class/mmc_host/mmc0/mmc0:0001/manfid') },
    [ordered]@{ Name = 'storage-emmc-oemid'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/sys/class/mmc_host/mmc0/mmc0:0001/oemid') },
    [ordered]@{ Name = 'storage-emmc-revision'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/sys/class/mmc_host/mmc0/mmc0:0001/prv') },
    [ordered]@{ Name = 'storage-emmc-date'; Category = 'storage'; Timeout = 10; Args = @('shell', 'cat', '/sys/class/mmc_host/mmc0/mmc0:0001/date') },

    [ordered]@{ Name = 'runtime-processes'; Category = 'runtime'; Timeout = 15; Args = @('shell', 'ps', '-A', '-o', 'USER,PID,PPID,NAME') },
    [ordered]@{ Name = 'runtime-services'; Category = 'runtime'; Timeout = 20; Args = @('shell', 'service', 'list') },
    [ordered]@{ Name = 'runtime-dumpsys-services'; Category = 'runtime'; Timeout = 20; Args = @('shell', 'dumpsys', '-l') },
    [ordered]@{ Name = 'runtime-lshal'; Category = 'runtime'; Timeout = 30; Args = @('shell', 'lshal') },
    [ordered]@{ Name = 'runtime-kernel-modules'; Category = 'runtime'; Timeout = 10; Args = @('shell', 'cat', '/proc/modules') },
    [ordered]@{ Name = 'runtime-listeners'; Category = 'runtime'; Timeout = 15; Args = @('shell', 'ss', '-lntup') },

    [ordered]@{ Name = 'product-features'; Category = 'product'; Timeout = 15; Args = @('shell', 'pm', 'list', 'features') },
    [ordered]@{ Name = 'product-libraries'; Category = 'product'; Timeout = 15; Args = @('shell', 'pm', 'list', 'libraries') },
    [ordered]@{ Name = 'product-packages-system'; Category = 'product'; Timeout = 30; Args = @('shell', 'pm', 'list', 'packages', '-s', '-f') },
    [ordered]@{ Name = 'product-packages-user'; Category = 'product'; Timeout = 30; Args = @('shell', 'pm', 'list', 'packages', '-3', '-f') },
    [ordered]@{ Name = 'product-overlays'; Category = 'product'; Timeout = 20; Args = @('shell', 'cmd', 'overlay', 'list') },
    [ordered]@{ Name = 'product-tv-remote-overlay-path'; Category = 'product'; Timeout = 10; Args = @('shell', 'pm', 'path', 'com.ubox10.overlay.tvremote') },
    [ordered]@{ Name = 'product-tv-remote-service-path'; Category = 'product'; Timeout = 10; Args = @('shell', 'pm', 'path', 'com.google.android.tv.remote.service') },
    [ordered]@{ Name = 'product-tv-remote-provider'; Category = 'product'; Timeout = 10; Args = @('shell', 'cmd', 'overlay', 'lookup', 'android', 'android:string/config_tvRemoteServicePackage') },

    [ordered]@{ Name = 'vintf-locations'; Category = 'vintf'; Timeout = 20; Args = @('shell', 'find', '/vendor/etc/vintf', '/system/etc/vintf', '/system/system_ext/etc/vintf', '/product/etc/vintf', '-type', 'f', '-print') },
    [ordered]@{ Name = 'vintf-vendor-manifest'; Category = 'vintf'; Timeout = 10; Args = @('shell', 'cat', '/vendor/etc/vintf/manifest.xml') },
    [ordered]@{ Name = 'vintf-legacy-vendor-manifest'; Category = 'vintf'; Timeout = 10; Args = @('shell', 'cat', '/vendor/manifest.xml') },
    [ordered]@{ Name = 'vintf-system-manifest'; Category = 'vintf'; Timeout = 10; Args = @('shell', 'cat', '/system/etc/vintf/manifest.xml') },
    [ordered]@{ Name = 'vintf-product-manifest'; Category = 'vintf'; Timeout = 10; Args = @('shell', 'cat', '/product/etc/vintf/manifest.xml') },

    [ordered]@{ Name = 'graphics-library-roots'; Category = 'graphics'; Timeout = 15; Args = @('shell', 'ls', '-ld', '/system/lib', '/system/lib64', '/vendor/lib', '/vendor/lib64') },
    [ordered]@{ Name = 'graphics-egl-files'; Category = 'graphics'; Timeout = 15; Args = @('shell', 'ls', '-la', '/vendor/lib/egl') },
    [ordered]@{ Name = 'graphics-hal-files'; Category = 'graphics'; Timeout = 20; Args = @('shell', 'ls', '-la', '/vendor/lib/hw') },
    [ordered]@{ Name = 'graphics-hal-services'; Category = 'graphics'; Timeout = 20; Args = @('shell', 'ls', '-la', '/vendor/bin/hw') },
    [ordered]@{ Name = 'graphics-surfaceflinger'; Category = 'graphics'; Timeout = 90; Args = @('shell', 'dumpsys', 'SurfaceFlinger') },
    [ordered]@{ Name = 'graphics-display'; Category = 'graphics'; Timeout = 60; Args = @('shell', 'dumpsys', 'display') },

    [ordered]@{ Name = 'media-codec'; Category = 'media'; Timeout = 90; Args = @('shell', 'dumpsys', 'media.codec') },
    [ordered]@{ Name = 'media-extractor'; Category = 'media'; Timeout = 60; Args = @('shell', 'dumpsys', 'media.extractor') },
    [ordered]@{ Name = 'media-player'; Category = 'media'; Timeout = 60; Args = @('shell', 'dumpsys', 'media.player') },
    [ordered]@{ Name = 'media-audio-flinger'; Category = 'media'; Timeout = 60; Args = @('shell', 'dumpsys', 'media.audio_flinger') },
    [ordered]@{ Name = 'media-audio-policy'; Category = 'media'; Timeout = 60; Args = @('shell', 'dumpsys', 'media.audio_policy') },

    [ordered]@{ Name = 'wireless-wifi'; Category = 'wireless'; Timeout = 90; Args = @('shell', 'dumpsys', 'wifi') },
    [ordered]@{ Name = 'wireless-bluetooth'; Category = 'wireless'; Timeout = 90; Args = @('shell', 'dumpsys', 'bluetooth_manager') },
    [ordered]@{ Name = 'input'; Category = 'input'; Timeout = 60; Args = @('shell', 'dumpsys', 'input') },
    [ordered]@{ Name = 'power'; Category = 'power'; Timeout = 60; Args = @('shell', 'dumpsys', 'power') },
    [ordered]@{ Name = 'hdmi-control'; Category = 'display'; Timeout = 60; Args = @('shell', 'dumpsys', 'hdmi_control') },

    [ordered]@{ Name = 'drm-media'; Category = 'drm'; Timeout = 60; Args = @('shell', 'dumpsys', 'media.drm') },
    [ordered]@{ Name = 'drm-manager'; Category = 'drm'; Timeout = 60; Args = @('shell', 'dumpsys', 'drm.drmManager') },
    [ordered]@{ Name = 'drm-plugin-files'; Category = 'drm'; Timeout = 15; Args = @('shell', 'ls', '-la', '/vendor/lib/mediadrm') },
    [ordered]@{ Name = 'drm-optee-files'; Category = 'drm'; Timeout = 15; Args = @('shell', 'ls', '-la', '/vendor/lib/optee_armtz') },

    [ordered]@{ Name = 'modules-load'; Category = 'modules'; Timeout = 10; Args = @('shell', 'cat', '/vendor_dlkm/lib/modules/modules.load') },
    [ordered]@{ Name = 'modules-dep'; Category = 'modules'; Timeout = 15; Args = @('shell', 'cat', '/vendor_dlkm/lib/modules/modules.dep') },
    [ordered]@{ Name = 'modules-alias'; Category = 'modules'; Timeout = 15; Args = @('shell', 'cat', '/vendor_dlkm/lib/modules/modules.alias') },
    [ordered]@{ Name = 'modules-options'; Category = 'modules'; Timeout = 15; Args = @('shell', 'cat', '/vendor_dlkm/lib/modules/modules.options') }
)

$compatibilityCommands = @(
    [ordered]@{ Name = 'compat-identity-sdk'; Category = 'compat'; Timeout = 10; Args = @('shell', 'getprop', 'ro.build.version.sdk') },
    [ordered]@{ Name = 'compat-identity-abi'; Category = 'compat'; Timeout = 10; Args = @('shell', 'getprop', 'ro.product.cpu.abilist') },
    [ordered]@{ Name = 'compat-identity-fingerprint'; Category = 'compat'; Timeout = 10; Args = @('shell', 'getprop', 'ro.build.fingerprint') },

    [ordered]@{ Name = 'compat-linkerconfig-files'; Category = 'compat'; Timeout = 15; Args = @('shell', 'find', '/linkerconfig', '-type', 'f', '-print') },
    [ordered]@{
        Name = 'compat-linkerconfig-content'
        Category = 'compat'
        Timeout = 30
        Args = @(
            'shell',
            'for f in $(find /linkerconfig -type f); do echo; echo ===== $f =====; cat $f; echo; done'
        )
    },

    [ordered]@{ Name = 'compat-apex-info-list'; Category = 'compat'; Timeout = 15; Args = @('shell', 'cat', '/apex/apex-info-list.xml') },
    [ordered]@{ Name = 'compat-apexservice-active'; Category = 'compat'; Timeout = 15; Args = @('shell', 'cmd', 'apexservice', 'list', '--active') },
    [ordered]@{
        Name = 'compat-apex-mounts'
        Category = 'compat'
        Timeout = 15
        Args = @('shell', 'mount | grep " /apex/"')
    },

    [ordered]@{ Name = 'compat-bootclasspath'; Category = 'compat'; Timeout = 10; Args = @('shell', 'printenv', 'BOOTCLASSPATH') },
    [ordered]@{ Name = 'compat-systemserverclasspath'; Category = 'compat'; Timeout = 10; Args = @('shell', 'printenv', 'SYSTEMSERVERCLASSPATH') },
    [ordered]@{ Name = 'compat-dex2oatbootclasspath'; Category = 'compat'; Timeout = 10; Args = @('shell', 'printenv', 'DEX2OATBOOTCLASSPATH') },
    [ordered]@{ Name = 'compat-init-environ'; Category = 'compat'; Timeout = 15; Args = @('shell', 'cat', '/init.environ.rc') },

    [ordered]@{ Name = 'compat-shared-libraries'; Category = 'compat'; Timeout = 20; Args = @('shell', 'dumpsys', 'package', 'libraries') },
    [ordered]@{ Name = 'compat-package-uses-libraries'; Category = 'compat'; Timeout = 45; Args = @('shell', 'dumpsys', 'package', 'packages') },

    [ordered]@{
        Name = 'compat-vintf-files'
        Category = 'compat'
        Timeout = 20
        Args = @(
            'shell',
            'find',
            '/vendor/etc/vintf',
            '/system/etc/vintf',
            '/system/system_ext/etc/vintf',
            '/product/etc/vintf',
            '-type',
            'f',
            '-print'
        )
    },
    [ordered]@{
        Name = 'compat-vintf-content'
        Category = 'compat'
        Timeout = 30
        Args = @(
            'shell',
            'for d in /vendor/etc/vintf /system/etc/vintf /system/system_ext/etc/vintf /product/etc/vintf; do for f in $(find $d -type f 2>/dev/null); do echo; echo ===== $f =====; cat $f; echo; done; done'
        )
    },
    [ordered]@{ Name = 'compat-checkvintf-path'; Category = 'compat'; Timeout = 10; Args = @('shell', 'which', 'checkvintf') },
    [ordered]@{ Name = 'compat-checkvintf'; Category = 'compat'; Timeout = 20; Args = @('shell', 'checkvintf', '--check-compat') }
)

if ($CompatibilityOnly) {
    $commands = $compatibilityCommands
}
else {
    $commands += $compatibilityCommands
}

$results = [System.Collections.Generic.List[object]]::new()
$startedAt = Get-Date

foreach ($command in $commands) {
    $timeout = if ($command.Timeout) {
        [int]$command.Timeout
    }
    else {
        $DefaultTimeoutSeconds
    }
    $arguments = $adbClientPrefix + @('-s', $Device) + @($command.Args)

    Write-Output ("[{0}] {1}" -f $command.Category, $command.Name)
    $started = Get-Date
    $commandResult = Invoke-AdbClient `
        -AdbPath $adbPath `
        -Arguments $arguments `
        -TimeoutSeconds $timeout
    $ended = Get-Date

    $combined = $commandResult.Stdout
    if (-not [string]::IsNullOrWhiteSpace($commandResult.Stderr)) {
        if (-not [string]::IsNullOrWhiteSpace($combined)) {
            $combined += "`n"
        }
        $combined += "[stderr]`n$($commandResult.Stderr)"
    }
    if ($commandResult.TimedOut) {
        $combined += "`n[capture] command timed out after $timeout seconds"
    }

    $protectedText = Protect-CaptureText -Text $combined
    $outputPath = Join-Path $outputDir "$($command.Name).txt"
    Write-Utf8NoBom -Path $outputPath -Text $protectedText

    $results.Add([ordered]@{
        Name = $command.Name
        Category = $command.Category
        DeviceArguments = @($command.Args)
        ExitCode = $commandResult.ExitCode
        TimedOut = $commandResult.TimedOut
        StartedAt = $started.ToString('o')
        EndedAt = $ended.ToString('o')
        DurationSeconds = [Math]::Round(($ended - $started).TotalSeconds, 3)
        OutputFile = Split-Path -Leaf $outputPath
        OutputBytes = (Get-Item -LiteralPath $outputPath).Length
    })
}

$endedAt = Get-Date
$manifest = [ordered]@{
    SchemaVersion = 1
    Collector = 'scripts/capture-m8-runtime-readonly.ps1'
    ReadOnlyContract = $true
    BaselineLabel = $BaselineLabel
    CaptureKind = $captureKind
    UserDataAppsPresent = [bool]$UserDataAppsPresent
    EndpointKind = if ($Device.Contains(':')) { 'tcp' } else { 'local-or-usb' }
    StartedAt = $startedAt.ToString('o')
    EndedAt = $endedAt.ToString('o')
    DurationSeconds = [Math]::Round(($endedAt - $startedAt).TotalSeconds, 3)
    Host = [ordered]@{
        PowerShellVersion = $PSVersionTable.PSVersion.ToString()
        AdbVersion = (Get-Item -LiteralPath $adbPath).VersionInfo.FileVersion
        AdbServerPort = $AdbServerPort
    }
    Privacy = [ordered]@{
        SanitizedBeforeWrite = $true
        RawOutputRetained = $false
        RedactedClasses = @(
            'MAC/BSSID',
            'non-loopback IPv4 address',
            'SSID',
            'email address',
            'device serial/Android ID/System ID/ESN',
            'password/PSK/token/cookie/credential/secret'
        )
    }
    Commands = $results
}

$manifestPath = Join-Path $outputDir 'capture-manifest.json'
$manifestJson = $manifest | ConvertTo-Json -Depth 8
Write-Utf8NoBom -Path $manifestPath -Text $manifestJson

$failed = @($results | Where-Object { $_.ExitCode -ne 0 }).Count
$timedOut = @($results | Where-Object { $_.TimedOut }).Count

Write-Output ''
Write-Output "Sanitized M8 runtime evidence written to: $outputDir"
Write-Output "Commands: $($results.Count); non-zero: $failed; timed out: $timedOut"
Write-Output 'No raw device output was retained.'
