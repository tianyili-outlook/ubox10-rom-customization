#!/usr/bin/env bash
# Build a project-authored ext4 fixture. Never mounts or reads firmware/devices.

set -Eeuo pipefail
umask 077

REPO="${1:-/mnt/c/Users/tiany/Documents/ubox10-rom改造}"
REPO="$(realpath -e -- "$REPO")"
EXPECTED_REPO="/mnt/c/Users/tiany/Documents/ubox10-rom改造"
[[ "$REPO" == "$EXPECTED_REPO" ]] || {
  printf 'Refuse: repository path is not the reviewed path: %s\n' "$REPO" >&2
  exit 1
}
[[ "$EUID" -ne 0 ]] || {
  printf 'Refuse: run as the ordinary WSL user, not root/sudo.\n' >&2
  exit 1
}

TOOLROOT="/home/tianyi/ubox10-toolchain/prefix/e2fsprogs-1.47.2-gcc13.3.0"
MKE2FS="$TOOLROOT/sbin/mke2fs"
DEBUGFS="$TOOLROOT/sbin/debugfs"
E2FSCK="$TOOLROOT/sbin/e2fsck"
DUMPE2FS="$TOOLROOT/sbin/dumpe2fs"

check_tool() {
  local path="$1" expected="$2" actual
  [[ -x "$path" ]] || {
    printf 'Refuse: locked tool is missing or not executable: %s\n' "$path" >&2
    exit 1
  }
  actual="$(sha256sum "$path" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || {
    printf 'Refuse: tool hash mismatch: %s\nexpected=%s\nactual=%s\n' \
      "$path" "$expected" "$actual" >&2
    exit 1
  }
}

check_tool "$MKE2FS" "18634c9e146141ae08f52f0d7b9fb83168d8920c4aecda41b7a1303661e89c39"
check_tool "$DEBUGFS" "7417553fa71ef79d5b114889129b0f502e2841d527e876fcc8e2b3d02f492276"
check_tool "$E2FSCK" "7c3d3c00e5a42b13fbcf3a171475319c50bf241228cf627957cb9bb3df73d57c"
check_tool "$DUMPE2FS" "cad9db2a5d73dee101a4790f3399bf5b4848e4c1e0af01ba4b490e9328d59f2f"

RUN_ID="$(date -u +%Y%m%d-%H%M%S)-m6b-positive-fixture"
OUT="$REPO/out/m6b-fixture/$RUN_ID"
EVIDENCE="$REPO/logs/host/$RUN_ID"
for path in "$OUT" "$EVIDENCE"; do
  [[ ! -e "$path" ]] || {
    printf 'Refuse: run path already exists: %s\n' "$path" >&2
    exit 1
  }
done
mkdir -p -- "$REPO/out/m6b-fixture" "$REPO/logs/host"
mkdir -- "$OUT" "$EVIDENCE"

STATUS="FAIL"
on_exit() {
  local rc=$?
  printf 'status=%s\nexit_code=%s\n' "$STATUS" "$rc" >"$EVIDENCE/exit-status.txt"
}
trap on_exit EXIT

IMAGE="$OUT/positive.ext4"
INPUT="$OUT/synthetic-input"
COMMANDS="$OUT/debugfs-write.commands"
mkdir -- "$INPUT"

# These are project-authored test bytes, never firmware or device content.
printf '#!/system/bin/sh\nexit 0\n' >"$INPUT/init"
printf 'synthetic-owned-tool-v1\n' >"$INPUT/owned-tool"
printf 'synthetic-selinux-payload-v1\n' >"$INPUT/selinux-test"
printf 'synthetic-capability-payload-v1\n' >"$INPUT/cap-test"
printf 'synthetic-acl-payload-v1\n' >"$INPUT/acl-test"
printf 'u:object_r:system_file:s0\0' >"$INPUT/security.selinux.bin"
printf '\x01\x00\x00\x02\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
  >"$INPUT/security.capability.bin"
printf '\x02\x00\x00\x00\x01\x00\x06\x00\xff\xff\xff\xff\x04\x00\x04\x00\xff\xff\xff\xff\x20\x00\x00\x00\xff\xff\xff\xff' \
  >"$INPUT/system.posix_acl_access.bin"

export SOURCE_DATE_EPOCH=1700000000
export E2FSPROGS_FAKE_TIME=1700000000

truncate -s 16M "$IMAGE"
{
  printf 'command='
  printf '%q ' "$MKE2FS" -t ext4 -F -q -b 4096 -I 256 -N 4096 -m 0 \
    -U 12345678-1234-5678-9abc-def012345678 -L UBOX10_FIXTURE \
    -O none,has_journal,ext_attr,resize_inode,dir_index,filetype,extent,64bit,flex_bg,sparse_super,large_file,huge_file,dir_nlink,extra_isize,metadata_csum \
    -E lazy_itable_init=0,lazy_journal_init=0,root_owner=0:0,hash_seed=87654321-4321-6789-abcd-210fedcba987 \
    "$IMAGE"
  printf '\n'
} >"$EVIDENCE/mke2fs-command.txt"

"$MKE2FS" -t ext4 -F -q -b 4096 -I 256 -N 4096 -m 0 \
  -U 12345678-1234-5678-9abc-def012345678 -L UBOX10_FIXTURE \
  -O none,has_journal,ext_attr,resize_inode,dir_index,filetype,extent,64bit,flex_bg,sparse_super,large_file,huge_file,dir_nlink,extra_isize,metadata_csum \
  -E lazy_itable_init=0,lazy_journal_init=0,root_owner=0:0,hash_seed=87654321-4321-6789-abcd-210fedcba987 \
  "$IMAGE" >"$EVIDENCE/mke2fs.stdout.txt" 2>"$EVIDENCE/mke2fs.stderr.txt"

cat >"$COMMANDS" <<EOF
set_current_time 1700000000
mkdir /system
mkdir /system/bin
mkdir /system/etc
write $INPUT/init /system/bin/init
set_inode_field /system/bin/init mode 0100755
set_inode_field /system/bin/init uid 0
set_inode_field /system/bin/init gid 0
write $INPUT/owned-tool /system/bin/owned-tool
set_inode_field /system/bin/owned-tool mode 0100750
set_inode_field /system/bin/owned-tool uid 1000
set_inode_field /system/bin/owned-tool gid 1000
ln /system/bin/owned-tool /system/bin/owned-tool-hardlink
set_inode_field /system/bin/owned-tool links_count 2
symlink /system/bin/tool-link /system/bin/owned-tool
write $INPUT/selinux-test /system/etc/selinux-test
set_inode_field /system/etc/selinux-test mode 0100644
ea_set -f $INPUT/security.selinux.bin /system/etc/selinux-test security.selinux
write $INPUT/cap-test /system/bin/cap-test
set_inode_field /system/bin/cap-test mode 0100755
ea_set -f $INPUT/security.capability.bin /system/bin/cap-test security.capability
write $INPUT/acl-test /system/etc/acl-test
set_inode_field /system/etc/acl-test mode 0100640
ea_set -f $INPUT/system.posix_acl_access.bin /system/etc/acl-test system.posix_acl_access
EOF

"$DEBUGFS" -w -f "$COMMANDS" "$IMAGE" \
  >"$EVIDENCE/debugfs-write.stdout.txt" \
  2>"$EVIDENCE/debugfs-write.stderr.txt"
cp -- "$COMMANDS" "$EVIDENCE/debugfs-write.commands.txt"
if grep -Eiq \
  '(^|[[:space:]])(Usage:|Command not found|File not found|No such file|Invalid argument|while setting extended attribute|while writing|while creating)' \
  "$EVIDENCE/debugfs-write.stdout.txt" "$EVIDENCE/debugfs-write.stderr.txt"; then
  printf 'Refuse: debugfs reported a write-command error; inspect evidence.\n' >&2
  exit 1
fi

"$E2FSCK" -fn "$IMAGE" \
  >"$EVIDENCE/e2fsck-fn.stdout.txt" \
  2>"$EVIDENCE/e2fsck-fn.stderr.txt"
"$DUMPE2FS" -h "$IMAGE" \
  >"$EVIDENCE/dumpe2fs-header.stdout.txt" \
  2>"$EVIDENCE/dumpe2fs-header.stderr.txt"

{
  "$DEBUGFS" -R "ls -l -p /" "$IMAGE"
  "$DEBUGFS" -R "ls -l -p /system" "$IMAGE"
  "$DEBUGFS" -R "ls -l -p /system/bin" "$IMAGE"
  "$DEBUGFS" -R "ls -l -p /system/etc" "$IMAGE"
  for path in \
    /system/bin/init \
    /system/bin/owned-tool \
    /system/bin/owned-tool-hardlink \
    /system/bin/tool-link \
    /system/etc/selinux-test \
    /system/bin/cap-test \
    /system/etc/acl-test
  do
    printf '\n===== stat %s =====\n' "$path"
    "$DEBUGFS" -R "stat $path" "$IMAGE"
  done
  printf '\n===== xattrs =====\n'
  "$DEBUGFS" -R "ea_get -x /system/etc/selinux-test security.selinux" "$IMAGE"
  "$DEBUGFS" -R "ea_get -x /system/bin/cap-test security.capability" "$IMAGE"
  "$DEBUGFS" -R "ea_get -x /system/etc/acl-test system.posix_acl_access" "$IMAGE"
} >"$EVIDENCE/debugfs-author-evidence.txt" 2>&1

{
  printf 'fixture_contract=ubox10.m6b-positive-fixture/v1\n'
  printf 'analysis_boundary=project-authored synthetic ext4 only; no firmware or device access\n'
  printf 'image_size_bytes=16777216\nblock_size=4096\ninode_size=256\ninode_count=4096\n'
  printf 'uuid=12345678-1234-5678-9abc-def012345678\n'
  printf 'hash_seed=87654321-4321-6789-abcd-210fedcba987\n'
  printf 'label=UBOX10_FIXTURE\nfixed_epoch=1700000000\n'
  printf 'required_root_child=/system\n'
  printf 'hardlink_paths=/system/bin/owned-tool,/system/bin/owned-tool-hardlink\n'
  printf 'symlink=/system/bin/tool-link -> /system/bin/owned-tool\n'
  printf 'nondefault_owner=/system/bin/owned-tool uid=1000 gid=1000 mode=0750\n'
  printf 'required_xattrs=security.selinux,security.capability,system.posix_acl_access\n'
} >"$EVIDENCE/fixture-contract.txt"

{
  printf 'run_id=%s\nout=%s\nevidence=%s\n' "$RUN_ID" "$OUT" "$EVIDENCE"
  id
  uname -a
  printf 'script_sha256='
  sha256sum "$REPO/scripts/build-m6b-positive-fixture.sh" | awk '{print $1}'
  for tool in "$MKE2FS" "$DEBUGFS" "$E2FSCK" "$DUMPE2FS"; do
    sha256sum "$tool"
    "$tool" -V 2>&1 | head -n 2
  done
} >"$EVIDENCE/execution-manifest.txt"

sha256sum "$IMAGE" >"$EVIDENCE/image-sha256.txt"
sha256sum "$INPUT"/* >"$EVIDENCE/synthetic-input-sha256.txt"
STATUS="PASS"
printf 'status=PASS\nexit_code=0\n' >"$EVIDENCE/exit-status.txt"
trap - EXIT
(
  cd "$EVIDENCE"
  find . -maxdepth 1 -type f \
    ! -name SHA256SUMS.txt \
    ! -name SHA256SUMS.verify.txt \
    -printf '%f\0' |
    LC_ALL=C sort -z |
    xargs -0 sha256sum >SHA256SUMS.txt
  sha256sum --check --strict SHA256SUMS.txt >SHA256SUMS.verify.txt
)

printf 'Fixture output: %s\nEvidence directory: %s\n' "$OUT" "$EVIDENCE"
