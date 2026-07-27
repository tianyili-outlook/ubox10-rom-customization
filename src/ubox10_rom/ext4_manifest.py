"""Pure JSON checks for M6b ext4 semantic-manifest contracts.

This module deliberately does not parse images, invoke ext4 tools, create
filesystems, or communicate with hardware.  It is the first M6b.1 guard that
rejects a logical `/system` subtree when it is presented as the ext4 root.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


MANIFEST_SCHEMA_V1 = "ubox10.ext4-semantic-manifest/v1"


@dataclass(frozen=True)
class RootHierarchyResult:
    """Machine-readable result of a root-hierarchy contract check."""

    status: str
    reason_codes: tuple[str, ...]
    source_root_identity: str | None
    observed_direct_child_names: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "source_root_identity": self.source_root_identity,
            "observed_direct_child_names": list(self.observed_direct_child_names),
            "analysis_boundary": (
                "Pure JSON manifest validation only; no image, ext4 tool, "
                "Fastboot, UART, PhoenixCard, or device access occurred."
            ),
        }


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _as_string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return value


def _direct_child_name(path: str) -> str | None:
    """Return a normalized direct child name for an absolute logical path."""

    if not path.startswith("/") or path == "/" or "\\" in path:
        return None
    components = path.split("/")[1:]
    if len(components) != 1 or not components[0] or components[0] in {".", ".."}:
        return None
    return components[0]


def assess_root_hierarchy(manifest: Mapping[str, Any]) -> RootHierarchyResult:
    """Validate the M6b.0 root contract without trusting a host path string.

    The input may be a deliberately small root-contract fixture.  A complete
    v1 semantic manifest adds many more fields, but this guard intentionally
    validates only the invariants required before any ext4 builder can run.
    """

    reasons: list[str] = []

    schema = manifest.get("schema")
    if schema != MANIFEST_SCHEMA_V1:
        reasons.append("invalid_schema")

    root_contract = _as_mapping(manifest.get("root_contract"))
    if root_contract is None:
        return RootHierarchyResult("FAIL", ("missing_root_contract",), None, ())

    logical_root = root_contract.get("logical_root")
    if logical_root != "/":
        reasons.append("invalid_logical_root")

    source_root_identity = root_contract.get("source_root_identity")
    if not isinstance(source_root_identity, str) or not source_root_identity:
        reasons.append("missing_source_root_identity")
        source_root_identity = None

    entries_value = manifest.get("entries")
    entries = entries_value if isinstance(entries_value, list) else None
    entries_by_path: dict[str, Mapping[str, Any]] = {}
    if entries is None:
        reasons.append("missing_entries")
    else:
        for index, entry_value in enumerate(entries):
            entry = _as_mapping(entry_value)
            if entry is None:
                reasons.append(f"invalid_entry:{index}")
                continue
            path = entry.get("path")
            item_type = entry.get("type")
            if not isinstance(path, str) or not isinstance(item_type, str):
                reasons.append(f"invalid_entry_fields:{index}")
                continue
            if path in entries_by_path:
                reasons.append(f"duplicate_path:{path}")
                continue
            entries_by_path[path] = entry

    root_entry = entries_by_path.get("/")
    if root_entry is None:
        reasons.append("missing_root_entry")
    elif root_entry.get("type") != "directory":
        reasons.append("root_not_directory")

    actual_direct_children = tuple(
        sorted(
            child
            for path in entries_by_path
            if (child := _direct_child_name(path)) is not None
        )
    )

    required_directories = _as_string_list(root_contract.get("required_directories"))
    if required_directories is None:
        reasons.append("invalid_required_directories")
        required_directories = []
    if "/system" not in required_directories:
        reasons.append("system_not_required")
    for required_path in required_directories:
        entry = entries_by_path.get(required_path)
        if entry is None:
            reasons.append(f"missing_required_directory:{required_path}")
        elif entry.get("type") != "directory":
            reasons.append(f"required_path_not_directory:{required_path}")

    required_child_names = _as_string_list(root_contract.get("required_child_names"))
    if required_child_names is None:
        reasons.append("invalid_required_child_names")
        required_child_names = []
    for child_name in required_child_names:
        if child_name not in actual_direct_children:
            reasons.append(f"missing_required_child:{child_name}")

    declared_children = _as_string_list(root_contract.get("observed_direct_child_names"))
    if declared_children is None:
        reasons.append("invalid_observed_direct_child_names")
    elif tuple(sorted(declared_children)) != actual_direct_children:
        reasons.append("declared_direct_children_mismatch")

    prohibited = root_contract.get("prohibited_subtree_root_identities")
    if not isinstance(prohibited, list):
        reasons.append("invalid_prohibited_subtree_root_identities")
    else:
        for index, item_value in enumerate(prohibited):
            item = _as_mapping(item_value)
            if item is None:
                reasons.append(f"invalid_prohibited_identity:{index}")
                continue
            logical_path = item.get("logical_path")
            subtree_identity = item.get("subtree_identity")
            if not isinstance(logical_path, str) or not isinstance(subtree_identity, str):
                reasons.append(f"invalid_prohibited_identity_fields:{index}")
                continue
            if source_root_identity is not None and source_root_identity == subtree_identity:
                reasons.append(f"prohibited_subtree_identity:{logical_path}")

    return RootHierarchyResult(
        status="PASS" if not reasons else "FAIL",
        reason_codes=tuple(reasons),
        source_root_identity=source_root_identity,
        observed_direct_child_names=actual_direct_children,
    )


def load_manifest(path: Path) -> Mapping[str, Any]:
    """Read one JSON manifest.  The caller decides how to report parse errors."""

    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, Mapping):
        raise ValueError("manifest JSON root must be an object")
    return decoded


def assess_root_hierarchy_file(path: Path) -> RootHierarchyResult:
    """Load and check a manifest, returning a deterministic failure on bad JSON."""

    try:
        manifest = load_manifest(path)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        return RootHierarchyResult(
            status="FAIL",
            reason_codes=(f"manifest_load_error:{exc.__class__.__name__}",),
            source_root_identity=None,
            observed_direct_child_names=(),
        )
    return assess_root_hierarchy(manifest)
