# M8 社区参考

核验日期：2026-07-30。下列项目只用于读取结构、补丁思路或诊断方法；没有
任何社区 GSI、GApps 包或通用 workaround 被视为可直接刷入 UBOX10 的方案。

| Project | Relevant M8 stage | What to borrow | What not to copy | Reference URL |
|---|---|---|---|---|
| AOSP `device/google/atv` | M8A.1–M8A.3 | Android 12 ARM TV product 继承、TV package、permission、overlay 分层 | emulator/goldfish/generic_x86 硬件层；未经 UBOX 验证的整套 product | [android12-release](https://android.googlesource.com/device/google/atv/+/refs/heads/android12-release/) |
| MindTheGapps TV | M8.GMS | TV Google 组件分类、priv-app/permission/overlay 与打包结构 | 专有 APK、签名、认证声明；不能整包当作 UBOX candidate | [vendor_gapps_tv](https://github.com/MindTheGapps/vendor_gapps_tv) |
| TrebleDroid `device_phh_treble` / `treble_experimentations` | M8A 启动故障；M8B 供体评估 | 旧 Vendor + 新 Framework 的问题分类、可定位的兼容补丁思路 | 通用 GSI、全局属性伪装、大批未归因 workaround | [device_phh_treble](https://github.com/TrebleDroid/device_phh_treble) / [treble_experimentations](https://github.com/TrebleDroid/treble_experimentations) |
| PHH Treble Experimentations（旧仓库） | 历史兼容性研究 | 查旧补丁来源和讨论背景 | 作为当前上游依赖；该仓库已归档，应优先看 TrebleDroid | [phhusson/treble_experimentations](https://github.com/phhusson/treble_experimentations) |
| TrebleDroid `vendor_hardware_overlay` | M8A.2c–M8A.3 | overlay 按硬件条件组织、匹配和最小覆盖的方式 | 与 UBOX 无关的手机 overlay，或不验证资源名就批量复制 | [vendor_hardware_overlay](https://github.com/TrebleDroid/vendor_hardware_overlay) |
| LineageOS `android_device_google_atv` | M8A.3；后续 device tree | products/overlays/permissions/sepolicy/TvProvision 的 device-tree 布局 | 用当前 Lineage 分支替换已锁定 Android 12 ATV 来源；它不是 UBOX device tree | [android_device_google_atv](https://github.com/LineageOS/android_device_google_atv) |
| AOSP `system/linkerconfig` | M8A.2b；M8B | `/linkerconfig` 生成逻辑、namespace、APEX/vendor provide/require 库诊断 | 为绕过单一缺库而长期开放 namespace 或堆全局 public library | [android12-release](https://android.googlesource.com/platform/system/linkerconfig/+/refs/heads/android12-release/) |
| AOSP `check_elf_file.py` | M8A.2a；M8B 供体 | 对新增/替换 ELF 检查 DT_NEEDED、声明依赖和未解析符号；实际使用锁定 Android 12 源码树内版本 | 把全树零警告当作每个 candidate 的硬门禁 | [upstream tool](https://android.googlesource.com/platform/build/+/HEAD/tools/check_elf_file.py) |
| Android TV Remote Protocol v2 clients | M8.INPUT | 用 Python 客户端自动化协议测试；用 Swift 客户端区分 iPhone、mDNS、TLS/配对问题 | 把客户端误当成电视 receiver/provider，或取代官方 iPhone 体验验收 | [tronikos/androidtvremote2](https://github.com/tronikos/androidtvremote2) / [AndroidTVRemoteControl](https://github.com/odyshewroman/AndroidTVRemoteControl) |
| Legvan `tv-remote` | M8.INPUT fallback | 在开发期快速提供 LAN Web/ADB 遥控 | 作为原生 Remote v2、正式安全模型或无 ADB 的日常方案 | [Legvan/tv-remote](https://github.com/Legvan/tv-remote) |

使用外部补丁前只记录 URL、revision、实际借用点和本轮差异。只有进入可复现
构建输入时才增加 source-lock；普通阅读不额外制作哈希清单。
