# 构建与打包管线

## 已有 IMAGEWTY candidate 链

```text
官方 x12-1024.img
  → prepare-candidate-inputs.py 恢复并验证活动输入
  → 提取 system_a/product_a/vendor_a/vendor_dlkm_a
  → 在 ext4 中应用配置驱动的单变量修改
  → 重建 system AVB footer 和 vbmeta
  → lpmake 重建 sparse super
  → pack_image.py 替换 IMAGEWTY 载荷
  → 验证 ext4/e2fsck、AVB、super 和容器
  → 发布 candidate
  → PhoenixCard 实机测试
```

这条链仍用于 Test8r2 恢复和旧式增量 candidate 的复现。核心入口：

- `scripts/prepare-candidate-inputs.py`
- `scripts/build-candidate-firmware.py`
- `scripts/pack_image.py`
- `configs/candidates/`
- `src/ubox10_rom/`

直接修改 ext4，避免整树解包/重建丢失 UID/GID、SELinux、capability、ACL、
链接或根目录语义。官方逻辑分区缓存和本地镜像保留政策见
[STORAGE_AND_REPRODUCTION.md](STORAGE_AND_REPRODUCTION.md)。

## M8A AOSP 链

M8A 不再以“删除厂商 APK”作为产品路线，而是：

```text
锁定的 Android 12 AOSP
  + device/google/atv ARM32 product 层
  + UBOX10 device/product 定义
  + 当前工作 boot/kernel/vendor/vendor_dlkm/DTB/TEE
  → ARM32 system/product/system_ext
  → UBOX logical partition / AVB / super / IMAGEWTY 打包
  → 单变量实机 candidate
```

详细继承和阶段边界见 [m8/ARCHITECTURE.md](m8/ARCHITECTURE.md) 与
[m8/research/m8a-atv-arm32/ubox10-atv-product-plan.md](m8/research/m8a-atv-arm32/ubox10-atv-product-plan.md)。

## 环境

- Windows PowerShell：仓库脚本和设备操作。
- Python 3.11+：解析、构建编排和测试。
- WSL2 Ubuntu 24.04 / Linux ext4：Android 和文件系统工具。
- e2fsprogs、AVB、lpmake/lpdump、simg2img/img2simg、IMAGEWTY 工具。
- PhoenixCard 4.2.7：用户确认 TF 卡后的实机刷写。

完整路径和构建空间见 [BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md)。

## 目录角色

```text
src/       可复用代码
scripts/   构建、采集、验证和恢复入口
tests/     小型 fixture 与单元测试
tools/     固定核心工具
configs/   candidate、应用和 source-lock 配置
firmware/  官方容器活动缓存
work/      本地输入和临时工作树
out/       可再生成分区、报告和 candidate
logs/      UART、设备和主机证据
docs/      当前事实、研究证据和历史归档
```
