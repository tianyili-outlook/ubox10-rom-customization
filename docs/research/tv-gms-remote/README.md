# TV GMS、手机遥控与文字输入参考项目

研究快照：2026-07-29。本文是 Test9r2 之后与 M8 共用的参考索引和决策门，
不代表已取得 Google TV/GMS TV 授权、Play Protect 认证或可直接使用的
Android 12 专有二进制。

## 1. 当前问题模型

当前固件不是一致的 Android TV 产品：

- Test8r2 是手机取向的 32 位 Google stack，加上电视 UI、Projectivy 和部分
  TV feature；Play Store 可登录、搜索和安装部分 TV 应用，但首页失败且界面
  不适合遥控器。
- Android 12 `SystemServer` 只在 `FEATURE_LEANBACK` 存在时启动
  `TvRemoteService`。
- Test9a/Test9b/Test9r1 加入 leanback 后，当前 Play Store 进入
  `AccessRestrictedActivity`。
- Test9r1 证明 remoteprovider、Remote Service APK 和权限可以被加载，但
  RRO 不在实际扫描路径，provider 未获白名单，端口未监听。
- Test9r2 已证明 RRO 修正后完整 Remote v2 技术链可工作：初始服务只因缺少
  `BLUETOOTH_CONNECT` 运行时授权崩溃；临时授予这一项后，6466/6467、
  mDNS、官方 iPhone TLS 配对、遥控和文字输入全部通过。Play Store 仍进入
  `AccessRestrictedActivity`，Store “missing”/Google API 警告继续存在但
  没有阻止本地遥控。

结论：receiver/protocol 可行性已证实，但当前手机 GMS、TV feature 与 TV
专有 APK 仍不是一致产品。已选择 S3 收束 32 位 remote，不再制作下一个
Test9/Test10 remote 候选；产品化转入 M8.INPUT/M8.GMS。

## 2. Test9r2 证据结果

Test9r2 已按以下层级完成报告，采证中没有制作新镜像：

1. `RRO`：package path、`overlay list`、enabled state、framework resource
   lookup。
2. `FRAMEWORK`：`TvRemoteService` 启动、provider watcher 选择/拒绝原因、
   shared library 和 privileged permission。
3. `RECEIVER`：Remote Service 进程、崩溃、Google API/Play Store 依赖日志、
   6466/6467 监听。
4. `DISCOVERY`：mDNS 广播、同 LAN 可见性、设备名。
5. `CLIENT`：官方 Google TV iOS 应用发现、配对、按键、文字输入和重启复验。
6. `REGRESSION`：Play Store、Projectivy、Settings、实体遥控、Wi‑Fi、蓝牙。

实际结果：

| 层级 | 结果 | 关键证据 |
|---|---|---|
| RRO | PASS | system_ext RRO 生效，lookup 返回 Remote Service package |
| FRAMEWORK | PASS | provider 绑定，shared library 与 uinput bridge 正常 |
| RECEIVER 初始状态 | FAIL | 缺 `BLUETOOTH_CONNECT`，主进程崩溃 |
| RECEIVER 最小权限后 | PASS | 只授予 CONNECT；SCAN/ADVERTISE 仍为 false |
| DISCOVERY | PASS | 6466/6467 与 `_androidtvremote2._tcp` |
| CLIENT | PASS | 官方 Google TV iPhone 配对、遥控、文字输入 |
| REGRESSION | PARTIAL | Play Store not compatible；重启 remote 未复验 |

按证据分类：

| 结果 | 含义 | 下一动作 |
|---|---|---|
| `R2-REMOTE-PASS` | provider、接收端、发现、配对和输入均通过 | **本次实际分类**；技术证据转入 M8.INPUT |
| `R2-CLIENT-FAIL` | 6466/6467 与接收端正常，但官方 iOS 客户端失败 | 用 Python/Swift v2 客户端区分 mDNS、协议和官方客户端问题 |
| `R2-GOOGLE-FAIL` | RRO/provider 正常，但接收端因 Play/GMS 依赖失败 | 停止 Test9r3，先完成 TV GMS 组件差距报告 |
| `R2-PLATFORM-FAIL` | RRO、lookup、watcher 或 shared library 仍失败 | 只修正对应平台层，不同时改变 GMS、身份或网络 |

无论分类为何，Test9r2 因已知 Play Store 回归都不能晋级为日常基线；采证后
回到 Test8r2。完整证据见
[test9r2-runtime-report.md](test9r2-runtime-report.md)。

## 3. Test9r2 后路线选择

已选择 `S3 / 结束 32 位 remote 实验`。S1/S2 保留为历史评估，不再在 M7
执行。完整依据见 [route-decision.md](route-decision.md)。

### 路线 S1：Test9r3，保留 Test8r2 Google stack（未选择）

仅当 `R2-REMOTE-PASS` 且 framework 修改能从锁定 Android 12 源码精确复现时
进入：

- 从 Test8r2 构筑；
- 不声明 leanback，保留 Test8r2 的 Play Store 行为；
- 只定点改变 `TvRemoteService` 的启动 gate；
- 复用已验证的 remoteprovider、RRO、最小权限和本地原签名 donor；
- 不同时改变 Play Store/GMS、设备身份、Wi‑Fi、蓝牙或 vendor 分区。

Test9r2 已证明接收端即使出现 Google API/Play Store 警告仍可完成本地
Remote v2；但 S3 已选择，因此不再制作 Test9r3。

### 路线 S2：Android 12 ARM32 一致的 TV product/GMS 实验（未选择）

仅当能锁定合法来源、精确 Android 12、ARM32、签名与依赖闭合的 TV 组件集合
时进入，候选暂定为 Test10p1：

- 先完成 package、shared library、permission、overlay、property、SELinux、
  Setup/Provision、Play Store、GMSCore 与 Remote Service 组件差距报告；
- 将 AOSP ATV product 与 Google 专有层分开验收；
- Google 专有二进制只允许用户本地提供，不进 Git、不公开下载、不再分发；
- 不用 model/fingerprint 欺骗、签名伪造或认证绕过制造“兼容”结果。

若不存在可审计的 Android 12 ARM32 TV 专有组件集合，这条路线记为
`BLOCKED`，不从较新 MindTheGapps 分支复制二进制。

### 路线 S3：结束 32 位 remote 实验（已选择）

当前执行：

- Test8r2 继续作为稳定基线；
- Test9.3 只完成应用、AirPlay、文件管理和整体回归；
- 官方 Google TV 手机遥控目标转入 M8.INPUT；
- 蓝牙键盘可以作为用户回退，但不算项目目标通过。

该选择已经关闭近期 S1/S2；不能再把 framework gate、全套 GMS、身份和网络
修改混入同一 M7 候选。

## 4. M8 路线收敛

M8 改为先产品、后架构：

```text
M8.0 共享证据门
  ├─ M8A：保留当前 32 位 Kernel/vendor/ABI，建立真正 Android 12 AOSP ATV product
  │    └─ M8.GMS / M8.INPUT：以独立门禁验证 TV GMS 与官方手机遥控
  └─ M8B：在 M8A 产品合同稳定后迁移 AArch64/multilib
       └─ 第一硬门槛仍是兼容 H616/Mali-G31 的 64 位图形栈
```

这样先验证“电视产品定义是否正确”，再验证“64 位硬件栈是否可行”，避免在
一个候选中同时调试 product、GMS、ABI、图形和 Vendor。

## 5. 参考项目目录

### 5.1 AOSP `device/google/atv`

- 地址：<https://android.googlesource.com/device/google/atv/>
- Android 12 分支：
  <https://android.googlesource.com/device/google/atv/+/refs/heads/android12-release/>
- 价值：Android TV product inheritance、`aosp_tv_arm`/`aosp_tv_arm64`、
  feature、package、overlay 和产品拆分的权威基准。
- 用法：锁定 Android 12 commit 后做 M8A product/package/overlay 差异，
  不使用当前 `main` 代替 Android 12。
- 边界：AOSP ATV 不包含 Google TV 商业认证，也不保证 TV Play Store、
  Play Protect 或 Netflix 分发资格。

### 5.2 AOSP TV remote framework

- `remoteprovider`：
  <https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-12.0.0_r1/media/lib/tvremote/>
- `SystemServer`：
  <https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-12.0.0_r1/services/java/com/android/server/SystemServer.java>
- 价值：shared library、provider watcher、Binder/uinput 合同和 leanback
  启动 gate 的权威来源。
- 用法：M8A 原生源码集成；任何 patch 必须保存源码
  tag、最小 diff、构建方式和产物哈希。

### 5.3 MindTheGapps TV

- 新分支仓库：<https://github.com/MindTheGapps/vendor_gapps_tv>
- 历史/Android 15 `vic` 仓库：
  <https://gitlab.com/MindTheGapps/vendor_gapps_tv>
- 价值：ARM/ARM64 分层、common/overlay、proprietary file list、privapp/
  default permission 与内联构建结构，可用来建立 TV GMS 组件清单。
- 用法：只借鉴组件分类、依赖关系、权限/overlay 和可复现打包方法。
- 边界：当前可见分支面向比 Android 12 更新的平台，尚未证明存在适合本机的
  Android 12 ARM32 完整集合；不得把较新 APK/库直接当作 Test10p1 donor。

### 5.4 `tronikos/androidtvremote2`

- 地址：<https://github.com/tronikos/androidtvremote2>
- 许可证：Apache-2.0。
- 价值：Python 实现 Android TV Remote protocol v2；与 Google TV 手机应用
  使用同类协议，不依赖 ADB，但要求电视端已有 Remote Service。
- 用法：在 `R2-CLIENT-FAIL` 时作为协议级诊断客户端，验证配对、按键、URL
  与语音消息；锁定 release/commit 后再写自动化。
- 边界：它是客户端库，不提供电视端 receiver，不能修复缺失的 system/GMS
  组件。

### 5.5 `odyshewroman/AndroidTVRemoteControl`

- 地址：<https://github.com/odyshewroman/AndroidTVRemoteControl>
- 许可证：MIT；README 声明 iOS 13+、Swift 4+、Remote protocol v2。
- 价值：在 iPhone 上独立复现 TLS、配对码和遥控流程，区分“官方 Google TV
  应用问题”与“电视 receiver/protocol 问题”。
- 用法：只做诊断 App/测试夹具；使用前审查证书持久化、信任处理、密钥存储
  和后台网络行为。
- 边界：同样不是电视端 receiver，也不替代官方 Google TV 应用的最终验收。

### 5.6 `Legvan/tv-remote`

- 地址：<https://github.com/Legvan/tv-remote>
- 许可证：MIT。
- 价值：展示 ADB over TCP、网页遥控、ASCII 文字输入、设备发现和 on-device
  Web 服务的备选实现。
- 当前不采用：上游桌面服务默认绑定 `0.0.0.0`，on-device 方案向 LAN 开放
  8080，并通过 ADB/loopback 注入；其 CLI 还提供 raw shell 能力，文字输入
  只保证 ASCII。这与本项目的配对认证、Unicode、最小权限和不扩大 ADB
  攻击面的门槛不一致。
- 仅在官方 Remote v2 路线确认 `BLOCKED` 后重新评估；任何衍生方案必须先
  保证 CLI raw shell 不向 LAN API 暴露、加入强认证/配对和 CSRF 防护、限制
  绑定地址、隔离 ADB key、审计 SELinux/启动行为，并证明未配对 LAN 客户端
  不能注入事件。

## 6. 参考项目使用规则

每个外部项目进入实验前必须记录：

1. 上游 URL、branch/tag/commit、许可证和检查日期；
2. Android 版本、ABI、最低 SDK、package、签名和所需 shared library；
3. product property/feature、permission、overlay、SELinux 和 native library；
4. 网络端口、发现机制、认证、密钥存储与最小攻击面；
5. 可复现构建命令、输入哈希和本项目允许提交的产物；
6. “上游声明”“离线产物证据”“UBOX10 真机证据”三者分开记录。

Google 专有二进制、账号/token、设备证书、密钥和大型源码/构建产物不进入
Git。MindTheGapps 或其他项目的 proprietary file list 只能帮助盘点，不能
自动赋予专有文件的下载、使用或再分发权利。

## 7. 已完成交付物与 M8 移交

当前目录已有真实证据：

```text
docs/research/tv-gms-remote/
├─ README.md
├─ test9r2-runtime-report.md
└─ route-decision.md
```

官方 iOS 客户端已经通过，因此不创建无必要的 receiver-client matrix。
S3 已选择，因此 M7 不再创建 framework startup gate 报告，也不制作
Test9r3/Test10p1。TV GMS component gap、原生 default-permissions 和
framework/provider product 合同转入 M8.GMS/M8.INPUT 交付物。
