#!/usr/bin/env python3
"""Fail-closed static isolation and marker checks for r7-diag1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/candidates/a16-prototype-b-r7-diag1.json"
DEFAULT_CANDIDATE = REPO / "out/candidates/a16-prototype-b-r7-diag1"
PREFIX = "UBOX_R7_DIAG1"


def fail(message: str) -> None:
    raise RuntimeError(message)


def patch_lines(path: Path, marker: str) -> list[str]:
    return [
        line[1:]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(marker) and not line.startswith(marker * 3) and line[1:].strip()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    overlay = REPO / cfg["source_contract"]["overlay"]
    patches = sorted((overlay / "patches").glob("*.patch"))
    if [path.name for path in patches] != [
        "0001-frameworks-native-renderengine-trace.patch",
        "0002-external-skia-egl-gl-trace.patch",
        "0003-frameworks-av-media-native-window-trace.patch",
        "0004-gralloc-private-contract-trace.patch",
    ]:
        fail("diag1 patch inventory changed")

    canonical_paths = [
        REPO / "configs/aosp/architecture-ceiling-a16/patches",
        REPO / "scripts/build-a16-prototype-b-r7-candidate.py",
        REPO / "configs/candidates/a16-prototype-b-r7.json",
    ]
    for path in canonical_paths:
        files = path.rglob("*") if path.is_dir() else [path]
        for candidate in files:
            if candidate.is_file() and PREFIX in candidate.read_text(
                encoding="utf-8", errors="replace"
            ):
                fail(f"canonical r7 path contains diag1 marker: {candidate}")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in patches)
    if combined.count("DIAGNOSTIC ONLY") < len(patches) or combined.count(
        "NO FUNCTIONAL REPAIR"
    ) < len(patches):
        fail("a diagnostic-only/no-repair patch header is absent")
    for stage in cfg["diagnostic"]["stages"]:
        if f"stage={stage}" not in combined:
            fail(f"diagnostic stage absent from patch series: {stage}")

    removed = [(path.name, line.strip()) for path in patches for line in patch_lines(path, "-")]
    allowed_removed = {
        (
            "0002-external-skia-egl-gl-trace.patch",
            'SkDebugf("Could not create EGL image, err = (%#x)", (int) eglGetError() );',
        ),
        (
            "0002-external-skia-egl-gl-trace.patch",
            "GrGLuint target = isRenderable ? GR_GL_TEXTURE_2D : GR_GL_TEXTURE_EXTERNAL;",
        ),
        ("0002-external-skia-egl-gl-trace.patch", "if ((status = glGetError()) != GL_NO_ERROR) {"),
    }
    if set(removed) != allowed_removed:
        fail(f"patch series removes non-instrumentation production lines: {removed}")
    if removed.count(
        ("0002-external-skia-egl-gl-trace.patch", "if ((status = glGetError()) != GL_NO_ERROR) {")
    ) != 2:
        fail("expected exactly two mechanically refactored glGetError checks")

    additions = "\n".join(
        line for path in patches for line in patch_lines(path, "+")
    )
    forbidden_added = {
        "fatal suppression": r"#\s*undef\s+LOG_ALWAYS_FATAL|LOG_ALWAYS_FATAL\s*=",
        "format mutation": r"native_window_set_buffers_format|setBuffersFormat\s*\(",
        "usage mutation": r"native_window_set_usage|setUsage\s*\(",
        "HWC policy": r"force.*(?:HWC|DEVICE)|setCompositionType\s*\(",
        "software decode": r"software.*decode|OMX\.google.*hevc",
        "timing workaround": r"\b(?:sleep|usleep|retry)\s*\(",
    }
    for label, pattern in forbidden_added.items():
        if re.search(pattern, additions, re.IGNORECASE):
            fail(f"diag1 added forbidden {label}")
    if "LOG_ALWAYS_FATAL(\"Failed to create a valid texture." not in combined:
        fail("the unchanged RenderEngine fatal context is absent")
    if combined.count("eglGetError()") != 2 or len(
        re.findall(r"(?<!e)glGetError\(\)", combined)
    ) != 5:
        # Counts include removed and replacement lines (plus the existing GL clear);
        # they lock the reviewed error-state refactor against extra queries.
        fail("reviewed EGL/GL error-query count changed")
    if "not_queried_preserve_state" not in combined:
        fail("successful unchecked EGL/GL stages no longer declare preserved error state")

    result: dict[str, object] = {
        "schema": 1,
        "candidate": cfg["id"],
        "decision": "PASS_DIAGNOSTIC_ONLY_STATIC_ISOLATION",
        "canonical_r7_marker_absent": True,
        "diag1_patch_count": len(patches),
        "expected_stages_present": cfg["diagnostic"]["stages"],
        "repair_logic_added": False,
        "fatal_path_present": True,
        "egl_error_query_semantics_locked": True,
        "format_usage_allocation_hwc_decision_mutation": False,
    }

    if args.candidate.is_dir():
        installed = {
            "surfaceflinger": args.candidate / "diag1-surfaceflinger",
            "libstagefright64": args.candidate / "diag1-libstagefright64",
            "gralloc32": args.candidate / "diag1-gralloc32",
            "gralloc64": args.candidate / "diag1-gralloc64",
        }
        canonical = {
            "surfaceflinger": args.candidate / "r7-surfaceflinger",
            "libstagefright64": args.candidate / "r7-libstagefright64",
            "gralloc32": args.candidate / "r7-gralloc32",
            "gralloc64": args.candidate / "r7-gralloc64",
        }
        for name, path in installed.items():
            if not path.is_file() or PREFIX.encode() not in path.read_bytes():
                fail(f"diag1 runtime marker absent: {name}")
        for name, path in canonical.items():
            if not path.is_file() or PREFIX.encode() in path.read_bytes():
                fail(f"canonical r7 runtime isolation failed: {name}")
        strings = "\n".join(
            subprocess.check_output(["strings", str(path)], text=True)
            for path in installed.values()
        )
        for stage in cfg["diagnostic"]["stages"]:
            if f"stage={stage}" not in strings:
                fail(f"built runtime stage absent: {stage}")
        if "Failed to create a valid texture." not in strings:
            fail("built runtime no longer contains the RenderEngine fatal text")
        result["built_runtime_markers"] = "PRESENT_ALL_FOUR_FILES"
        result["canonical_r7_runtime_markers"] = "ABSENT_ALL_FOUR_FILES"
        result["built_stage_strings"] = "PRESENT_ALL_EXPECTED"
    else:
        result["built_runtime_markers"] = "NOT_CHECKED_CANDIDATE_ABSENT"

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(result["decision"])


if __name__ == "__main__":
    main()
