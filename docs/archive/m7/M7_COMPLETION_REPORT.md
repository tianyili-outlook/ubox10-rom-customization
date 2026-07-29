# M7 Android TV 产品化完成报告

状态：`COMPLETE`

日期：2026-07-29

## 最终结论

M7 以 Test8r2 为唯一稳定固件基线完成。Launcher、英语界面、遥控器、
Settings、HDMI、Wi‑Fi、蓝牙和 ContactsProvider/PBAP 保持稳定；五项
userdata 应用完成来源锁、统一安装、启动、D-pad、重启持久性与人工体验门。
AirReceiverLite 完成 iPhone 发现、镜像、HDMI 音频和同步实测。

Test9w1 未证明 Wi‑Fi 改善并已退役；Test9r1 因 RRO 路径失败，Test9r2
Remote v2 技术链通过但因 Play Store 回归不晋级。后续固件仍从 Test8r2
构筑，Google TV 手机遥控产品化由 M8.INPUT 继承。

## 最终验收

| 项目 | 结果 | 证据边界 |
|---|---|---|
| Projectivy | PASS | 五个新图标可见；滚动、打开和焦点正常 |
| 五项通用遥控 | PASS | 方向、OK、Back、Home 可用，不要求鼠标模式 |
| SmartTube 32.03 | PASS | 浏览并播放 1080p，声音和返回正常 |
| Kodi 21.3 | PASS-WAIVER | 界面与遥控通过；缺本地媒体，未做播放 |
| Jellyfin TV 0.19.9 | PASS-WAIVER | 进入服务器连接流程；缺服务器，未做播放 |
| Moonlight 12.1 | PASS-WAIVER | 可发现/手动添加 Sunshine；缺主机，未做串流 |
| AnExplorer TV 6.0.5 | PASS | 存储授权、内置存储、USB、本地 APK 路径通过 |
| AirReceiverLite 5.1.7 | PASS-SCOPED | iPhone 镜像/音频/同步通过；接受 Lite 前台与五分钟限制 |
| 系统回归 | PASS | Projectivy、HDMI、遥控、Settings、Wi‑Fi、蓝牙无可见回归 |

Kodi、Jellyfin 和 Moonlight 的端到端内容测试因缺少外部资源而豁免，不代表
已经验证其全部媒体路径。SmartTube、AirReceiverLite 和 AnExplorer 已分别
覆盖真实网络媒体、实时音视频与 USB/本地文件路径；因此这些有限豁免不阻塞
M7。未来具备对应资源时可做非阻塞扩展复测，不重新开启里程碑。

发布收束时再次运行了五项 APK 的真实来源锁验证，并在
`192.168.1.5:7896` 对当前设备执行只读 `--dry-run`；SDK 31、ARMv7、
television feature、Projectivy HOME、ContactsProvider、Play Store、
禁止的 leanback/Remote Service 以及五项 ABI 合同全部通过。
最终再实跑 `--guided-after-flash`：脚本识别 AirReceiverLite 5.1.7
已安装并自动跳过 Play 交互，五项应用全部返回 `already-current`，发布报告
成功写入 Git 忽略的 `work/test9.3-guided-install.json`。

## AirPlay 范围决定

AirReceiverLite 的协议与性能已通过。真实重启确认 Lite 不会自动恢复服务，
且应用明确说明必须保持前台、部分功能每次会话限 5 分钟。用户决定不把购买
完整版 AirReceiver 纳入当前项目，因此：

- M7 接受 Lite 为按需前台 AirPlay 能力；
- M7 不承诺后台接收、开机自启或无限会话；
- 不转测含广告/内购的 AirScreen；
- 不导出、修改、破解或再分发任何付费 APK。

## 刷机后恢复流程

推荐使用一个交互式入口完成 Play 登录与本地应用统一安装：

```powershell
python .\scripts\install-userdata-apps.py `
  --guided-after-flash `
  --device "<电视IP>:7896"
```

流程固定为：

1. 刷入 Test8r2，完成网络连接；
2. 脚本从锁定官方地址取得缺失 APK，并验证 Test8r2 合同与五项来源锁；
3. 脚本直接打开 AirReceiverLite 的 Play Store 页面；
4. 用户登录 Play Store；出现 `Complete account setup` 时选择
   `Skip`/`Not now`，无需绑定信用卡；
5. 用户从 Play 安装免费 AirReceiverLite，返回终端按 Enter；
6. 脚本确认 Lite 已安装，再统一安装 SmartTube、Kodi、Jellyfin TV、
   Moonlight 和 AnExplorer，并写入忽略的本地报告；
7. 在 Projectivy 中首次打开 AirReceiverLite，按界面提示授予
   “显示在其他应用上层”权限。

该入口不保存 Google 账号或付款信息、不代购完整版，也不下载或重新分发
Play 专有 APK。第三方 APK 只进入 Git 忽略的 `work/`，并须通过完整性和
签名校验。非交互的 `--verify-only`、`--dry-run` 和默认安装模式继续
保留用于诊断与复现。

面向最终用户的完整刷机、工具准备、重建和故障定位见
[M7 发布与复现指南](../../M7_RELEASE_GUIDE.md)。

## 归档索引

- [Test9.3 用户态应用与详细证据](TEST9_3_USERDATA_APPS.md)
- [Test9r1 RRO 路径失败实验](TEST9R1_ANDROID_TV_REMOTE_SERVICE.md)
- [Test9r2 Remote v2 技术探针](TEST9R2_RRO_SCAN_PATH.md)
- [TV GMS/Remote 后续研究](../../research/tv-gms-remote/README.md)

## M8 交接

M7 不再接受新功能修改。后续工作进入 M8：

- M8.0：只读 ELF/HAL/VINTF/图形/媒体/DRM 证据；
- M8A：保持现有 Kernel/vendor/32 位 ABI，建立真正 Android 12 AOSP ATV；
- M8.INPUT：继承 Test9r2 的 Remote v2、最小 `BLUETOOTH_CONNECT` 与官方
  Google TV iPhone 证据；
- M8.GMS：解决 TV Play Store、package visibility、认证与设备身份一致性；
- M8B：只有 64 位 Mali/Gralloc/Mapper/HWC 证据通过后才进入 AArch64。
