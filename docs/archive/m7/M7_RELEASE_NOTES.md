# M7 GitHub Release Notes

M7 是 UBOX10 / I12 Pro Max 当前稳定发布，固件基线为 Test8r2。

## 包含内容

- Projectivy 4.71、英语界面与实体遥控器友好的 Test8r2 系统基线；
- SmartTube、Kodi、Jellyfin TV、Moonlight、AnExplorer 的来源锁和统一安装器；
- 通过 Google Play 安装的免费 AirReceiverLite 引导流程；
- PhoenixCard 刷机、官方原件重建、哈希校验、回滚与最小验收说明。

本说明与 `m7` tag 是固定发布入口。刷机联网后运行：

```powershell
python .\scripts\install-userdata-apps.py `
  --guided-after-flash `
  --device "<电视IP>:7896"
```

## 固定校验值

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| 官方 `x12-1024.img` | 2,018,890,752 | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |
| Test8r2 | 2,005,954,560 | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |

## Release 资产边界

`ubox10-m7-reproducibility.zip` 是 release commit 的确定性 `git archive`，
包含代码、配置、来源锁、校验值、测试与文档。它不包含官方固件、Google APK、
Remote Service donor 或第三方 APK；这些二进制文件不具备由本项目公开
再分发的授权。

资产可在 tag 创建后复现：

```powershell
python .\scripts\package-m7-release.py --ref m7
```

同时生成 `.sha256` 与 JSON metadata，供下载后校验。

## 已知边界

- AirReceiverLite 必须保持前台，部分功能每次会话限 5 分钟；
- Kodi、Jellyfin 与 Moonlight 的发布验收缺少对应外部资源，只通过界面与
  连接/发现边界；
- Play Store 电视化、GMS/认证、官方 Google TV 手机遥控产品化、64 位系统
  和 Netflix/DRM 不属于 M7。

Test9r1/Test9r2 本地候选产物已经删除；候选配置、输入哈希、生成脚本、镜像
SHA-256 与完整实验文档继续保留，可以按需复现。后续 M8 开发使用独立分支，
本 tag 保持为 M7 产品发布点。
