# UBOX10 M7 稳定版

状态：`STABLE / COMPLETE`

发布日期：2026-07-29

这是 UBOX10 / I12 Pro Max 定制项目的 M7 发布主页，也是刷机、恢复应用和
验收的唯一用户入口。M7 由两层组成：

1. **Test8r2 固件**：Projectivy 4.71、英文界面、实体遥控器友好的稳定基线；
2. **刷机后应用层**：SmartTube、Kodi、Jellyfin TV、Moonlight、AnExplorer，
   加上由 Google Play 管理的 AirReceiverLite。

[GitHub Release `m7`](https://github.com/tianyili-outlook/ubox10-rom-customization/releases/tag/m7)
附带可复现源码包和校验文件。由于官方固件、Google APK 与第三方 APK 的授权
边界，Release **不重新分发这些二进制文件**；本地已有 Test8r2 时直接校验
使用，没有时按本页从合法取得的官方原件重建。

机器可读组成清单位于
[`configs/releases/m7.json`](configs/releases/m7.json)，完整验收结论位于
[`docs/archive/m7/M7_COMPLETION_REPORT.md`](docs/archive/m7/M7_COMPLETION_REPORT.md)。
`main` 在本次发布后代表 M7 稳定基线；后续 M8 开发应在独立分支进行。

## 最短恢复流程

已有通过校验的 Test8r2 镜像时，实际使用流程只有四步：

1. 用 PhoenixCard 4.2.7 以 `Product` 模式把 Test8r2 写入 TF 卡并刷机；
2. 首次启动后连接 Wi-Fi，优先使用更稳定的 5 GHz，并记下电视 IP；
3. 在电视 Play Store 登录 Google 账号，出现付款设置时选择
   `Skip` / `Not now`；
4. 在仓库根目录运行：

```powershell
python .\scripts\install-userdata-apps.py `
  --guided-after-flash `
  --device "<电视IP>:7896"
```

脚本会打开 AirReceiverLite 的 Play 页面，等待用户完成免费安装，然后统一、
幂等地安装其余五项应用。下面是完整准备、刷机、重建和故障处理说明。

## 1. 准备

日常复现需要 Windows PowerShell、Python 3.11+、同一局域网和：

- PhoenixCard 4.2.7、读卡器及一张可清空的 TF 卡；
- Android Platform Tools（`adb.exe`）；
- Android SDK Build Tools（`aapt`、`apksigner`）；
- Java 17。

安装器会从 `ANDROID_SDK_ROOT` / `ANDROID_HOME`、PATH 和项目本地工具目录
查找这些工具，也可显式传入 `--adb`、`--aapt`、`--apksigner` 和
`--java-home`。项目惯用 ADB 路径为 `tools/platform-tools/adb.exe`。

只有从官方原件重建 Test8r2 时，才需要
[`docs/BUILD_ENVIRONMENT.md`](docs/BUILD_ENVIRONMENT.md) 中的 WSL2、
e2fsprogs 和固件工具链。

## 2. 取得并校验 Test8r2

### 路径 A：复用本地稳定镜像

优先复用：

```text
out/candidates/test8r2-restore-contacts-provider-r1/
  x12-test8r2-restore-contacts-provider.img
```

从仓库根目录校验：

```powershell
$release = Get-Content .\configs\releases\m7.json -Raw |
  ConvertFrom-Json
$image = $release.firmware.image
$actual = (Get-FileHash $image -Algorithm SHA256).Hash
if ($actual -ne $release.firmware.sha256) {
  throw "M7 image SHA-256 mismatch: $actual"
}
if ((Get-Item $image).Length -ne $release.firmware.bytes) {
  throw "M7 image byte size mismatch"
}
Write-Host "M7 image verified: $image"
```

Test8r2 的固定值为：

```text
大小：2,005,954,560 bytes
SHA-256：6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8
```

哈希或大小不符时不要刷写。

### 路径 B：从官方原件重建

把用户合法取得的官方 `x12-1024.img` 放在仓库根目录。固定值为：

```text
大小：2,018,890,752 bytes
SHA-256：371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065
```

准备 Projectivy 的锁定官方版本：

```powershell
$projectivy = Get-Content .\configs\apps\projectivy-4.71.json -Raw |
  ConvertFrom-Json
New-Item -ItemType Directory -Force `
  (Split-Path $projectivy.local_path) | Out-Null
if (-not (Test-Path -LiteralPath $projectivy.local_path)) {
  Invoke-WebRequest `
    -Uri $projectivy.download_url `
    -OutFile $projectivy.local_path
}
$actual = (Get-FileHash $projectivy.local_path -Algorithm SHA256).Hash
if ($actual -ne $projectivy.sha256) {
  throw "Projectivy SHA-256 mismatch: $actual"
}
```

随后执行：

```powershell
# 仅当缓存缺失、损坏或需要重新审计时运行
python .\scripts\prepare-candidate-inputs.py

python .\scripts\build-candidate-firmware.py `
  --config .\configs\candidates\test8r2-restore-contacts-provider.json
```

构建器需要至少 7 GiB 临时空间，并会执行单元测试、ext4、AVB、dynamic
super 与 IMAGEWTY 校验。不要为了常规重建删除以下四份官方逻辑分区缓存：

```text
out/official-system-a/20260726-r1/system_a.img
out/official-product-a/20260726-r1/product_a.img
out/official-vendor-a/20260726-r1/vendor_a.img
out/official-vendor-dlkm-a/20260726-r1/vendor_dlkm_a.img
```

构建器拒绝覆盖已有候选目录。已有目录应先按“路径 A”核验；异常输出应隔离
后再从干净目录重试，不能删除官方原件。

## 3. 用 PhoenixCard 刷机

刷机会清除盒子的 userdata / metadata，包括账号、设置和用户安装应用。

1. 备份需要保留的数据，关闭 UBOX10 电源。
2. 断开其他不必要的移动磁盘，只保留目标 TF 卡；再次核对盘符和容量。
3. 以管理员身份运行 PhoenixCard 4.2.7。
4. 选择 TF 卡和已经通过 SHA-256 校验的 Test8r2 镜像。
5. 选择 `Product` 模式，点击 `Burn`；写卡成功后安全弹出 TF 卡。
6. 保持盒子断电，插入量产 TF 卡后上电；刷写期间不要断电或拔卡。
7. 等待写入完成。历史 UART 成功标志为 `CARD OK` 和 `sprite success`；
   没有 UART 时也要留足时间，不要因电视暂时无画面而提前断电。
8. 盒子断电，取出 TF 卡，再次上电进入 Test8r2。

PhoenixCard 中若无法确定目标磁盘、模式或结果，应停止操作，不要猜测。需要
回滚时，用相同步骤刷回已经校验的官方 `x12-1024.img`。

## 4. 首次启动与联网

1. 确认 Projectivy 启动、界面为英语，方向、OK、Back、Home 和 Settings 正常。
2. 连接 Wi-Fi；5 GHz 扫描和连接更稳定，建议优先使用。
3. 在已连接网络详情中记下电视 IP。
4. 确认电脑和电视处于同一局域网；Test8r2 的 TCP ADB 端口为 `7896`。

连接检查：

```powershell
$adb = ".\tools\platform-tools\adb.exe"
& $adb connect "<电视IP>:7896"
& $adb devices -l
```

设备必须显示为 `device`，不能是 `offline` 或 `unauthorized`。

## 5. 一条命令完成应用安装

```powershell
python .\scripts\install-userdata-apps.py `
  --guided-after-flash `
  --device "<电视IP>:7896"
```

引导模式会：

1. 从配置锁定的官方 HTTPS 地址下载缺失的五个 APK；
2. 校验文件名、大小、SHA-256、APK metadata 和签名证书；
3. 验证电视符合 Test8r2 合同；
4. 打开 AirReceiverLite 的 Google Play 页面并暂停；
5. 等待用户登录 Play Store；出现 `Complete account setup` 时选择
   `Skip` / `Not now`，无需绑定信用卡；
6. 等待用户安装免费的 AirReceiverLite；
7. 统一、幂等安装 SmartTube、Kodi、Jellyfin TV、Moonlight 和 AnExplorer；
8. 将结果写入已被 Git 忽略的 `work/test9.3-guided-install.json`。

下载使用临时文件与原子发布，校验失败的 APK 不会投入使用；已有文件也不会
被静默覆盖。重复运行时，正确版本会返回 `already-current`。Google 账号、
付款信息和 Play 专有 APK 不会写入报告或 Git。

首次打开 AirReceiverLite 时，按提示授予“显示在其他应用上层”权限。Lite
必须保持前台，部分功能每次会话限 5 分钟；这是 M7 明确接受的范围，不要求
购买完整版。

## 6. 最小验收

安装后确认：

- Projectivy 中五个新图标可见，滚动、打开和焦点正常；
- 五项均可用方向、OK、Back、Home 导航，不强制鼠标模式；
- SmartTube 可播放 1080p，声音和返回正常；
- Kodi 可进入界面；
- Jellyfin TV 可进入服务器连接流程；
- Moonlight 可发现或手动添加 Sunshine；
- AnExplorer 可浏览内置存储 / USB，并能选择本地 APK；
- 打开 AirReceiverLite 后，iPhone 可发现电视，镜像、声音和同步正常。

Kodi、Jellyfin 和 Moonlight 在 M7 验收时缺少本地媒体、Jellyfin 服务器和
Sunshine 主机，只验证到界面及连接/发现边界；这是已记录的有限豁免，不代表
端到端播放已经测试。

## 7. 常见问题

- `adb connect` 失败：确认电视 IP、`7896` 端口和同一局域网，再重试。
- `baseline mismatch`：停止安装；可能刷入了 Test9r1/Test9r2 或其他镜像，
  不要用参数绕过合同。
- 找不到 `aapt` / `apksigner` / Java：安装 Android SDK Build Tools 与
  Java 17，或用命令行参数给出路径。
- Play Store 显示 `not compatible`：先确认 Test8r2 合同；不要加入 Leanback、
  混装 Google APK 或伪造设备身份规避。
- APK 下载或校验失败：保留错误信息并重试网络，不要改用随机 APK 镜像站。

## 发布与后续边界

- GitHub Release 只发布代码、配置、来源锁、校验值和文档；不发布官方固件、
  Google APK、Remote Service donor 或第三方 APK。
- 本地长期保留的可刷写镜像仅为官方原件与 M7/Test8r2；Test9r1/Test9r2
  已删除，但配置、生成脚本、固定哈希与实验文档仍可复现。
- M7 不再接受新功能修改。Play Store 电视化、GMS/认证、官方手机遥控产品化、
  64 位系统及 Netflix/DRM 属于 M8，并应在独立分支继续。

更多入口：

- [文档索引](docs/README.md)
- [M7 完成报告](docs/archive/m7/M7_COMPLETION_REPORT.md)
- [存储与复现策略](docs/STORAGE_AND_REPRODUCTION.md)
- [构建环境](docs/BUILD_ENVIRONMENT.md)
- [历史归档](docs/archive/README.md)
