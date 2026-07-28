# 工程架构

## 技术栈

- Python 3.11+：固件容器、LP、ext4、AVB 编排和测试。
- PowerShell：Windows 设备、UART 和主机环境辅助。
- WSL2 Ubuntu 24.04：Linux 文件系统工具。
- e2fsprogs 1.47.2：`mke2fs/debugfs/e2fsck/dumpe2fs`。
- AOSP/Android 工具：`avbtool`、`lpmake`、`simg2img/img2simg`、boot image 工具。
- PhoenixCard 4.2.7：制作写入 UBOX eMMC 的量产卡。

## 目录

```text
firmware/extracted/   官方容器活动提取缓存（可重建）
src/ubox10_rom/       可复用 Python 解析代码
scripts/              构建、提取、检查和采集入口
tests/                小型 fixture 与单元测试
tools/                固定工具
work/                 当前 APK/manifest 输入与临时工作树
out/                  可再生成的逻辑分区、验证报告和候选固件
logs/                 UART、主机和分析结果
docs/                 核心文档、M8 研究区与 archive 历史资料
```

## 当前构建链

```text
官方 x12-1024.img
  → prepare-candidate-inputs.py 校验并恢复活动输入
  → 官方 super.fex
  → 提取 system_a/product_a/vendor_a/vendor_dlkm_a
  → 直接修改 system_a ext4
  → 重建 system AVB footer 和 vbmeta
  → lpmake 重建 sparse super
  → pack_image.py 替换容器载荷
  → 自动验证 ext4 差异/e2fsck/AVB/super/IMAGEWTY
  → 验证通过后原子发布候选目录
  → PhoenixCard 测试固件
```

构建前先检查 WSL、工具、输入和磁盘空间；修改在继承正常 Windows ACL 的唯一临时目录中完成，失败自动清理。直接修改 ext4，避免“解出全部文件再重建”造成 SELinux、属主、权限、链接和目录层级丢失。

## 基线边界

- 官方基线只来自 SHA-256 锁定的 `x12-1024.img`；`firmware/extracted/` 和 `out/official-*` 都是可再生成缓存。
- `work/` 的旧解包树与 `x12-purified.img` 含历史调试修改，已停止使用并按存储策略清理。
- 硬件相关的 `vendor`、`vendor_dlkm`、`boot`、`vendor_boot` 和 `dtbo` 在测试版 1 中保持官方内容。
- 长期可刷写镜像只保留官方原件、Test8r2 和当前 Test9r1；Test9w1 已退役并仅保留配置/历史。完整政策见 `STORAGE_AND_REPRODUCTION.md`。

## M8 目标架构

M8 不在当前镜像上伪造 arm64 属性。首选过渡结构是 64 位 Framework/ART/SurfaceFlinger、arm32 secondary ABI，以及经 Binder/VINTF 证明可独立保留的 32 位 Vendor service。64 位图形 same-process HAL 是第一硬门槛；详见 `architecture/M8_ARM64_AOSP_TV_MIGRATION.md`。
