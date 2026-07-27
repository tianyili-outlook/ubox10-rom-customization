#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only U3.2-f audit for the system ext4 source-root selection.

This tool parses the rebuild and purification scripts as Python syntax; it
never imports or executes them.  It combines their declared paths with the
streaming logical-system audit evidence to prove or refute a root-directory
flattening explanation.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditError(RuntimeError):
    """Raised when the source scripts no longer match the audited structure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise AuditError(f"{label} does not exist or is not a file: {resolved}")
    return resolved


def require_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AuditError(f"{label} must be below repository root {root}: {resolved}") from exc
    return resolved


def assignment_nodes(tree: ast.Module) -> dict[str, ast.expr]:
    result: dict[str, ast.expr] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value:
            result[statement.target.id] = statement.value
    return result


def evaluate_expression(node: ast.expr, environment: dict[str, str]) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in environment:
        return environment[node.id]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "os"
        and node.func.value.attr == "path"
        and node.func.attr == "join"
    ):
        return os.path.join(*(evaluate_expression(argument, environment) for argument in node.args))
    raise AuditError(f"Unsupported path expression: {ast.unparse(node)}")


def dict_value(node: ast.Dict, key: str) -> ast.expr:
    for candidate_key, candidate_value in zip(node.keys, node.values):
        if isinstance(candidate_key, ast.Constant) and candidate_key.value == key:
            return candidate_value
    raise AuditError(f"Dictionary has no {key!r} key")


def line_context(path: Path, lineno: int) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"line": lineno, "text": lines[lineno - 1].strip()}


def find_line_contexts(path: Path, needle: str) -> list[dict[str, Any]]:
    return [
        {"line": number, "text": line.strip()}
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if needle in line
    ]


def parse_rebuild_paths(repack: Path, purify: Path) -> dict[str, Any]:
    repack_tree = ast.parse(repack.read_text(encoding="utf-8"), filename=str(repack))
    purify_tree = ast.parse(purify.read_text(encoding="utf-8"), filename=str(purify))
    repack_assignments = assignment_nodes(repack_tree)
    purify_assignments = assignment_nodes(purify_tree)

    work_dir = evaluate_expression(repack_assignments["WORK_DIR"], {})
    partitions = repack_assignments["PARTITIONS"]
    if not isinstance(partitions, ast.Dict):
        raise AuditError("PARTITIONS is not a literal dictionary")
    system_config = dict_value(partitions, "system")
    if not isinstance(system_config, ast.Dict):
        raise AuditError("PARTITIONS['system'] is not a literal dictionary")
    system_source_expr = dict_value(system_config, "src_dir")
    system_source = evaluate_expression(system_source_expr, {"WORK_DIR": work_dir})

    purify_system_dir = evaluate_expression(purify_assignments["SYSTEM_DIR"], {})
    build_prop_expr = purify_assignments["BUILD_PROP_PATH"]
    build_prop = evaluate_expression(build_prop_expr, {"SYSTEM_DIR": purify_system_dir})

    return {
        "repack_work_dir": work_dir,
        "repack_system_source": {
            "path": system_source.replace("\\", "/"),
            "line_context": line_context(repack, system_source_expr.lineno),
        },
        "repack_make_ext4fs_source_argument": find_line_contexts(repack, 'cfg["src_dir"]'),
        "purify_system_directory": {
            "path": purify_system_dir.replace("\\", "/"),
            "line_context": line_context(purify, purify_assignments["SYSTEM_DIR"].lineno),
        },
        "purify_build_prop": {
            "path": build_prop.replace("\\", "/"),
            "line_context": line_context(purify, build_prop_expr.lineno),
        },
        "purify_system_relative_mutations": find_line_contexts(purify, '("system/'),
    }


def derive_root_relationship(paths: dict[str, Any], logical_report: dict[str, Any]) -> dict[str, Any]:
    official_root = logical_report["official"]["directory_observations"]["/"]
    official_system = logical_report["official"]["directory_observations"]["/system"]
    candidate_root = logical_report["candidate"]["directory_observations"]["/"]
    candidate_system = logical_report["candidate"]["directory_observations"]["/system"]
    relative = paths["repack_system_source"]["path"].removeprefix(paths["purify_system_directory"]["path"].rstrip("/") + "/")
    return {
        "purify_to_repack_relative_path": relative,
        "official_root_contains_system": "system" in official_root.get("entries", []),
        "official_system_directory_state": official_system.get("state"),
        "candidate_root_contains_system": "system" in candidate_root.get("entries", []),
        "candidate_system_directory_state": candidate_system.get("state"),
        "confirmed_root_flattening_chain": (
            relative == "system"
            and "system" in official_root.get("entries", [])
            and official_system.get("state") == "present"
            and "system" not in candidate_root.get("entries", [])
            and candidate_system.get("state") == "absent"
        ),
    }


def write_manifest(output_dir: Path) -> None:
    lines: list[str] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            lines.append(f"{sha256_file(path)}  {path}")
    (output_dir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser(repository_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="New evidence directory below this repository")
    parser.add_argument("--repack-script", type=Path, default=repository_root / "scripts/repack-rom.py")
    parser.add_argument("--purify-script", type=Path, default=repository_root / "scripts/purify-rom.py")
    parser.add_argument(
        "--logical-report",
        type=Path,
        default=repository_root / "logs/analysis/20260725-u3.2-logical-system-init-audit-r2/logical-system-init-audit.json",
    )
    return parser


def main() -> int:
    repository_root = Path(__file__).resolve().parent.parent
    args = build_parser(repository_root).parse_args()
    output_dir = require_within(args.output_dir, repository_root, "output directory")
    if output_dir.exists():
        raise AuditError(f"Refusing to overwrite existing output directory: {output_dir}")
    repack = require_file(args.repack_script, "repack script")
    purify = require_file(args.purify_script, "purify script")
    logical_report_path = require_file(args.logical_report, "logical-system report")
    logical_report = json.loads(logical_report_path.read_text(encoding="utf-8"))

    paths = parse_rebuild_paths(repack, purify)
    relationship = derive_root_relationship(paths, logical_report)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "scripts_imported_or_executed": False,
            "device_commands": "none",
            "input_images_modified": False,
            "output_directory": str(output_dir),
        },
        "inputs": {
            "repack_script": {"path": str(repack), "sha256": sha256_file(repack)},
            "purify_script": {"path": str(purify), "sha256": sha256_file(purify)},
            "logical_system_report": {"path": str(logical_report_path), "sha256": sha256_file(logical_report_path)},
        },
        "script_paths": paths,
        "logical_layout_relationship": relationship,
        "conclusion": (
            "The current rebuild pipeline selects a child of the extracted ext4 root as make_ext4fs input. "
            "When confirmed_root_flattening_chain is true, this is a sufficient local explanation for the "
            "candidate system_a root hierarchy mismatch. It does not prove the candidate is installed on the device."
        ),
        "next_step_boundary": (
            "Do not patch or run the rebuild pipeline. Design a M6b zero-content, root-hierarchy-preserving "
            "control experiment with explicit metadata and AVB gates first."
        ),
    }
    output_dir.mkdir(parents=True)
    report_path = output_dir / "rebuild-system-root-audit.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_manifest(output_dir)
    print(f"Rebuild system-root audit written to: {output_dir}")
    print(f"Report: {report_path}")
    print("Scripts executed: false; device commands: none; input images modified: false")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AuditError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2)
