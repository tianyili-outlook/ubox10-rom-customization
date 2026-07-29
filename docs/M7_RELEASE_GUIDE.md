# M7 发布与复现指南

发布状态：`STABLE / COMPLETE`

发布日期：2026-07-29

本页是 M7 的唯一发布入口。最终版本由以下两层组成：

1. Test8r2 固件：Projectivy 4.71、英文界面、遥控器友好的系统基线；
2. 刷机后应用层：SmartTube、Kodi、Jellyfin TV、Moonlight、AnExplorer，
   加上由 Google Play 管理的 AirReceiverLite。

机器可读版本清单位于 `configs/releases/m7.json`。Git 仓库保存构建方法、
来源锁、校验值、测试与文档，不重新分发官方固件、Google APK 或第三方 APK。

## 1. 准备

日常复现只需要 Windows PowerShell、Python 3.11+、同一局域网和以下工具：

- PhoenixCard 4.2.7、读卡器和一张可清空的 TF 卡；
- Android Platform Tools（`adb.exe`）；
- Android SDK Build Tools（`aapt`、`apksigner`）；
- 可供 `apksigner` 使用的 Java 17。

安装器会依次从 `ANDROID_SDK_ROOT`/`ANDROID_HOME`、PATH 和项目现有本地
工具目录查找这些工具。也可以分别传入 `--adb`、`--aapt`、
`--apksigner` 和 `--java-home`。本项目当前惯用的 ADB 路径是
`tools/platform-tools/adb.exe`。

只有在需要从官方原件重建 Test8r2 时，才需要
`docs/BUILD_ENVIRONMENT.md` 中的 WSL2、e2fsprogs 和固件工具链。

## 2. 取得并校验 Test8r2

### 路径 A：复用已经构建的稳定镜像

若本地已有下列文件，优先复用，不要仅为重建而删除候选或官方逻辑分区缓存：

```text
out/candidates/test8r2-restore-contacts-provider-r1/
  x12-test8r2-restore-contacts-provider.img
```

从仓库根目录执行：

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

预期 SHA-256：

```text
6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8
```

### 路径 B：从官方原件重建

把用户合法取得的官方 `x12-1024.img` 放在仓库根目录。它必须是
2,018,890,752 bytes，SHA-256 必须为：

```text
371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065
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
# 仅当缓存缺失、损坏或需要重新审计时运行；不要主动删除官方逻辑分区缓存
python .\scripts\prepare-candidate-inputs.py

python .\scripts\build-candidate-firmware.py `
  --config .\configs\candidates\test8r2-restore-contacts-provider.json
```

构建器需要至少 7 GiB 可用临时空间，并且只会在单元测试、ext4、AVB、
dynamic super 和 IMAGEWTY 校验全部通过后发布结果。若目标候选目录已存在，
构建器会拒绝覆盖；先按“路径 A”核验它。哈希不符时不要刷写，也不要删除
官方原件或四份官方逻辑分区缓存；应隔离异常候选并从干净输出目录重试。

## 3. 用 PhoenixCard 刷机

刷机会清除盒子的 userdata/metadata，包括账号、设置和用户安装的应用。

1. 备份需要保留的数据，关闭 UBOX10 电源。
2. 断开其他不必要的移动磁盘，只保留目标 TF 卡；确认盘符和容量无误。
3. 以管理员身份运行 PhoenixCard 4.2.7。
4. 选择目标 TF 卡和已经通过 SHA-256 校验的 Test8r2 镜像。
5. 选择 `Product` 模式，点击 `Burn`，等待写卡成功后安全弹出 TF 卡。
6. 保持盒子断电，插入量产 TF 卡后再上电；刷写期间不要断电或拔卡。
7. 等待写入完成。历史 UART 成功标志为 `CARD OK` 和 `sprite success`；
   没有 UART 时应留足时间，不要因电视暂时无画面而提前断电。
8. 盒子断电，取出 TF 卡，再次上电进入 Test8r2。

如果 PhoenixCard 中无法确定目标磁盘、模式或结果，停止操作，不要猜测。
需要回滚时用相同步骤刷回已校验的官方 `x12-1024.img`。

## 4. 首次启动与联网

1. 确认 Projectivy 启动、界面为英语，方向、OK、Back、Home 和 Settings 正常。
2. 连接 Wi‑Fi；已知 5 GHz 扫描和连接更稳定，建议优先使用。
3. 在 Settings 的已连接网络详情中记下电视 IP。
4. 确认电脑与电视在同一局域网。Test8r2 的 TCP ADB 端口为 `7896`。

可先手动确认连接：

```powershell
$adb = ".\tools\platform-tools\adb.exe"
& $adb connect "<电视IP>:7896"
& $adb devices -l
```

设备必须显示为 `device`，不能是 `offline` 或 `unauthorized`。

## 5. 一条命令完成应用安装

从仓库根目录运行，把地址替换为电视实际 IP：

```powershell
python .\scripts\install-userdata-apps.py `
  --guided-after-flash `
  --device "<电视IP>:7896"
```

引导模式会自动完成以下流程：

1. 只下载缺失的五个 APK，来源必须是配置中锁定的官方 HTTPS 地址；
2. 按文件名、bytes、SHA-256、APK metadata 和签名证书逐项校验；
3. 连接电视并验证设备确实符合 Test8r2 合同；
4. 在电视上打开 AirReceiverLite 的 Google Play 页面并暂停；
5. 用户登录 Play Store；若出现 `Complete account setup`，选择
   `Skip`/`Not now`，无需添加信用卡；
6. 用户安装免费的 AirReceiverLite，回到 PowerShell 按 Enter；
7. 脚本统一、幂等安装其余五项应用，并复核设备上的版本和 APK 哈希；
8. 把完整结果写入 `work/test9.3-guided-install.json`。

下载采用临时文件和原子发布；校验不匹配的文件不会成为正式 APK。脚本也
不会覆盖已经存在的文件：若现有 APK 校验失败，应先隔离该文件，再重试。
重复运行时，已安装的 AirReceiverLite 会被识别并跳过 Play 交互，其余五项
版本完全相同时返回 `already-current`。
Google 账号、付款信息和 Play 专有 APK 不会写入项目报告或 Git。

首次打开 AirReceiverLite 时，按电视提示授予“显示在其他应用上层”权限。
Lite 必须保持前台，且部分功能每次会话限 5 分钟；这是 M7 接受的明确范围，
不要求购买完整版。

## 6. 最小验收

安装后确认：

- Projectivy 中五个新图标可见，滚动和打开没有明显焦点错误；
- 五项均可用方向、OK、Back、Home 完成基础导航，不强制鼠标模式；
- SmartTube 可播放 1080p，声音和返回正常；
- Kodi 可进入界面；
- Jellyfin TV 可进入服务器连接流程；
- Moonlight 可发现或手动添加 Sunshine；
- AnExplorer 可浏览内置存储/USB，并能选择本地 APK；
- 打开 AirReceiverLite 后，iPhone 可发现电视，镜像、声音和同步正常。

Kodi、Jellyfin 和 Moonlight 因发布验收时缺少本地媒体、Jellyfin 服务器和
Sunshine 主机，只验证到界面与连接/发现边界，属于已记录的有限豁免，不代表
端到端播放已经测试。

## 7. 故障定位

- `adb connect` 失败：确认电视 IP、`7896` 端口、同一局域网，并重试连接。
- 脚本报告 baseline mismatch：停止安装；很可能刷入了 Test9r1/Test9r2
  或其他镜像，不要用参数绕过合同。
- 找不到 `aapt`/`apksigner`/Java：安装 Android SDK Build Tools 和 Java 17，
  或用对应命令行参数给出路径。
- Play Store 显示 not compatible：先确认脚本的 Test8r2 合同已通过；
  不要通过加入 Leanback、混装 Google APK 或伪造设备身份规避。
- APK 下载或校验失败：保留错误信息并重试网络；不要改用随机 APK 镜像站。

M7 的验收边界和历史实验结论见
`docs/archive/m7/M7_COMPLETION_REPORT.md`。Play Store 电视化、GMS/认证、
官方手机遥控产品化和 64 位系统均属于 M8，不重新打开 M7。
