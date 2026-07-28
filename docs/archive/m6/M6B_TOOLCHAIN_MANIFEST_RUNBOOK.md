# [归档] R2：e2fsprogs 1.47.2 toolchain manifest 批量执行

> 历史运行手册：e2fsprogs 1.47.2 工具链已完成，不需要重复配置。

## 目标与边界

本批次只下载、验签、构建并记录 Linux e2fsprogs 1.47.2 的工具链 manifest。它不创建 ext4、fixture、Android 映像或设备连接。

固定版本为 1.47.2：项目已有 Android `mke2fs 1.47.2` 观察项和 M6b.2 比较目标。Ubuntu 自带 1.47.0 只作宿主依赖，不可冒充本批次构建产物。

允许：安装 `gnupg`；从 kernel.org 下载发布物并从 Ubuntu 官方 keyserver 获取 kernel.org checksum autosigner 公钥；在 `~/ubox10-toolchain/` 内构建及私有安装；向仓库 `logs/host/` 写入文本证据。

禁止：`make check`、任何 `mke2fs` 创建参数、`debugfs` 写入、`e2fsck` 修复、fixture、挂载、固件文件复制、Android/AOSP 构建、super/AVB/PhoenixCard/Fastboot、UBOX10 上电或 FT232RL 接线。

失败即停止：保留日志和源码，禁止使用镜像站、随机 Git commit、`sudo make install`、额外 configure 参数或其他版本；不要删除目录重试。

## 固定输入

| 字段 | 固定值 |
|---|---|
| 发布目录 | `https://www.kernel.org/pub/linux/kernel/people/tytso/e2fsprogs/v1.47.2` |
| 源码 | `e2fsprogs-1.47.2.tar.xz` |
| 源码 SHA-256 | `08242e64ca0e8194d9c1caad49762b19209a06318199b63ce74ae4ef2d74e63c` |
| 签名子键指纹 | `B8868C80BA62A1FFFAF5FDA9632D3A06589DA6B1` |
| 公钥服务器 | `hkps://keyserver.ubuntu.com`，必须以完整指纹查询 |
| configure 参数 | `--prefix=<私有前缀> --disable-rpath` |
| install 路径覆盖 | `UDEV_RULES_DIR`、`CROND_DIR`、`SYSTEMD_SYSTEM_UNIT_DIR` 全部指向私有前缀 |

发布目录和签名清单见 [kernel.org e2fsprogs 1.47.2](https://www.kernel.org/pub/linux/kernel/people/tytso/e2fsprogs/v1.47.2/) 与 [签名 SHA-256 清单](https://www.kernel.org/pub/linux/kernel/people/tytso/e2fsprogs/v1.47.2/sha256sums.asc)。

## 一次性执行

在 Ubuntu-24.04 的普通用户 shell 依次执行；仅安装 `gnupg` 使用 `sudo`。

```bash
sudo apt update
sudo apt install -y gnupg
gpg --version | head -n 1
```

```bash
set -euo pipefail
umask 077
REPO=/mnt/c/Users/tiany/Documents/ubox10-rom改造
ROOT="$HOME/ubox10-toolchain"
VERSION=1.47.2
TAG="e2fsprogs-$VERSION"
RELEASE="https://www.kernel.org/pub/linux/kernel/people/tytso/e2fsprogs/v$VERSION"
EXPECTED_SHA256=08242e64ca0e8194d9c1caad49762b19209a06318199b63ce74ae4ef2d74e63c
EXPECTED_SIGNING_FPR=B8868C80BA62A1FFFAF5FDA9632D3A06589DA6B1
RUN_ID="$(date +%Y%m%d-%H%M%S)-m6b-toolchain-$VERSION"
SRC="$ROOT/src/$TAG"
BUILD="$ROOT/build/$TAG-gcc13.3.0"
PREFIX="$ROOT/prefix/$TAG-gcc13.3.0"
GNUPGHOME="$ROOT/gnupg-$TAG"
EVIDENCE="$REPO/logs/host/$RUN_ID"
test -d "$REPO"
for path in "$SRC" "$BUILD" "$PREFIX" "$GNUPGHOME" "$EVIDENCE"; do
  test ! -e "$path" || { echo "Refuse: existing path: $path" >&2; exit 1; }
done
mkdir -p "$SRC" "$BUILD" "$PREFIX" "$GNUPGHOME" "$EVIDENCE"
chmod 700 "$GNUPGHOME"
printf '%s\n' "$RUN_ID" | tee "$EVIDENCE/run-id.txt"
```

```bash
curl --fail --location --proto '=https' --tlsv1.2 -o "$SRC/sha256sums.asc" "$RELEASE/sha256sums.asc"
curl --fail --location --proto '=https' --tlsv1.2 -o "$SRC/$TAG.tar.xz" "$RELEASE/$TAG.tar.xz"
gpg --homedir "$GNUPGHOME" --batch --keyserver hkps://keyserver.ubuntu.com --recv-keys "$EXPECTED_SIGNING_FPR" >"$EVIDENCE/gpg-import.stdout.txt" 2>"$EVIDENCE/gpg-import.stderr.txt"
gpg --homedir "$GNUPGHOME" --batch --armor --export "$EXPECTED_SIGNING_FPR" >"$SRC/kernel-org-checksum-autosigner.asc"
gpg --homedir "$GNUPGHOME" --batch --with-colons --fingerprint >"$EVIDENCE/gpg-fingerprints.colons.txt"
grep -Fq "fpr:::::::::$EXPECTED_SIGNING_FPR:" "$EVIDENCE/gpg-fingerprints.colons.txt"
gpg --homedir "$GNUPGHOME" --batch --no-auto-key-retrieve --verify "$SRC/sha256sums.asc" >"$EVIDENCE/gpg-verify.stdout.txt" 2>"$EVIDENCE/gpg-verify.stderr.txt"
gpg --homedir "$GNUPGHOME" --batch --no-auto-key-retrieve --output "$SRC/sha256sums.txt" --decrypt "$SRC/sha256sums.asc"
printf '%s  %s\n' "$EXPECTED_SHA256" "$TAG.tar.xz" | sha256sum --check --strict | tee "$EVIDENCE/pinned-source-sha256-check.txt"
grep -Fx "$EXPECTED_SHA256  $TAG.tar.xz" "$SRC/sha256sums.txt" | tee "$EVIDENCE/upstream-source-sha256-entry.txt"
sha256sum "$SRC/kernel-org-checksum-autosigner.asc" "$SRC/sha256sums.asc" "$SRC/$TAG.tar.xz" | tee "$EVIDENCE/download-sha256.txt"
```

继续条件是 GPG 验证成功且完整指纹精确匹配。即使 GnuPG 显示 ownertrust 警告，也不要用 ownertrust 绕过；项目同时审计固定指纹、独立公钥端点、签名清单和固定源码 SHA-256。

```bash
tar --extract --xz --file "$SRC/$TAG.tar.xz" --no-same-owner --no-same-permissions -C "$SRC"
SOURCE_TREE="$SRC/$TAG"
test -d "$SOURCE_TREE"
{
  printf 'version=%s\nrelease=%s\nexpected_source_sha256=%s\nexpected_signing_fingerprint=%s\nsource_tree=%s\nbuild_dir=%s\nprefix=%s\nconfigure_args=--prefix=%s --disable-rpath\n' "$VERSION" "$RELEASE" "$EXPECTED_SHA256" "$EXPECTED_SIGNING_FPR" "$SOURCE_TREE" "$BUILD" "$PREFIX" "$PREFIX"
  uname -a
  gcc --version | head -n 1
  make --version | head -n 1
  ld -v
  dpkg-query -W -f='${Package}\t${Version}\n' build-essential gcc make binutils pkg-config libarchive-dev liblz4-dev liblzma-dev libzstd-dev libssl-dev uuid-dev libblkid-dev libattr1-dev libacl1-dev libselinux1-dev zlib1g-dev gnupg
} | tee "$EVIDENCE/build-input-manifest.txt"
(
  cd "$BUILD"
  "$SOURCE_TREE/configure" --prefix="$PREFIX" --disable-rpath 2>&1 | tee "$EVIDENCE/configure.log"
  make -j"$(nproc)" 2>&1 | tee "$EVIDENCE/make.log"
  make install \
    UDEV_RULES_DIR="$PREFIX/lib/udev/rules.d" \
    CROND_DIR="$PREFIX/etc/cron.d" \
    SYSTEMD_SYSTEM_UNIT_DIR="$PREFIX/lib/systemd/system" \
    2>&1 | tee "$EVIDENCE/make-install.log"
)
```

不得把 `make install` 改为 `sudo make install`。e2fsprogs 上游的 udev、cron 和 systemd 默认安装目录不自动跟随 `--prefix`，所以三项 make-time 路径覆盖也是固定合同的一部分；它们必须全部落在 Linux 家目录的私有前缀中。

```bash
{
  printf 'installed_prefix=%s\n' "$PREFIX"
  for tool in mke2fs debugfs e2fsck dumpe2fs; do
    path="$(find "$PREFIX" -type f -name "$tool" -print -quit)"
    test -n "$path"
    printf '\n[%s]\npath=%s\n' "$tool" "$path"
    "$path" -V 2>&1
    sha256sum "$path"
    ldd "$path"
  done
} | tee "$EVIDENCE/installed-tools-manifest.txt"
{
  printf 'build-metadata-sha256\n'
  sha256sum "$BUILD/config.log" "$BUILD/config.status" "$BUILD/MCONFIG" 2>/dev/null || true
  printf '\nsource-tree-top-level\n'
  find "$SOURCE_TREE" -mindepth 1 -maxdepth 1 -printf '%f\n' | LC_ALL=C sort
} | tee "$EVIDENCE/build-artifact-manifest.txt"
(
  cd "$EVIDENCE"
  find . -maxdepth 1 -type f ! -name SHA256SUMS.txt -printf '%f\0' | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS.txt
  sha256sum --check --strict SHA256SUMS.txt
) | tee "$EVIDENCE/SHA256SUMS.verify.txt"
printf 'Evidence directory: %s\n' "$EVIDENCE"
```

## 交回内容

提交 `Evidence directory` 路径，以及 `gpg-verify.stderr.txt`、`pinned-source-sha256-check.txt`、`upstream-source-sha256-entry.txt`、`installed-tools-manifest.txt`、`SHA256SUMS.verify.txt` 的完整内容。失败时发送第一条错误开始的完整输出和证据路径。

验收通过后才评审公开 synthetic fixture；Android `mke2fs + e2fsdroid`、官方 `system_a`、super、AVB 和 UBOX10 不属于本批次。
