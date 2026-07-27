# M6b.3a：合成 ext4 正样本批量执行

> 历史运行手册：两次 fixture 已通过，不需要重复执行。

## 这一阶段在做什么

这一阶段会制造两块内容完全相同、每块 16 MiB 的“小型练习磁盘”。它们不是 UBOX 固件，也不包含官方文件。练习盘中会放入：

- 正确的 ext4 根目录和根级 `/system`；
- 普通文件与目录；
- 一个真实符号链接；
- 两个名字指向同一 inode 的硬链接；
- 非默认 UID、GID 和权限；
- 模拟 Android SELinux、capability 和 POSIX ACL 的三个二进制扩展属性。

然后使用已经锁定的 `e2fsprogs 1.47.2` 做只读结构检查并生成证据。连续生成两次，是为了确认相同输入会得到相同镜像哈希。

## 为什么与最终 UBOX 固件有关

Android 12 动态分区中的 `system_a` 本质上是 ext4 文件系统。以后删除厂商应用、换 launcher 或调整系统文件时，如果重建工具把软链接、权限、SELinux 标签、capability、硬链接或 `/system` 根层级弄错，设备可能无法启动，硬件服务也可能失效。

本阶段相当于先用已知答案的“标准试件”检查测量仪器。只有正样本能被稳定生成并完整读出，才进入独立解析器和故障样本；之后才有资格只读分析官方 `system_a`。

## 风险、边界与恢复

- UBOX 风险：**无**。UBOX10 保持断电，FT232RL 不连接电脑或盒子。
- 主机风险：**低**。只在项目 `out/m6b-fixture/` 和 `logs/host/` 新建目录及两个 16 MiB 文件。
- 不使用管理员权限或 `sudo`，不安装软件，不挂载 loop device，不访问 `/dev`。
- 不读取或写入 `x12-1024.img`、`super.img`、`work/`、任何官方分区、PhoenixCard、Fastboot 或 UART。
- 失败时保留失败目录，不删除、不覆盖、不自行修改脚本重试。项目回滚就是忽略本次新建的 `out/` 与 `logs/host/` 目录；设备没有状态需要恢复。

## 成功标准

1. 两次执行都显示 `status=PASS`。
2. 两个 `e2fsck -fn` 都正常完成，没有修复动作。
3. 作者侧证据能看到 `/system`、软链接、同 inode 的硬链接、指定 UID/GID/mode 和三个 xattr。
4. 两次 `positive.ext4` 的 SHA-256 完全相同。
5. 所有证据清单自身校验通过。

本阶段通过只证明“标准练习盘可以稳定生成”。它不证明仓库解析器正确，也不放行官方镜像重建或刷机。

## 一次性完整操作

### 1. 操作前状态

确认：

- UBOX10 已断电；
- FT232RL 与电脑、UBOX10 都断开；
- 不需要打开管理员 PowerShell；
- 不需要再次进入 BIOS、安装软件或更新 Ubuntu。

### 2. 在 Ubuntu 24.04 中执行两次

从开始菜单打开 `Ubuntu 24.04`。看到类似 `tianyi@Illidan:~$` 的提示符后，整段复制执行：

```bash
set -euo pipefail
cd /mnt/c/Users/tiany/Documents/ubox10-rom改造
bash scripts/build-m6b-positive-fixture.sh
bash scripts/build-m6b-positive-fixture.sh
```

每次成功都会打印：

```text
Fixture output: .../out/m6b-fixture/<run-id>
Evidence directory: .../logs/host/<run-id>
```

不要给命令加 `sudo`，不要改变脚本路径或参数。

### 3. 一次性比较两次结果

仍在同一个 Ubuntu 窗口执行：

```bash
cd /mnt/c/Users/tiany/Documents/ubox10-rom改造
mapfile -t RUNS < <(find logs/host -maxdepth 1 -type d -name '*-m6b-positive-fixture' -printf '%f\n' | sort | tail -n 2)
test "${#RUNS[@]}" -eq 2
printf 'RUN_1=%s\nRUN_2=%s\n' "${RUNS[0]}" "${RUNS[1]}"
cat "logs/host/${RUNS[0]}/exit-status.txt"
cat "logs/host/${RUNS[1]}/exit-status.txt"
cat "logs/host/${RUNS[0]}/image-sha256.txt"
cat "logs/host/${RUNS[1]}/image-sha256.txt"
H1="$(cut -d' ' -f1 "logs/host/${RUNS[0]}/image-sha256.txt")"
H2="$(cut -d' ' -f1 "logs/host/${RUNS[1]}/image-sha256.txt")"
test "$H1" = "$H2"
printf 'REPRODUCIBILITY=PASS\n'
(cd "logs/host/${RUNS[0]}" && sha256sum --check --strict SHA256SUMS.txt)
(cd "logs/host/${RUNS[1]}" && sha256sum --check --strict SHA256SUMS.txt)
```

最后应出现 `REPRODUCIBILITY=PASS`，且清单项目全部显示 `OK`。

## 停止条件

遇到以下任一情况立即停止，不执行后续命令，也不要删除或覆盖失败目录：

- 出现 `Refuse:`；
- 任一命令返回错误；
- `exit-status.txt` 不是 `status=PASS` 和 `exit_code=0`；
- 两个镜像哈希不同；
- `e2fsck`、`debugfs` 或 SHA 清单报告失败；
- 脚本要求密码、管理员权限、`sudo`、挂载或访问设备。

## 统一交回

完成后只需发给我：

1. 两个 `Evidence directory` 的 Windows 相对路径，例如：
   `logs\host\20260726-xxxxxx-m6b-positive-fixture`
2. 第 3 步整段输出。

我会直接读取两个目录内的全部文件，统一验收镜像可重复性、目录/链接/权限/xattr 证据并更新文档。无需逐个粘贴文件内容。
