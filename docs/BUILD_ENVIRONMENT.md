# 当前构建环境

## 已验证主机

- Windows PowerShell 为候选构建入口。
- Python 3.11+；当前主机使用 Python 3.13。
- WSL2：`Ubuntu-24.04`。
- 私有 e2fsprogs：`1.47.2`。
- 固定路径：`/home/tianyi/ubox10-toolchain/prefix/e2fsprogs-1.47.2-gcc13.3.0/sbin`。
- Windows 工具：`avbtool.py`、`lpmake.exe`、`lpdumps.exe`、`simg2img.exe`、IMAGEWTY 解析/封装工具。
- PhoenixCard 4.2.7 只用于用户确认目标 TF 卡后的实机刷写。

旧的 WSL/Fastboot 配置过程已移至 `docs/archive/host/`，不需要日常重复执行。

## 从保留集恢复候选构建输入

仓库主动删除可再生成的逻辑分区和候选中间镜像。首次构建或清理后先执行：

```powershell
python .\scripts\prepare-candidate-inputs.py
```

该脚本会：

1. 核对官方 `x12-1024.img` SHA-256；
2. 验证 IMAGEWTY 伴生校验；
3. 必要时恢复 `firmware/extracted/` 和 `work/manifest.json`；
4. 从官方 `super.fex` 流式提取 `system_a/product_a/vendor_a/vendor_dlkm_a`；
5. 核对四个分区的固定 SHA-256；
6. 重新生成 ext4 语义清单。

脚本拒绝覆盖哈希不匹配的现有逻辑分区。

## 构建候选

```powershell
python .\scripts\build-candidate-firmware.py `
  --config .\configs\candidates\test9r1-android-tv-remote-service.json
```

构建器需要至少 7 GiB 临时空间，并在唯一事务目录完成 ext4、AVB、super、IMAGEWTY 和单元测试验证后才发布候选。目标目录已经存在时会拒绝覆盖。

Test8r2/Test9r1 依赖本地、未提交 Git 的 Projectivy 官方 APK：

```text
work/preinstall_apks/ProjectivyLauncher-4.71-c95-xda-release.apk
SHA-256 6818FC2DB44411A605CA4D7067FB9D7227AAEF2414CFF42DE58FE13E9321B47A
```

## Test9r1 Remote 准备工具链

Test9r1 额外使用本地、不提交 Git 的：

- Eclipse Temurin JDK 17.0.19+10；
- Android API 31 platform；
- Android Build Tools 31；
- OpenSSL（当前为 Git for Windows 自带版本）；
- Android 12 `android-12.0.0_r1` 的 AOSP tvremote/media-tv source archive；
- 用户本地提供、原始 Google 签名的 Android TV Remote Service
  5.2.473254133 APK。

执行：

```powershell
python .\scripts\prepare-tv-remote-experiment.py
```

脚本不会下载 Google APK。它会验证 APK SHA-256、Google 签名证书、
package/version 和 AOSP archive 哈希，编译只含 `TvRemoteProvider*` 的
runtime DEX，构建/签名单资源 framework RRO，再把三个输入写入忽略的
`work/`。Android Build Tools 31 在 Windows 对非 ASCII 路径兼容不稳定，
脚本因此在主机临时目录构建，最后只复制结果。

当前锁定工具包哈希：

| 文件 | SHA-256 |
|---|---|
| Temurin JDK 17 zip | `B5B235C48ADF6A081874B812C630B9F4B5F637B7A5ED18B9174D08A41EC4C235` |
| Android API 31 platform zip | `1D69FE1D7F9788D82FF3A374FAF4F6CCC9D1D372AA84A86B5BCFB517523B0B3F` |
| Android Build Tools 31 zip | `BFF1286DD77FFF51981DF15AC4349A618430DC5064870886B7108870433549F1` |

完整 donor/source/output 哈希见
`experiments/TEST9R1_ANDROID_TV_REMOTE_SERVICE.md`。

## M8 环境边界

M8 的 BPI H618 BSP 和 AOSP Android 12 构建必须放在 WSL/Linux 文件系统或独立构建盘，不放入本仓库或 `C:\` NTFS 工作树。开始大型下载前必须先锁定 commit、oversized files 清单、容器环境、预计磁盘空间和退出条件；当前未授权下载或编译。
