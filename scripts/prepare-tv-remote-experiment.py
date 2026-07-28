#!/usr/bin/env python3
"""Prepare the non-redistributable inputs for the TV Remote Service experiment.

The script intentionally does not download Google's APK. It verifies a
user-supplied, original-signed donor, builds the Apache-2.0 AOSP compatibility
library from locked Android 12 source archives, builds a one-resource framework
RRO, and stages all generated/proprietary inputs under ignored ``work/`` paths.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile


REPO = Path(__file__).resolve().parents[1]
MIGRATION_WORK = REPO / "work" / "remote-service-migration"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

REMOTE_APK_PACKAGE = "com.google.android.tv.remote.service"
REMOTE_APK_VERSION_CODE = "95855272"
REMOTE_APK_VERSION_NAME = "5.2.473254133"
REMOTE_APK_SHA256 = "9D1B5C5EF0E293F8ED17C26E8F62DE661ACC7F2DDC2AAA8EF23E4CABE430B973"
REMOTE_APK_CERT_SHA256 = "456EDBC33222D20FF158D42E9FAB0252DBE0514D6E1C39588D6B1982CC189137"

TVREMOTE_ARCHIVE_SHA256 = (
    "DE5B0404ADDC23C1B373810E448C381724D50D16BC2AE4816415998B701B51C6"
)
MEDIA_TV_ARCHIVE_SHA256 = (
    "CE355B15F1C3DD11B92AAD35AE03FE229AD01C67C3A4C56E13F53FE534A1465C"
)
OVERLAY_TEST_KEY_SHA256 = (
    "F1D5765A2BDFB92FB08AEE021107C7AC1A7A3F590DAFD853771C85375EF0FBD7"
)
OVERLAY_CERTIFICATE_SHA256 = (
    "D8634FDD59ED237F89F2ADA435B99B66B52A23A90C13F1BE8721B52E8E3CEDE0"
)

TVREMOTE_JAVA_MEMBER = (
    "java/com/android/media/tv/remoteprovider/TvRemoteProvider.java"
)
MEDIA_TV_AIDL_MEMBERS = (
    "ITvRemoteProvider.aidl",
    "ITvRemoteServiceInput.aidl",
)

SOURCE_STUBS = {
    "android/annotation/FloatRange.java": """\
package android.annotation;
import java.lang.annotation.*;
@Retention(RetentionPolicy.SOURCE)
@Target({ElementType.FIELD, ElementType.METHOD, ElementType.PARAMETER, ElementType.TYPE_USE})
public @interface FloatRange {
    double from() default Double.NEGATIVE_INFINITY;
    double to() default Double.POSITIVE_INFINITY;
    boolean fromInclusive() default true;
    boolean toInclusive() default true;
}
""",
    "android/annotation/NonNull.java": """\
package android.annotation;
import java.lang.annotation.*;
@Retention(RetentionPolicy.SOURCE)
@Target({ElementType.FIELD, ElementType.METHOD, ElementType.PARAMETER,
         ElementType.LOCAL_VARIABLE, ElementType.TYPE_USE})
public @interface NonNull {}
""",
    "android/annotation/SuppressAutoDoc.java": """\
package android.annotation;
import java.lang.annotation.*;
@Retention(RetentionPolicy.SOURCE)
@Target({ElementType.METHOD, ElementType.TYPE})
public @interface SuppressAutoDoc {}
""",
    "android/compat/annotation/UnsupportedAppUsage.java": """\
package android.compat.annotation;
import java.lang.annotation.*;
@Retention(RetentionPolicy.SOURCE)
@Target({ElementType.CONSTRUCTOR, ElementType.FIELD, ElementType.METHOD, ElementType.TYPE})
public @interface UnsupportedAppUsage {
    String overrideSourcePosition() default "";
}
""",
    "android/support/annotation/IntDef.java": """\
package android.support.annotation;
import java.lang.annotation.*;
@Retention(RetentionPolicy.SOURCE)
@Target({ElementType.ANNOTATION_TYPE, ElementType.FIELD, ElementType.METHOD,
         ElementType.PARAMETER, ElementType.TYPE_USE})
public @interface IntDef {
    long[] value() default {};
    boolean flag() default false;
    String[] prefix() default {};
}
""",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise RuntimeError(f"{label} is missing: {resolved}")
    return resolved


def require_hash(path: Path, expected: str, label: str) -> None:
    observed = sha256(path)
    if observed != expected:
        raise RuntimeError(
            f"{label} SHA-256 mismatch: {observed}; expected {expected}"
        )


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    show_output: bool = True,
) -> str:
    print("+", subprocess.list2cmdline(command))
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    output = (completed.stdout + completed.stderr).strip()
    if output and show_output:
        print(output)
    if completed.returncode:
        raise RuntimeError(
            f"command failed with exit code {completed.returncode}: "
            f"{subprocess.list2cmdline(command)}"
        )
    return output


def read_tar_member(archive: Path, member_name: str) -> bytes:
    with tarfile.open(archive, "r:gz") as source:
        try:
            member = source.getmember(member_name)
        except KeyError as exc:
            raise RuntimeError(
                f"locked source member is missing from {archive}: {member_name}"
            ) from exc
        if not member.isfile():
            raise RuntimeError(f"locked source member is not a file: {member_name}")
        stream = source.extractfile(member)
        if stream is None:
            raise RuntimeError(f"cannot read locked source member: {member_name}")
        return stream.read()


def write_source(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8", newline="\n")


def publish_file(source: Path, destination: Path) -> None:
    """Atomically replace one ignored local build input."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".publishing")
    shutil.copy2(source, temporary)
    temporary.replace(destination)


def read_uleb128(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(5):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    raise RuntimeError("invalid DEX ULEB128 value")


def dex_class_descriptors(path: Path) -> set[str]:
    """Return class descriptors from a DEX class_defs table."""

    data = path.read_bytes()
    if len(data) < 0x70 or not data.startswith(b"dex\n"):
        raise RuntimeError("D8 output is not a valid DEX file")
    string_ids_size, string_ids_off = struct.unpack_from("<II", data, 0x38)
    type_ids_size, type_ids_off = struct.unpack_from("<II", data, 0x40)
    class_defs_size, class_defs_off = struct.unpack_from("<II", data, 0x60)
    if (
        string_ids_off + string_ids_size * 4 > len(data)
        or type_ids_off + type_ids_size * 4 > len(data)
        or class_defs_off + class_defs_size * 32 > len(data)
    ):
        raise RuntimeError("DEX index table exceeds file bounds")

    descriptors: set[str] = set()
    for class_number in range(class_defs_size):
        class_idx = struct.unpack_from(
            "<I", data, class_defs_off + class_number * 32
        )[0]
        if class_idx >= type_ids_size:
            raise RuntimeError("DEX class_idx exceeds type_ids table")
        descriptor_idx = struct.unpack_from(
            "<I", data, type_ids_off + class_idx * 4
        )[0]
        if descriptor_idx >= string_ids_size:
            raise RuntimeError("DEX descriptor_idx exceeds string_ids table")
        string_data_off = struct.unpack_from(
            "<I", data, string_ids_off + descriptor_idx * 4
        )[0]
        _, text_offset = read_uleb128(data, string_data_off)
        terminator = data.find(b"\x00", text_offset)
        if terminator < 0:
            raise RuntimeError("unterminated DEX descriptor string")
        descriptors.add(data[text_offset:terminator].decode("ascii"))
    return descriptors


def verify_remote_apk(
    apk: Path,
    *,
    java: Path,
    apksigner_jar: Path,
    aapt2: Path,
) -> None:
    require_hash(apk, REMOTE_APK_SHA256, "Android TV Remote Service donor")
    certificates = run(
        [
            str(java),
            "-jar",
            str(apksigner_jar),
            "verify",
            "--verbose",
            "--print-certs",
            str(apk),
        ],
        show_output=False,
    )
    normalized_certificates = certificates.replace(":", "").upper()
    if REMOTE_APK_CERT_SHA256 not in normalized_certificates:
        raise RuntimeError(
            "Android TV Remote Service donor certificate SHA-256 does not match "
            "the locked Google certificate"
        )
    badging = run(
        [str(aapt2), "dump", "badging", str(apk)],
        show_output=False,
    )
    identity = re.search(
        r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'",
        badging,
    )
    expected = (
        REMOTE_APK_PACKAGE,
        REMOTE_APK_VERSION_CODE,
        REMOTE_APK_VERSION_NAME,
    )
    if identity is None or identity.groups() != expected:
        observed = identity.groups() if identity else None
        raise RuntimeError(
            f"Android TV Remote Service identity mismatch: {observed}; "
            f"expected {expected}"
        )


def build_remoteprovider_jar(
    *,
    tvremote_archive: Path,
    media_tv_archive: Path,
    java: Path,
    javac: Path,
    aidl: Path,
    d8_jar: Path,
    android_jar: Path,
    core_lambda_stubs: Path,
    build_root: Path,
    output: Path,
) -> None:
    require_hash(tvremote_archive, TVREMOTE_ARCHIVE_SHA256, "AOSP tvremote archive")
    require_hash(media_tv_archive, MEDIA_TV_ARCHIVE_SHA256, "AOSP media/tv archive")

    source_root = build_root / "src"
    generated_root = build_root / "generated"
    classes_root = build_root / "classes"
    dex_root = build_root / "dex"
    source_root.mkdir(parents=True)
    generated_root.mkdir()
    classes_root.mkdir()
    dex_root.mkdir()

    # Keep classpath jars inside the ASCII-only temporary build tree. The
    # generated class set and final DEX are validated below rather than trusted
    # solely from compiler output.
    build_android_jar = build_root / "android.jar"
    build_core_lambda_stubs = build_root / "core-lambda-stubs.jar"
    shutil.copy2(android_jar, build_android_jar)
    shutil.copy2(core_lambda_stubs, build_core_lambda_stubs)

    provider_source = (
        source_root
        / "com"
        / "android"
        / "media"
        / "tv"
        / "remoteprovider"
        / "TvRemoteProvider.java"
    )
    write_source(
        provider_source,
        read_tar_member(tvremote_archive, TVREMOTE_JAVA_MEMBER),
    )
    for member_name in MEDIA_TV_AIDL_MEMBERS:
        write_source(
            source_root / "android" / "media" / "tv" / member_name,
            read_tar_member(media_tv_archive, member_name),
        )
    for relative, contents in SOURCE_STUBS.items():
        write_source(source_root / relative, contents)

    # Relative inputs keep generated @UnsupportedAppUsage source positions
    # host-independent and avoid embedding Windows paths in class files.
    aidl_inputs = [
        f"android/media/tv/{member}" for member in MEDIA_TV_AIDL_MEMBERS
    ]
    run(
        [
            str(aidl),
            "--lang=java",
            "-I",
            ".",
            "-o",
            str(generated_root),
            *aidl_inputs,
        ],
        cwd=source_root,
    )

    java_sources = sorted(source_root.rglob("*.java")) + sorted(
        generated_root.rglob("*.java")
    )
    classpath = os.pathsep.join(
        (str(build_android_jar), str(build_core_lambda_stubs))
    )
    run(
        [
            str(javac),
            "-encoding",
            "UTF-8",
            "-source",
            "8",
            "-target",
            "8",
            "-Xlint:-options",
            "-classpath",
            classpath,
            "-d",
            str(classes_root),
            *(str(path) for path in java_sources),
        ],
        show_output=False,
    )

    provider_classes = sorted(
        (classes_root / "com" / "android" / "media" / "tv" / "remoteprovider").glob(
            "*.class"
        )
    )
    if not provider_classes:
        raise RuntimeError("javac produced no TvRemoteProvider classes")
    run(
        [
            str(java),
            "-cp",
            str(d8_jar),
            "com.android.tools.r8.D8",
            "--min-api",
            "24",
            "--lib",
            str(build_android_jar),
            "--classpath",
            str(classes_root),
            "--output",
            str(dex_root),
            *(str(path) for path in provider_classes),
        ]
    )

    classes_dex = require_file(dex_root / "classes.dex", "D8 classes.dex")
    descriptors = dex_class_descriptors(classes_dex)
    required_descriptor = "Lcom/android/media/tv/remoteprovider/TvRemoteProvider;"
    if required_descriptor not in descriptors:
        raise RuntimeError("runtime dex does not define TvRemoteProvider")
    unexpected = sorted(
        descriptor
        for descriptor in descriptors
        if not descriptor.startswith(
            "Lcom/android/media/tv/remoteprovider/TvRemoteProvider"
        )
    )
    if unexpected:
        raise RuntimeError(
            "runtime dex unexpectedly bundles framework/AIDL definitions: "
            + ", ".join(unexpected)
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".jar.tmp")
    info = zipfile.ZipInfo("classes.dex", date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    with zipfile.ZipFile(temporary, "w") as archive:
        archive.writestr(info, classes_dex.read_bytes())
    temporary.replace(output)


def build_framework_overlay(
    *,
    java: Path,
    openssl: Path,
    aapt2: Path,
    apksigner_jar: Path,
    android_jar: Path,
    build_root: Path,
    output: Path,
) -> None:
    build_root.mkdir(parents=True, exist_ok=True)
    overlay_root = REPO / "assets" / "tv_remote_overlay"
    manifest = require_file(
        overlay_root / "AndroidManifest.xml", "TV remote overlay manifest"
    )
    resources = overlay_root / "res"
    signing_key = require_file(
        REPO / "tools" / "testkey_rsa2048.pem", "repository test private key"
    )
    certificate = require_file(
        overlay_root / "ubox10-test-overlay.x509.pem",
        "TV remote overlay certificate",
    )
    require_hash(signing_key, OVERLAY_TEST_KEY_SHA256, "repository test private key")
    require_hash(
        certificate,
        OVERLAY_CERTIFICATE_SHA256,
        "TV remote overlay certificate",
    )
    build_overlay_root = build_root / "source"
    shutil.copytree(overlay_root, build_overlay_root)
    build_signing_key = build_root / "testkey_rsa2048.pem"
    build_signing_key_pk8 = build_root / "testkey_rsa2048.pk8"
    build_android_jar = build_root / "android.jar"
    shutil.copy2(signing_key, build_signing_key)
    shutil.copy2(android_jar, build_android_jar)
    manifest = build_overlay_root / "AndroidManifest.xml"
    resources = build_overlay_root / "res"
    certificate = build_overlay_root / "ubox10-test-overlay.x509.pem"
    compiled = build_root / "overlay-res.zip"
    unsigned = build_root / "overlay-unsigned.apk"
    signed = build_root / "overlay-signed.apk"
    run(
        [
            str(openssl),
            "pkcs8",
            "-topk8",
            "-nocrypt",
            "-in",
            str(build_signing_key),
            "-outform",
            "DER",
            "-out",
            str(build_signing_key_pk8),
        ]
    )
    run(
        [
            str(aapt2),
            "compile",
            "--dir",
            str(resources),
            "-o",
            str(compiled),
        ]
    )
    run(
        [
            str(aapt2),
            "link",
            "-o",
            str(unsigned),
            "--manifest",
            str(manifest),
            "-I",
            str(build_android_jar),
            "--auto-add-overlay",
            str(compiled),
        ]
    )
    run(
        [
            str(java),
            "-jar",
            str(apksigner_jar),
            "sign",
            "--key",
            str(build_signing_key_pk8),
            "--cert",
            str(certificate),
            "--out",
            str(signed),
            str(unsigned),
        ]
    )
    verification = run(
        [
            str(java),
            "-jar",
            str(apksigner_jar),
            "verify",
            "--verbose",
            "--print-certs",
            str(signed),
        ]
    )
    if not any(
        marker in verification
        for marker in (
            "Verified using v2 scheme (APK Signature Scheme v2): true",
            "Verified using v3 scheme (APK Signature Scheme v3): true",
        )
    ):
        raise RuntimeError("framework overlay has no verified APK v2/v3 signature")
    badging = run([str(aapt2), "dump", "badging", str(signed)])
    if (
        "package: name='com.ubox10.overlay.tvremote'" not in badging
        or "overlay: targetPackage='android' priority='999' isStatic='true'"
        not in badging
    ):
        raise RuntimeError("framework overlay package identity is incorrect")
    resources_dump = run([str(aapt2), "dump", "resources", str(signed)])
    if (
        "string/config_tvRemoteServicePackage" not in resources_dump
        or '"com.google.android.tv.remote.service"' not in resources_dump
    ):
        raise RuntimeError("framework overlay does not contain the target resource")

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(signed, output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--remote-apk",
        type=Path,
        default=(
            MIGRATION_WORK
            / "donor"
            / "com.google.android.tv.remote.service_5.2.473254133.apk"
        ),
        help="Original-signed Android TV Remote Service 5.2.473254133 APK",
    )
    parser.add_argument(
        "--tvremote-archive",
        type=Path,
        default=MIGRATION_WORK / "aosp-tvremote-android-12.0.0_r1.tar.gz",
    )
    parser.add_argument(
        "--media-tv-archive",
        type=Path,
        default=MIGRATION_WORK / "aosp-media-tv-android-12.0.0_r1.tar.gz",
    )
    parser.add_argument(
        "--jdk",
        type=Path,
        default=(
            MIGRATION_WORK
            / "toolchain"
            / "jdk17"
            / "jdk-17.0.19+10"
        ),
    )
    parser.add_argument(
        "--platform",
        type=Path,
        default=MIGRATION_WORK / "toolchain" / "platform31" / "android-12",
    )
    parser.add_argument(
        "--build-tools",
        type=Path,
        default=MIGRATION_WORK / "toolchain" / "build-tools31" / "android-12",
    )
    default_openssl = (
        Path("C:/Program Files/Git/usr/bin/openssl.exe")
        if os.name == "nt"
        else Path(shutil.which("openssl") or "openssl")
    )
    parser.add_argument(
        "--openssl",
        type=Path,
        default=default_openssl,
        help="OpenSSL used only to convert the existing test key to PKCS#8",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    remote_apk = require_file(args.remote_apk, "Android TV Remote Service donor")
    tvremote_archive = require_file(args.tvremote_archive, "AOSP tvremote archive")
    media_tv_archive = require_file(args.media_tv_archive, "AOSP media/tv archive")

    executable_suffix = ".exe" if os.name == "nt" else ""
    java = require_file(args.jdk / "bin" / f"java{executable_suffix}", "java")
    javac = require_file(args.jdk / "bin" / f"javac{executable_suffix}", "javac")
    aidl = require_file(args.build_tools / f"aidl{executable_suffix}", "aidl")
    aapt2 = require_file(args.build_tools / f"aapt2{executable_suffix}", "aapt2")
    d8_jar = require_file(args.build_tools / "lib" / "d8.jar", "d8.jar")
    apksigner_jar = require_file(
        args.build_tools / "lib" / "apksigner.jar", "apksigner.jar"
    )
    core_lambda_stubs = require_file(
        args.build_tools / "core-lambda-stubs.jar", "core-lambda-stubs.jar"
    )
    android_jar = require_file(args.platform / "android.jar", "Android API 31 jar")
    openssl = require_file(args.openssl, "OpenSSL")

    verify_remote_apk(
        remote_apk,
        java=java,
        apksigner_jar=apksigner_jar,
        aapt2=aapt2,
    )

    # Android Build Tools 31 on Windows cannot reliably consume non-ASCII
    # paths. Build in the host temp directory, then copy only final artifacts
    # into this repository's ignored work tree.
    with tempfile.TemporaryDirectory(
        prefix="ubox10-tvremote-"
    ) as temporary_directory:
        build_root = Path(temporary_directory)
        provider_output = (
            REPO
            / "work"
            / "system_injections"
            / "com.android.media.tv.remoteprovider.jar"
        )
        overlay_output = (
            REPO
            / "work"
            / "system_injections"
            / "UBOX10TvRemoteConfigOverlay.apk"
        )
        built_provider = build_root / "outputs" / provider_output.name
        built_overlay = build_root / "outputs" / overlay_output.name
        build_remoteprovider_jar(
            tvremote_archive=tvremote_archive,
            media_tv_archive=media_tv_archive,
            java=java,
            javac=javac,
            aidl=aidl,
            d8_jar=d8_jar,
            android_jar=android_jar,
            core_lambda_stubs=core_lambda_stubs,
            build_root=build_root / "provider",
            output=built_provider,
        )
        build_framework_overlay(
            java=java,
            openssl=openssl,
            aapt2=aapt2,
            apksigner_jar=apksigner_jar,
            android_jar=android_jar,
            build_root=build_root / "overlay",
            output=built_overlay,
        )
        staged_apk = (
            REPO
            / "work"
            / "preinstall_apks"
            / "AndroidTvRemoteService-5.2.473254133.apk"
        )
        publish_file(built_provider, provider_output)
        publish_file(built_overlay, overlay_output)
        publish_file(remote_apk, staged_apk)

    print("\nPrepared inputs:")
    for path in (staged_apk, provider_output, overlay_output):
        print(f"  {path.relative_to(REPO)}")
        print(f"    size={path.stat().st_size}")
        print(f"    sha256={sha256(path)}")
    print(
        "\nThe Google APK remains ignored under work/ and must never be "
        "committed or redistributed."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
