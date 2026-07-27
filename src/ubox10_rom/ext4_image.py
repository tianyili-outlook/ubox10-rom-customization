"""Small read-only ext4 manifest reader used by the UBOX10 project."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import stat
import struct
from typing import Any
import uuid


class Ext4Error(RuntimeError):
    pass


EXT4_MAGIC = 0xEF53
EXT4_EXTENTS_FL = 0x00080000
EXTENT_MAGIC = 0xF30A
XATTR_MAGIC = 0xEA020000
SUPPORTED_INCOMPAT = 0x000002C2  # filetype, extents, 64bit, flex_bg

XATTR_PREFIXES = {
    1: "user.",
    2: "system.posix_acl_access",
    3: "system.posix_acl_default",
    4: "trusted.",
    6: "security.",
    7: "system.",
    8: "system.richacl",
}


class Image:
    def __init__(self, path: Path):
        self.path = path
        self.size = path.stat().st_size
        self._file = path.open("rb")

    def read(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self.size:
            raise Ext4Error(f"read outside image: offset={offset} length={length}")
        self._file.seek(offset)
        data = self._file.read(length)
        if len(data) != length:
            raise Ext4Error("short image read")
        return data

    def close(self) -> None:
        self._file.close()

    def __del__(self) -> None:
        self._file.close()


@dataclass(frozen=True)
class Extent:
    logical: int
    physical: int
    length: int
    initialized: bool


@dataclass(frozen=True)
class Inode:
    number: int
    raw: bytes
    mode: int
    uid: int
    gid: int
    size: int
    links: int
    flags: int
    blocks: int
    file_acl: int
    extra_isize: int

    @property
    def kind(self) -> str:
        kind = stat.S_IFMT(self.mode)
        return {
            stat.S_IFREG: "regular",
            stat.S_IFDIR: "directory",
            stat.S_IFLNK: "symlink",
            stat.S_IFCHR: "char-device",
            stat.S_IFBLK: "block-device",
            stat.S_IFIFO: "fifo",
            stat.S_IFSOCK: "socket",
        }.get(kind, "unknown")


class Ext4Image:
    def __init__(self, path: Path):
        self.path = path
        self.image = Image(path)
        sb = self.image.read(1024, 1024)
        if struct.unpack_from("<H", sb, 56)[0] != EXT4_MAGIC:
            raise Ext4Error("invalid ext4 magic")
        self.sb = sb
        self.inodes_count = struct.unpack_from("<I", sb, 0)[0]
        blocks_lo = struct.unpack_from("<I", sb, 4)[0]
        blocks_hi = struct.unpack_from("<I", sb, 336)[0]
        self.blocks_count = blocks_lo | (blocks_hi << 32)
        self.block_size = 1024 << struct.unpack_from("<I", sb, 24)[0]
        self.blocks_per_group = struct.unpack_from("<I", sb, 32)[0]
        self.inodes_per_group = struct.unpack_from("<I", sb, 40)[0]
        self.inode_size = struct.unpack_from("<H", sb, 88)[0] or 128
        self.feature_compat = struct.unpack_from("<I", sb, 92)[0]
        self.feature_incompat = struct.unpack_from("<I", sb, 96)[0]
        self.feature_ro_compat = struct.unpack_from("<I", sb, 100)[0]
        self.desc_size = struct.unpack_from("<H", sb, 254)[0] or 32
        unknown = self.feature_incompat & ~SUPPORTED_INCOMPAT
        if unknown:
            raise Ext4Error(f"unsupported incompat feature bits: 0x{unknown:08X}")
        if self.block_size not in (1024, 2048, 4096, 8192, 16384, 32768, 65536):
            raise Ext4Error(f"unsupported block size: {self.block_size}")
        if not 128 <= self.inode_size <= self.block_size:
            raise Ext4Error(f"invalid inode size: {self.inode_size}")
        if not self.blocks_per_group or not self.inodes_per_group or self.desc_size < 32:
            raise Ext4Error("invalid ext4 geometry")
        self.group_count = math.ceil(self.blocks_count / self.blocks_per_group)
        self.gdt_offset = 2048 if self.block_size == 1024 else self.block_size
        if self.gdt_offset + self.group_count * self.desc_size > self.image.size:
            raise Ext4Error("group descriptor table outside image")

    def close(self) -> None:
        self.image.close()

    def _block(self, number: int) -> bytes:
        if number < 0 or number >= self.blocks_count:
            raise Ext4Error(f"invalid block number: {number}")
        return self.image.read(number * self.block_size, self.block_size)

    def inode(self, number: int) -> Inode:
        if number < 1 or number > self.inodes_count:
            raise Ext4Error(f"invalid inode number: {number}")
        group = (number - 1) // self.inodes_per_group
        index = (number - 1) % self.inodes_per_group
        gd = self.image.read(self.gdt_offset + group * self.desc_size, self.desc_size)
        table = struct.unpack_from("<I", gd, 8)[0]
        if self.desc_size >= 64:
            table |= struct.unpack_from("<I", gd, 40)[0] << 32
        raw = self.image.read(table * self.block_size + index * self.inode_size, self.inode_size)
        mode, uid_lo = struct.unpack_from("<HH", raw, 0)
        size_lo = struct.unpack_from("<I", raw, 4)[0]
        gid_lo, links = struct.unpack_from("<HH", raw, 24)
        blocks_lo, flags = struct.unpack_from("<II", raw, 28)
        uid_hi = struct.unpack_from("<H", raw, 120)[0] if self.inode_size >= 122 else 0
        gid_hi = struct.unpack_from("<H", raw, 122)[0] if self.inode_size >= 124 else 0
        blocks_hi = struct.unpack_from("<H", raw, 116)[0] if self.inode_size >= 118 else 0
        file_acl = struct.unpack_from("<I", raw, 104)[0]
        if self.inode_size >= 120:
            file_acl |= struct.unpack_from("<H", raw, 118)[0] << 32
        size_hi = (
            struct.unpack_from("<I", raw, 108)[0]
            if stat.S_IFMT(mode) == stat.S_IFREG and self.inode_size >= 112
            else 0
        )
        extra_isize = struct.unpack_from("<H", raw, 128)[0] if self.inode_size >= 130 else 0
        if 128 + extra_isize > self.inode_size:
            raise Ext4Error(f"inode {number} has invalid extra_isize")
        return Inode(
            number, raw, mode, uid_lo | (uid_hi << 16), gid_lo | (gid_hi << 16),
            size_lo | (size_hi << 32), links, flags, blocks_lo | (blocks_hi << 32),
            file_acl, extra_isize,
        )

    def _extent_node(self, data: bytes, expected_depth: int | None = None) -> list[Extent]:
        if len(data) < 12:
            raise Ext4Error("truncated extent header")
        magic, entries, maximum, depth, _generation = struct.unpack_from("<HHHHI", data)
        if magic != EXTENT_MAGIC or entries > maximum or 12 + entries * 12 > len(data):
            raise Ext4Error("invalid extent header")
        if expected_depth is not None and depth != expected_depth:
            raise Ext4Error("invalid extent depth")
        result: list[Extent] = []
        for index in range(entries):
            offset = 12 + index * 12
            if depth == 0:
                logical, raw_length, start_hi, start_lo = struct.unpack_from("<IHHI", data, offset)
                length = raw_length & 0x7FFF
                if length == 0:
                    length = 32768
                result.append(Extent(logical, start_lo | (start_hi << 32), length, not raw_length & 0x8000))
            else:
                _logical, leaf_lo, leaf_hi, _unused = struct.unpack_from("<IIHH", data, offset)
                result.extend(self._extent_node(self._block(leaf_lo | (leaf_hi << 32)), depth - 1))
        return sorted(result, key=lambda item: item.logical)

    def extents(self, inode: Inode) -> list[Extent]:
        if not inode.flags & EXT4_EXTENTS_FL:
            raise Ext4Error(f"inode {inode.number} does not use extents")
        result = self._extent_node(inode.raw[40:100])
        end = 0
        for item in result:
            if item.logical < end or item.physical + item.length > self.blocks_count:
                raise Ext4Error(f"invalid extents in inode {inode.number}")
            end = item.logical + item.length
        return result

    def data(self, inode: Inode) -> bytes:
        if inode.size == 0:
            return b""
        if inode.kind == "symlink" and inode.blocks == 0 and inode.size <= 60:
            return inode.raw[40:40 + inode.size]
        extents = self.extents(inode)
        output = bytearray()
        logical = 0
        remaining = inode.size
        index = 0
        while remaining:
            while index < len(extents) and logical >= extents[index].logical + extents[index].length:
                index += 1
            if index == len(extents) or logical < extents[index].logical:
                block = b"\0" * self.block_size
            else:
                item = extents[index]
                block = self._block(item.physical + logical - item.logical) if item.initialized else b"\0" * self.block_size
            take = min(remaining, self.block_size)
            output.extend(block[:take])
            remaining -= take
            logical += 1
        return bytes(output)

    def directory(self, inode: Inode) -> list[tuple[bytes, int]]:
        if inode.kind != "directory":
            raise Ext4Error(f"inode {inode.number} is not a directory")
        data = self.data(inode)
        result: list[tuple[bytes, int]] = []
        cursor = 0
        while cursor < len(data):
            if cursor + 8 > len(data):
                raise Ext4Error(f"truncated directory inode {inode.number}")
            child, record_length, name_length, _file_type = struct.unpack_from("<IHBB", data, cursor)
            if record_length < 8 or record_length % 4 or cursor + record_length > len(data):
                raise Ext4Error(f"bad directory record in inode {inode.number}")
            if name_length > record_length - 8:
                raise Ext4Error(f"bad directory name in inode {inode.number}")
            if child:
                result.append((data[cursor + 8:cursor + 8 + name_length], child))
            cursor += record_length
        return result

    @staticmethod
    def _xattr_name(index: int, suffix: bytes) -> str:
        try:
            decoded = suffix.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Ext4Error("non-UTF-8 xattr name") from exc
        prefix = XATTR_PREFIXES.get(index)
        if prefix is None:
            raise Ext4Error(f"unsupported xattr namespace index: {index}")
        if index in (2, 3, 8):
            if decoded:
                raise Ext4Error("fixed-name xattr has unexpected suffix")
            return prefix
        return prefix + decoded

    def _xattr_area(self, area: bytes, entries_offset: int, value_base: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        cursor = entries_offset
        while cursor + 4 <= len(area) and area[cursor:cursor + 4] != b"\0\0\0\0":
            if cursor + 16 > len(area):
                raise Ext4Error("truncated xattr entry")
            name_len, name_index, value_offset, value_inode, value_size, _hash = struct.unpack_from(
                "<BBHIII", area, cursor
            )
            name_end = cursor + 16 + name_len
            if name_end > len(area) or value_inode:
                raise Ext4Error("unsupported or truncated xattr value")
            value_start = value_base + value_offset
            value_end = value_start + value_size
            if value_end > len(area):
                raise Ext4Error("xattr value outside storage area")
            value = area[value_start:value_end]
            name = self._xattr_name(name_index, area[cursor + 16:name_end])
            item: dict[str, Any] = {
                "name": name,
                "length": len(value),
                "sha256": hashlib.sha256(value).hexdigest().upper(),
                "value_b64": base64.b64encode(value).decode("ascii"),
            }
            if name in ("system.posix_acl_access", "system.posix_acl_default"):
                item["acl_entries"] = self._decode_acl(value)
            result.append(item)
            cursor = (name_end + 3) & ~3
        return result

    @staticmethod
    def _decode_acl(value: bytes) -> list[dict[str, int | None]]:
        if len(value) < 4 or struct.unpack_from("<I", value)[0] != 1:
            raise Ext4Error("unsupported ext4 ACL version")
        result: list[dict[str, int | None]] = []
        cursor = 4
        while cursor < len(value):
            if cursor + 4 > len(value):
                raise Ext4Error("truncated ext4 ACL")
            tag, permissions = struct.unpack_from("<HH", value, cursor)
            cursor += 4
            identifier: int | None = None
            if tag in (2, 8):
                if cursor + 4 > len(value):
                    raise Ext4Error("truncated named ACL entry")
                identifier = struct.unpack_from("<I", value, cursor)[0]
                cursor += 4
            elif tag not in (1, 4, 16, 32):
                raise Ext4Error(f"unknown ACL tag: {tag}")
            result.append({"tag": tag, "permissions": permissions, "id": identifier})
        return result

    def xattrs(self, inode: Inode) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        start = 128 + inode.extra_isize
        if start + 4 <= self.inode_size and struct.unpack_from("<I", inode.raw, start)[0] == XATTR_MAGIC:
            area = inode.raw[start:]
            result.extend(self._xattr_area(area, 4, 4))
        if inode.file_acl:
            area = self._block(inode.file_acl)
            if struct.unpack_from("<I", area)[0] != XATTR_MAGIC:
                raise Ext4Error(f"inode {inode.number} has invalid external xattr block")
            result.extend(self._xattr_area(area, 32, 0))
        names = [item["name"] for item in result]
        if len(names) != len(set(names)):
            raise Ext4Error(f"inode {inode.number} has duplicate xattrs")
        return sorted(result, key=lambda item: item["name"])

    def manifest(self) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        paths_by_inode: dict[int, list[str]] = {}
        visited_dirs: set[int] = set()

        def visit(path: str, inode_number: int) -> None:
            inode = self.inode(inode_number)
            if inode.kind == "unknown":
                raise Ext4Error(f"unknown inode type at {path}")
            data: bytes | None = None
            entry: dict[str, Any] = {
                "path": path,
                "type": inode.kind,
                "mode_octal": f"{stat.S_IMODE(inode.mode):04o}",
                "uid": inode.uid,
                "gid": inode.gid,
                "link_count": inode.links,
                "diagnostic_inode_number": inode.number,
                "xattrs": self.xattrs(inode),
            }
            if inode.kind == "regular":
                data = self.data(inode)
                entry["content"] = {
                    "logical_size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest().upper(),
                }
            elif inode.kind == "symlink":
                data = self.data(inode)
                entry["symlink"] = {
                    "target_b64": base64.b64encode(data).decode("ascii"),
                    "target_sha256": hashlib.sha256(data).hexdigest().upper(),
                    "target_length": len(data),
                }
            entries.append(entry)
            paths_by_inode.setdefault(inode.number, []).append(path)
            if inode.kind == "directory":
                if inode.number in visited_dirs:
                    raise Ext4Error(f"directory cycle at {path}")
                visited_dirs.add(inode.number)
                for name_bytes, child in self.directory(inode):
                    if name_bytes in (b".", b".."):
                        continue
                    try:
                        name = name_bytes.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise Ext4Error(f"non-UTF-8 path below {path}") from exc
                    child_path = "/" + name if path == "/" else path + "/" + name
                    visit(child_path, child)

        visit("/", 2)
        entries.sort(key=lambda item: item["path"].encode("utf-8"))
        direct_children = sorted(
            item["path"][1:] for item in entries if item["path"].count("/") == 1 and item["path"] != "/"
        )
        hardlinks = []
        for inode_number, paths in paths_by_inode.items():
            if len(paths) > 1 and self.inode(inode_number).kind != "directory":
                ordered = sorted(paths)
                hardlinks.append({
                    "paths": ordered,
                    "expected_link_count": self.inode(inode_number).links,
                    "diagnostic_inode_number": inode_number,
                })
        hardlinks.sort(key=lambda item: item["paths"])
        root_identity = hashlib.sha256(
            json.dumps(entries[0], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest().upper()
        return {
            "schema": "ubox10.ext4-semantic-manifest/v1",
            "manifest_kind": "direct-image",
            "source": {
                "path": str(self.path),
                "ext4_image_sha256": _sha256_file(self.path),
                "read_method": "ubox10-rom pure-python ext4 reader",
            },
            "filesystem": {
                "magic": "EF53",
                "block_size": self.block_size,
                "inode_size": self.inode_size,
                "blocks_count": self.blocks_count,
                "inodes_count": self.inodes_count,
                "uuid": str(uuid.UUID(bytes=self.sb[104:120])),
                "volume_label": self.sb[120:136].split(b"\0", 1)[0].decode("utf-8"),
                "feature_compat": f"0x{self.feature_compat:08X}",
                "feature_incompat": f"0x{self.feature_incompat:08X}",
                "feature_ro_compat": f"0x{self.feature_ro_compat:08X}",
            },
            "root_contract": {
                "logical_root": "/",
                "required_directories": ["/system"],
                "required_child_names": ["system"],
                "observed_direct_child_names": direct_children,
                "source_root_identity": root_identity,
                "prohibited_subtree_root_identities": [],
            },
            "entries": entries,
            "hardlink_groups": hardlinks,
            "errors": [],
            "analysis_boundary": "Offline ext4 bytes only; not device-install or boot evidence.",
        }


def read_manifest(path: Path) -> dict[str, Any]:
    filesystem = Ext4Image(path)
    try:
        return filesystem.manifest()
    finally:
        filesystem.close()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_fixture_contract(manifest: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, expected in contract.get("filesystem", {}).items():
        actual = manifest["filesystem"].get(key)
        if actual != expected:
            errors.append(f"filesystem.{key}: expected {expected!r}, got {actual!r}")
    entries = {item["path"]: item for item in manifest["entries"]}
    for path, expected in contract.get("entries", {}).items():
        actual = entries.get(path)
        if actual is None:
            errors.append(f"{path}: missing")
            continue
        for key in ("type", "mode_octal", "uid", "gid", "link_count"):
            if key in expected and actual.get(key) != expected[key]:
                errors.append(f"{path}.{key}: expected {expected[key]!r}, got {actual.get(key)!r}")
        if "content_sha256" in expected and actual.get("content", {}).get("sha256") != expected["content_sha256"]:
            errors.append(f"{path}.content_sha256 mismatch")
        if "symlink_target_b64" in expected and actual.get("symlink", {}).get("target_b64") != expected["symlink_target_b64"]:
            errors.append(f"{path}.symlink_target mismatch")
        actual_xattrs = {item["name"]: item for item in actual.get("xattrs", [])}
        for name, xexpected in expected.get("xattrs", {}).items():
            xactual = actual_xattrs.get(name)
            if xactual is None:
                errors.append(f"{path}.xattr[{name}]: missing")
            elif xactual.get("sha256") != xexpected["sha256"]:
                errors.append(f"{path}.xattr[{name}]: sha256 mismatch")
    actual_groups = sorted(sorted(item["paths"]) for item in manifest["hardlink_groups"])
    for expected in contract.get("hardlink_groups", []):
        if sorted(expected) not in actual_groups:
            errors.append(f"hardlink group missing: {expected}")
    return errors
