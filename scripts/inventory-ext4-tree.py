#!/usr/bin/env python3
"""Create a semantic manifest for an already-mounted ext4 filesystem tree."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat


def file_type(mode: int) -> str:
    for predicate, name in (
        (stat.S_ISDIR, "directory"),
        (stat.S_ISREG, "regular"),
        (stat.S_ISLNK, "symlink"),
        (stat.S_ISCHR, "character"),
        (stat.S_ISBLK, "block"),
        (stat.S_ISFIFO, "fifo"),
        (stat.S_ISSOCK, "socket"),
    ):
        if predicate(mode):
            return name
    return "unknown"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def xattrs(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in sorted(os.listxattr(path, follow_symlinks=False)):
        result[name] = os.getxattr(path, name, follow_symlinks=False).hex().upper()
    return result


def entry(path: Path, relative: str) -> dict[str, object]:
    value = path.lstat()
    result: dict[str, object] = {
        "path": relative,
        "type": file_type(value.st_mode),
        "mode": f"{stat.S_IMODE(value.st_mode):04o}",
        "uid": value.st_uid,
        "gid": value.st_gid,
        "nlink": value.st_nlink,
        "xattrs": xattrs(path),
    }
    if stat.S_ISREG(value.st_mode):
        result["size"] = value.st_size
        result["sha256"] = digest(path)
    elif stat.S_ISLNK(value.st_mode):
        result["target"] = os.readlink(path)
    elif stat.S_ISCHR(value.st_mode) or stat.S_ISBLK(value.st_mode):
        result["device"] = [os.major(value.st_rdev), os.minor(value.st_rdev)]
    return result


def inventory(root: Path) -> list[dict[str, object]]:
    root = root.resolve(strict=True)
    output = [entry(root, "/")]

    def visit(directory: Path, relative: str) -> None:
        for item in sorted(os.scandir(directory), key=lambda value: value.name):
            path = Path(item.path)
            child = relative.rstrip("/") + "/" + item.name
            output.append(entry(path, child))
            if item.is_dir(follow_symlinks=False):
                visit(path, child)

    visit(root, "/")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = {"root": str(args.root), "entries": inventory(args.root)}
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
