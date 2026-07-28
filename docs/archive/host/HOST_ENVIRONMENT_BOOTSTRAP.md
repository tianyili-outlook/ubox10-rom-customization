# [归档] B1：WSL/Linux 工具链主机环境批量配置

> 历史资料：WSL2、Ubuntu 24.04 和工具链已配置完成，不需要重复执行。

## 1. 目的与授权边界

本批次把已完成的 H2c Windows feature Apply 收口为可用的 Linux 构建环境。用户自行完成本文件列出的 Windows 重启、WSL runtime/Ubuntu 安装和 Ubuntu 软件包安装；完成后由项目统一核验。

允许范围：正常 Windows 重启；WSL runtime；一个 Ubuntu LTS 发行版；APT 获取本文件列出的构建依赖；创建 Linux 家目录下的隔离工具链目录。

不在范围内：Docker、Android Studio、Android Emulator、VMware/VirtualBox、Hyper-V/Containers/Sandbox、任何 Android/AOSP 编译、e2fsprogs 源码下载或编译、真实 ext4 fixture、固件解包/重打包、磁盘挂载、Fastboot 写入、PhoenixCard、UBOX10 上电或 FT232RL 接线。

## 2. Windows：完成 H2c 与安装 WSL runtime

先保存 Windows 工作，然后从开始菜单执行一次**正常重新启动**。这是完成当前 WSL/VMP feature 事务所必需的步骤。

重启后，用“以管理员身份运行”的 PowerShell 依次执行。每条完成后再执行下一条；标准输出无须逐条发送。

```powershell
wsl --version
wsl --status
```

若 `wsl --version` 已显示 WSL 版本信息，跳过下一条；若提示 WSL 未安装或不可用，则执行：

```powershell
wsl --install --no-distribution
```

然后执行：

```powershell
wsl --update
wsl --set-default-version 2
wsl --list --online
```

从最后一条的列表中选择 Ubuntu LTS。优先使用列表中精确存在的 `Ubuntu-24.04`；若该名称不存在，则选择列表中最新的 Ubuntu LTS 名称，并把实际名称记录下来。示例：

```powershell
wsl --install -d Ubuntu-24.04 --no-launch
```

不要使用 `--web-download`，除非标准安装明确失败；若需要该回退，记录失败文本和实际使用的命令。不要执行裸 `wsl --install`，因为它会自行选择默认发行版，降低可复现性。

安装完成后启动该发行版：

```powershell
wsl -d Ubuntu-24.04
```

按提示创建一个普通 Linux 用户和本地密码；密码不发送给项目。若实际发行版名称不同，用该名称替换命令中的 `Ubuntu-24.04`。

## 3. Ubuntu：安装受控的通用构建依赖

以下命令在 Ubuntu shell 内执行。它们只安装通用工具和开发头文件；不下载 e2fsprogs 源码，不构建 Android 镜像。

```bash
sudo apt update
sudo apt install -y \
  build-essential autoconf automake libtool pkg-config \
  git ca-certificates curl wget rsync \
  python3 python3-venv python3-pip \
  e2fsprogs libarchive-dev liblz4-dev liblzma-dev libzstd-dev \
  libssl-dev libuuid1 uuid-dev libblkid-dev \
  libattr1-dev libacl1-dev libselinux1-dev zlib1g-dev \
  bison flex bc gawk file jq xz-utils zip unzip p7zip-full
```

在 Linux 文件系统中建立隔离目录，不要把构建目录放在 `/mnt/c/...` 的 Windows NTFS 工作区：

```bash
mkdir -p ~/ubox10-toolchain/{src,build,bin,logs}
chmod 700 ~/ubox10-toolchain
```

项目仓库仍以 Windows 侧 `C:\Users\tiany\Documents\ubox10-rom改造` 为唯一文档和证据源。将来若需要使用官方固件或仓库输入，先由项目指定可复制、只读的最小输入；不要现在自行复制 `firmware/`、`work/` 或 `.img` 文件到 WSL。

## 4. 不要做的事

- 不运行 `wsl --install`（无参数）、`wsl --install --web-download`（除非标准路径失败）、`wsl --shutdown`、`wsl --mount`、`wsl --import` 或 `wsl --unregister`。
- 不安装 Docker、Android Studio、Android Emulator、BlueStacks、VMware、VirtualBox、WSA 或任何第三方 hypervisor。
- 不安装 Python `ext4` 解析包；项目 oracle 保持“e2fsprogs 作者 + 仓库独立解析器”分权。
- 不下载/编译 e2fsprogs 源码；版本、签名、SHA-256、configure 参数和二进制哈希将在下一门单独锁定。
- 不运行 `make_ext4fs`、`mke2fs -d`、`debugfs` 写入命令、`lpunpack.py --info`，不生成 fixture、不读取官方大镜像。
- UBOX10 保持断电；FT232RL 保持断开。

## 5. 批量完成后的统一验收输入

完成上述所有步骤后，不需要逐项解释。只需完成下面的只读证据采集，并把两个目录和 Ubuntu 的实际发行版名称发回项目：

在管理员 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\tiany\Documents\ubox10-rom改造\scripts\inspect-wsl-h2c-compatibility.ps1"

powershell -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\tiany\Documents\ubox10-rom改造\scripts\inspect-wsl-oracle-host.ps1"
```

随后在 Ubuntu 内执行以下只读命令，并将完整输出保存为文本或直接粘贴：

```bash
cat /etc/os-release
uname -a
df -h ~
command -v mke2fs debugfs e2fsck dumpe2fs
mke2fs -V
debugfs -V
e2fsck -V
dumpe2fs -V
python3 --version
gcc --version | head -n 1
make --version | head -n 1
dpkg-query -W -f='${Package}\t${Version}\n' \
  e2fsprogs libarchive-dev liblz4-dev liblzma-dev libzstd-dev \
  libssl-dev uuid-dev libblkid-dev libattr1-dev libacl1-dev libselinux1-dev
```

项目统一验收通过后，下一步才是锁定上游 e2fsprogs 源码、签名、SHA-256 和构建参数的 toolchain manifest 门；仍不是 ext4 fixture 或 Android 固件构建。

## 6. 来源与理由

Microsoft 说明 `wsl --install --no-distribution` 可仅安装 WSL 而不选择发行版；`wsl --list --online` 用于获取当前有效发行版名；`wsl --set-default-version 2` 设置新发行版默认使用 WSL 2；`wsl --update` 更新 WSL runtime。见 [Microsoft WSL 命令参考](https://learn.microsoft.com/windows/wsl/basic-commands) 与 [WSL 安装文档](https://learn.microsoft.com/windows/wsl/install)。

Linux e2fsprogs 工具在本批次只以发行版软件包形式安装，用于后续环境能力与版本取证；并不替代未来锁定的上游源码构建。内核文档把 e2fsprogs 作为 ext 文件系统工具链的一部分，且建议使用较新的版本。见 [Linux 内核构建依赖文档](https://www.kernel.org/doc/html/latest/process/changes.html)。
