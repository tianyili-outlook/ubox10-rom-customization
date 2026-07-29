[CmdletBinding()]
param(
    [string]$Device = "192.168.1.5:7896",
    [string]$OutputFile
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$adb = Join-Path $repo "tools/platform-tools/adb.exe"
$jdk = Join-Path $repo "work/remote-service-migration/toolchain/jdk17/jdk-17.0.19+10"
$androidJar = Join-Path $repo "work/remote-service-migration/toolchain/platform31/android-12/android.jar"
$d8Jar = Join-Path $repo "work/remote-service-migration/toolchain/build-tools31/android-12/lib/d8.jar"
$buildTools = Join-Path $repo "work/remote-service-migration/toolchain/build-tools31/android-12"
$sourceRoot = Join-Path $repo "tools/m8-drm-probe"
$manifest = Join-Path $sourceRoot "AndroidManifest.xml"
$testKey = Join-Path $repo "tools/testkey_rsa2048.pem"
$testCertificate = Join-Path $repo "assets/tv_remote_overlay/ubox10-test-overlay.x509.pem"
$openssl = "C:/Program Files/Git/usr/bin/openssl.exe"

foreach ($required in @(
    $adb,
    (Join-Path $jdk "bin/javac.exe"),
    (Join-Path $jdk "bin/java.exe"),
    (Join-Path $jdk "bin/jar.exe"),
    $androidJar,
    $d8Jar,
    (Join-Path $buildTools "aapt2.exe"),
    (Join-Path $buildTools "zipalign.exe"),
    (Join-Path $buildTools "lib/apksigner.jar"),
    $manifest,
    $testKey,
    $testCertificate,
    $openssl
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing required file: $required"
    }
}

$buildRoot = Join-Path $repo ("work/m8/drm-probe-" + [guid]::NewGuid().ToString("N"))
$classes = Join-Path $buildRoot "classes"
$dex = Join-Path $buildRoot "dex"
$unsignedApk = Join-Path $buildRoot "m8-drm-probe-unsigned.apk"
$alignedApk = Join-Path $buildRoot "m8-drm-probe-aligned.apk"
$probeApk = Join-Path $buildRoot "m8-drm-probe.apk"
$keyPk8 = Join-Path $buildRoot "testkey.pk8"
$packageName = "com.ubox10.m8.drmprobe"
$component = "$packageName/com.ubox10.m8.DrmProbeActivity"

New-Item -ItemType Directory -Path $classes, $dex -Force | Out-Null

try {
    $sources = @(
        Get-ChildItem -LiteralPath (Join-Path $sourceRoot "src") -Recurse -Filter *.java |
            ForEach-Object { $_.FullName }
    )
    & (Join-Path $jdk "bin/javac.exe") `
        -encoding UTF-8 `
        -source 8 `
        -target 8 `
        -Xlint:-options `
        -classpath $androidJar `
        -d $classes `
        @sources
    if ($LASTEXITCODE -ne 0) {
        throw "javac failed with exit code $LASTEXITCODE"
    }

    $classFiles = @(
        Get-ChildItem -LiteralPath $classes -Recurse -Filter *.class |
            ForEach-Object { $_.FullName }
    )
    & (Join-Path $jdk "bin/java.exe") `
        -cp $d8Jar `
        com.android.tools.r8.D8 `
        --min-api 31 `
        --lib $androidJar `
        --output $dex `
        @classFiles
    if ($LASTEXITCODE -ne 0) {
        throw "D8 failed with exit code $LASTEXITCODE"
    }

    & (Join-Path $buildTools "aapt2.exe") link `
        -o $unsignedApk `
        --manifest $manifest `
        -I $androidJar
    if ($LASTEXITCODE -ne 0) {
        throw "aapt2 link failed with exit code $LASTEXITCODE"
    }

    & (Join-Path $jdk "bin/jar.exe") uf $unsignedApk -C $dex classes.dex
    if ($LASTEXITCODE -ne 0) {
        throw "adding classes.dex failed with exit code $LASTEXITCODE"
    }

    & (Join-Path $buildTools "zipalign.exe") -f 4 $unsignedApk $alignedApk
    if ($LASTEXITCODE -ne 0) {
        throw "zipalign failed with exit code $LASTEXITCODE"
    }

    & $openssl pkcs8 -topk8 -nocrypt -in $testKey -outform DER -out $keyPk8
    if ($LASTEXITCODE -ne 0) {
        throw "test-key conversion failed with exit code $LASTEXITCODE"
    }

    & (Join-Path $jdk "bin/java.exe") `
        -jar (Join-Path $buildTools "lib/apksigner.jar") `
        sign `
        --key $keyPk8 `
        --cert $testCertificate `
        --out $probeApk `
        $alignedApk
    if ($LASTEXITCODE -ne 0) {
        throw "APK signing failed with exit code $LASTEXITCODE"
    }

    & $adb -s $Device get-state | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "ADB device is unavailable: $Device"
    }

    & $adb -s $Device install -r -t $probeApk | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "ADB install failed with exit code $LASTEXITCODE"
    }

    $runId = [guid]::NewGuid().ToString("N")
    & $adb -s $Device shell am start -W -n $component --es run_id $runId | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "DRM probe activity failed with exit code $LASTEXITCODE"
    }

    $rawLog = & $adb -s $Device logcat -d -v raw -s "M8DrmProbe:I" "*:S"
    $prefix = "$runId "
    $result = @(
        $rawLog |
            Where-Object { $_.StartsWith($prefix) } |
            ForEach-Object { $_.Substring($prefix.Length) }
    )
    if ($result -notcontains "complete=true") {
        throw "DRM probe did not emit a complete result"
    }

    $result | Write-Output
    if ($OutputFile) {
        $outputCandidate = if ([IO.Path]::IsPathRooted($OutputFile)) {
            $OutputFile
        } else {
            Join-Path $repo $OutputFile
        }
        $outputPath = [IO.Path]::GetFullPath($outputCandidate)
        $outputParent = Split-Path -Parent $outputPath
        New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
        $result | Set-Content -LiteralPath $outputPath -Encoding utf8
    }
} finally {
    & $adb -s $Device uninstall $packageName 2>$null | Out-Null
    if (Test-Path -LiteralPath $buildRoot) {
        Remove-Item -LiteralPath $buildRoot -Recurse -Force
    }
}
