# 当前构建环境

## 已验证主机

- Windows PowerShell：仓库脚本、IMAGEWTY 打包和设备操作入口。
- Python 3.11+；当前主机为 Python 3.13。
- WSL2 `Ubuntu-24.04`。
- 私有 e2fsprogs 1.47.2：
  `/home/tianyi/ubox10-toolchain/prefix/e2fsprogs-1.47.2-gcc13.3.0/sbin`。
- Windows 侧已有 AVB、lpmake/lpdump、simg2img/img2simg 和 IMAGEWTY 工具。
- PhoenixCard 4.2.7 只在用户确认目标 TF 卡后使用。

旧 WSL/Fastboot 配置过程位于 [archive/host/](archive/host/)。

## M8A AOSP 构建卷

Android 12 manifest、superproject 和 ATV revision 已锁定，AOSP 源码同步与 M8A.2a 离线产品构建已完成。

- 2026-07-31：宿主 C 盘可用空间 435 GiB，WSL2 ext4 构建卷 `/home/tianyi/ubox10-aosp/` 可用空间 954 GB。
- 已完成 93 GB AOSP 源码同步，并成功生成 `ubox10` 架构的 `system.img` (537MB)、`product.img` (73MB) 与 `system_ext.img` (53MB)。

构建卷准备后只需记录：

```text
mount/path:
filesystem:
free space:
source revision:
out path:
cleanup path:
```

不要求先设计完整容器、CI 或长期归档体系。

## 旧 IMAGEWTY candidate 输入

当官方逻辑分区缓存缺失时：

```powershell
python .\scripts\prepare-candidate-inputs.py
```

构建配置驱动的旧式 candidate：

```powershell
python .\scripts\build-candidate-firmware.py `
  --config .\configs\candidates\<candidate>.json
```

构建器从 Windows PowerShell 启动，内部调用 WSL ext4 工具。完整管线见
[BUILD_PIPELINE.md](BUILD_PIPELINE.md)，保留集见
[STORAGE_AND_REPRODUCTION.md](STORAGE_AND_REPRODUCTION.md)。

Test9r1/Test9r2 的 JDK、Android Build Tools、Remote Service donor 和 AOSP
remoteprovider 细节属于 M7 历史实验，只有复现该实验时才读取
[archive/m7/TEST9R1_ANDROID_TV_REMOTE_SERVICE.md](archive/m7/TEST9R1_ANDROID_TV_REMOTE_SERVICE.md)。

## 当前边界

- 在构建卷准备好前，不向当前磁盘同步完整 AOSP。
- 不下载 H618 BSP，除非 M8B 已进入具体 64 位图形供体评估。
- 大型 source/build/out 不放入 Git；仓库只保存 source-lock、device 配置、
  小型报告和可复现脚本。
- M8A.2a 的目标是先得到可打包 ARM32 product，不被生产级审计环境阻塞。
