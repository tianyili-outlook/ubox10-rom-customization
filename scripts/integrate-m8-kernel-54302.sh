#!/bin/bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: $0 ANDROID_COMMON_REPOSITORY" >&2
    exit 2
fi

repository=$1
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/.." && pwd)
record="${repo_root}/configs/kernel/m8-kernel-5.4.302/conflict-resolutions.json"
semantic_patch="${repo_root}/configs/kernel/m8-kernel-5.4.302/semantic-resolutions.patch"
whitespace_patch="${repo_root}/configs/kernel/m8-kernel-5.4.302/post-merge-whitespace-fixes.patch"
vendor_commit=9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6
common_125=6cb0d5ef8b388d0249d96060e9ef31b466f88c7d
common_302=2443acb8671f5eaeac985e70446726278ed014ae
expected_synthetic=31364553e3cb9171d767cbf0c5c1af4e0198d5d8
expected_tree=b328c32712d65f8da98e013bc74944d68c05552b
expected_commit=027ef79e8facb73cb2419b4a08c0bd3f13a2206e

test -f "${record}"
test -f "${semantic_patch}"
test -f "${whitespace_patch}"
git -C "${repository}" diff --quiet
git -C "${repository}" diff --cached --quiet
for object in "${vendor_commit}" "${common_125}" "${common_302}"; do
    git -C "${repository}" cat-file -e "${object}^{commit}"
done
test "$(git -C "${repository}" rev-parse "${vendor_commit}^{tree}")" = d37d590a1e61c8e099e72170bf36e54091aa4820

synthetic_message='UBOX10 synthetic Allwinner baseline on Android common 5.4.125

Tree is byte-identical to Orange Pi commit 9ab7a758149d3c9b721878a0c18b3f9c5d6c93e6.
Parent is Android common commit 6cb0d5ef8b388d0249d96060e9ef31b466f88c7d,
which merged upstream Linux 5.4.125 into android12-5.4.
This synthetic ancestry exists only to expose a correct three-way LTS merge.'
synthetic=$(
    printf '%s\n' "${synthetic_message}" | env \
        GIT_AUTHOR_NAME='UBOX10 Architecture Checkpoint' \
        GIT_AUTHOR_EMAIL='ubox10@example.invalid' \
        GIT_AUTHOR_DATE='2026-08-22T17:30:00Z' \
        GIT_COMMITTER_NAME='UBOX10 Architecture Checkpoint' \
        GIT_COMMITTER_EMAIL='ubox10@example.invalid' \
        GIT_COMMITTER_DATE='2026-08-22T17:30:00Z' \
        git -C "${repository}" commit-tree "${vendor_commit}^{tree}" -p "${common_125}"
)
test "${synthetic}" = "${expected_synthetic}"

git -C "${repository}" switch --detach "${synthetic}"
set +e
git -C "${repository}" merge --no-commit --no-ff "${common_302}"
merge_code=$?
set -e
test "${merge_code}" -eq 1

python3 - "${repository}" "${record}" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

repo = sys.argv[1]
record = json.loads(Path(sys.argv[2]).read_text())
expected = sorted(
    record["upstream_stable_fix_wins"]
    + record["vendor_implementation_must_be_preserved"]
    + list(record["semantic_merge_required"])
)
actual = sorted(
    subprocess.check_output(
        ["git", "-C", repo, "diff", "--name-only", "--diff-filter=U"], text=True
    ).splitlines()
)
if actual != expected:
    raise SystemExit(f"unexpected conflict set: expected={expected!r}, actual={actual!r}")
PY

while IFS= read -r path; do
    git -C "${repository}" checkout "${common_302}" -- "${path}"
    git -C "${repository}" add -- "${path}"
done < <(python3 -c 'import json,sys; print(*json.load(open(sys.argv[1]))["upstream_stable_fix_wins"], sep="\n")' "${record}")

while IFS= read -r path; do
    if git -C "${repository}" cat-file -e "${synthetic}:${path}" 2>/dev/null; then
        git -C "${repository}" checkout "${synthetic}" -- "${path}"
        git -C "${repository}" add -- "${path}"
    else
        git -C "${repository}" rm -- "${path}"
    fi
done < <(python3 -c 'import json,sys; print(*json.load(open(sys.argv[1]))["vendor_implementation_must_be_preserved"], sep="\n")' "${record}")

git -C "${repository}" checkout "${common_302}" -- drivers/char/Kconfig
git -C "${repository}" checkout "${synthetic}" -- \
    drivers/cpufreq/sun50i-cpufreq-nvmem.c \
    drivers/pinctrl/sunxi/pinctrl-sunxi.c
git -C "${repository}" add -- \
    drivers/char/Kconfig \
    drivers/cpufreq/sun50i-cpufreq-nvmem.c \
    drivers/pinctrl/sunxi/pinctrl-sunxi.c

# The merge output carries four whitespace diagnostics from three non-conflict
# Android-common files. Preserve the already validated target tree by applying
# the exact mechanical normalization recorded with the integration inputs.
git -C "${repository}" apply --check "${whitespace_patch}"
git -C "${repository}" apply "${whitespace_patch}"
git -C "${repository}" add -- \
    Documentation/devicetree/bindings/gpu/samsung-rotator.yaml \
    drivers/tty/synclink_gt.c \
    sound/soc/meson/meson-codec-glue.c
git -C "${repository}" apply --check "${semantic_patch}"
git -C "${repository}" apply "${semantic_patch}"
git -C "${repository}" add -- \
    drivers/char/Kconfig \
    drivers/cpufreq/sun50i-cpufreq-nvmem.c \
    drivers/pinctrl/sunxi/pinctrl-sunxi.c

test -z "$(git -C "${repository}" diff --name-only --diff-filter=U)"
git -C "${repository}" diff --check --cached

merge_message='Merge Android common 5.4.302 into H616 vendor BSP

Use Android common 5.4.125 as the synthetic merge base for the exact Orange Pi 9ab7a758 tree. The target 2443acb8 contains upstream v5.4.302 plus the maintained Android 12 5.4 patch set. Preserve all vendor-added hardware trees except two superseded generic pstore files; resolve 46 overlaps according to the tracked UBOX10 conflict record.'
printf '%s\n' "${merge_message}" | env \
    GIT_AUTHOR_NAME='UBOX10 Architecture Checkpoint' \
    GIT_AUTHOR_EMAIL='ubox10@example.invalid' \
    GIT_AUTHOR_DATE='2026-08-22T18:00:00Z' \
    GIT_COMMITTER_NAME='UBOX10 Architecture Checkpoint' \
    GIT_COMMITTER_EMAIL='ubox10@example.invalid' \
    GIT_COMMITTER_DATE='2026-08-22T18:00:00Z' \
    git -C "${repository}" commit -F -

test "$(git -C "${repository}" rev-parse 'HEAD^{tree}')" = "${expected_tree}"
test "$(git -C "${repository}" rev-parse HEAD)" = "${expected_commit}"
git -C "${repository}" status --short
