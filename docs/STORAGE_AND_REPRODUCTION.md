# 存储与复现策略

## 镜像保留集

本地只长期保留三份可刷写 IMAGEWTY 镜像：

| 角色 | 路径 | SHA-256 |
|---|---|---|
| 官方恢复与唯一源原件 | `x12-1024.img` | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |
| 当前稳定基线 | `out/candidates/test8r2-restore-contacts-provider-r1/x12-test8r2-restore-contacts-provider.img` | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| 最新已完成技术探针（不晋级） | `out/candidates/test9r2-android-tv-remote-service-rro-path-r1/x12-test9r2-android-tv-remote-service-rro-path.img` | `27B54FB83E96D3863FAE2EF2718E8EC9ADDD863E5ED123082D5E6C8CA6FFFD52` |

官方原件即使不是当前测试镜像也绝不删除：它同时承担恢复入口、IMAGEWTY 模板和所有候选的唯一来源。

## 保留但不计为候选镜像

- `firmware/extracted/*.fex`：当前构建活动缓存，可由官方镜像重新提取。
- `work/manifest.json`：IMAGEWTY 目录缓存。
- 四个官方逻辑分区构建缓存，合计 1,888,006,144 bytes；已经从官方原件
  重建并命中锁定 SHA-256，现为节省后续构建时间而长期保留：
  - `out/official-system-a/20260726-r1/system_a.img`
  - `out/official-product-a/20260726-r1/product_a.img`
  - `out/official-vendor-a/20260726-r1/vendor_a.img`
  - `out/official-vendor-dlkm-a/20260726-r1/vendor_dlkm_a.img`
- `work/preinstall_apks/`：当前阶段和后续用户态安装所需、未提交 Git 的第三方/Google 原签名 APK；不得重新分发。
- `work/system_injections/`：由锁定 AOSP 源码/RRO source 可再生成的 Test9r1/Test9r2 本地二进制输入。
- `configs/candidates/*.json`、构建脚本、测试、语义清单和小型验证日志。
- `logs/`：已分区存放的设备/主机/分析证据；不因清理镜像而删除。

## 主动删除

- 所有淘汰候选目录及其固件和中间分区。
- Test8r2/最新技术探针目录内除最终 PhoenixCard 固件外的 `system_a/super/vendor/product/vbmeta` 等中间 `.img`。
- 已退役的 Test9w1 整个候选目录；其配置、哈希、生成方法和 Git 历史保留。
- 已失败 Test9r1 的最终固件；其配置、构建日志、清单、哈希和实验文档保留。
- `work/` 中旧 boot/system/vendor/product 解包树和重建产物。
- `firmware/extracted/super.unsparse.img`。
- 旧 `x12-purified.img`。
- 临时 AVB/FEC 试验镜像和 M6 fixture 输出。

历史候选的删除项、注入项、属性、来源哈希和生成方法仍由 `configs/candidates/`、`scripts/build-candidate-firmware.py`、`CHANGELOG.md` 与 Git 历史保存。

## 复现

```powershell
python .\scripts\prepare-candidate-inputs.py
python .\scripts\prepare-tv-remote-experiment.py
python .\scripts\build-candidate-firmware.py --config <候选配置.json>
```

第一条只在四个官方缓存缺失、损坏或需要重新审计时运行；正常连续构建直接复用缓存。第二条验证用户本地 Remote Service donor，并从锁定 Android 12 AOSP 源码构建 remoteprovider/RRO；第三条事务式重建指定候选。Google/第三方 APK 必须按配置中的来源、版本、签名和 SHA-256 放回忽略的 `work/`，不能提交或由项目下载。

## 清理记录

- 清理前：149 个 `.img`，合计约 85.677 GiB；`out/candidates/` 约 70.811 GiB，`work/` 约 8.506 GiB。
- 第一轮清理后曾保留官方、Test8r2、Test9w1 三份 `.img`，合计 6,030,742,528 bytes（约 5.617 GiB）；`.img` 占用减少约 80.060 GiB。
- 连同淘汰候选目录、旧解包树和其他可重建中间产物，本次共删除约 81.604 GiB；清理后整个仓库工作区约 8.185 GiB，其中 `out/` 约 3.744 GiB、`work/` 约 0.307 GiB、`firmware/` 约 1.880 GiB。
- 删除完成后，已在四个官方逻辑分区均不存在的条件下实际运行 `prepare-candidate-inputs.py`；`system_a`、`product_a`、`vendor_a`、`vendor_dlkm_a` 均由保留的官方原件成功重建并命中锁定 SHA-256。验证后再次删除这四个缓存 `.img`，保持三镜像保留集。
- Test9r1 构建后，保留集由 Test9w1 切换为 Test9r1；当前三份 `.img` 合计 6,030,791,680 bytes。已删除 Test9w1 候选目录、Test9r1 的逻辑分区/AVB/super 中间镜像、本轮重建的官方逻辑分区缓存和分析日志，共释放 7,651,182,014 bytes（约 7.126 GiB）。
- Test9r1 真机失败后，保留集切换为官方原件、Test8r2 和 Test9r2，三份可刷写 IMAGEWTY 仍合计 6,030,791,680 bytes。删除 Test9r1 最终镜像、Test9r2 中间镜像和一次超时留下的重复临时分区，共释放 7,404,837,598 bytes。
- 用户于 2026-07-29 明确要求不再重复删除官方逻辑分区缓存；四份缓存合计 1,888,006,144 bytes，后续清理脚本和人工清理都必须排除 `out/official-*-a/20260726-r1/*.img`。
- 已删除产物无法从当前工作区直接恢复；候选配置、构建脚本、方法文档与 Git 历史仍在，可按需重新生成。官方原件、稳定回退点和最新技术探针均已再次核对 SHA-256。Test9r2 的本地保留不代表产品晋级。
