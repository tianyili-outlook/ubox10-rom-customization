# M8 研究索引

状态：`M8.0 READY`。Test9r2 runtime 证据和近期路线决策已经闭合；当前可开始
只读 inventory 与 source-lock，但不下载大型 BSP/AOSP、不混装 Google 专有
组件、不制作 M8 候选。

M8 执行顺序为：

```text
M8.0 共享证据门
  → M8A ARM32 真正 Android 12 AOSP ATV product
  → M8B AArch64/multilib
```

M8.GMS、M8.INPUT 和 M8.DRM 是横向门禁。详细路线见
`docs/architecture/M8_ARM64_AOSP_TV_MIGRATION.md`；TV GMS 与 Remote 参考
项目见 `docs/research/tv-gms-remote/README.md`。

## 输入

| 输入 | 用途 | Git 策略 |
|---|---|---|
| 官方 `x12-1024.img` | 唯一恢复源、分区和安全状态基线 | 不提交 |
| Test8r2 最终镜像与配置 | 当前稳定行为、文件系统与 32 位 vendor 基线 | 镜像不提交，配置提交 |
| Test9r1/Test9r2 donor、构建与真机证据 | remoteprovider、RRO、权限、Play/GMS 和发现/配对合同 | Google APK 不提交；只提交哈希、脚本和脱敏结论 |
| ADB/UART 只读输出 | service/HAL/module/DRM 运行时状态 | 只提交脱敏报告 |
| Android 12 AOSP ATV | M8A product 与 M8B 对照基准 | 构建树不提交；锁定 commit 和差异报告 |
| MindTheGapps TV | M8.GMS 组件、权限、overlay 与打包结构参考 | 不复制未验证专有二进制 |
| BPI H618 BSP | M8B 64 位供体能力审计 | 大型源码放 WSL/独立盘，只提交 source-lock 和报告 |

## 计划交付物

目录只在产生真实交付物时创建，不用空 `.gitkeep` 占位：

```text
docs/research/m8/
├─ current-device/
│  ├─ elf-inventory.csv
│  ├─ elf-dependency-summary.md
│  ├─ hal-inventory.json
│  ├─ kernel-module-inventory.csv
│  ├─ graphics-stack.md
│  ├─ media-stack.md
│  ├─ wifi-bt-stack.md
│  └─ arm64-blockers.md
├─ m8a-atv-arm32/
│  ├─ source-lock.md
│  ├─ product-package-diff.md
│  ├─ overlay-permission-vintf-diff.md
│  ├─ partition-budget.md
│  └─ ubox10-atv-product-plan.md
├─ m8b-arm64/
│  ├─ bpi-h618-source-lock.md
│  ├─ download-manifest.txt
│  ├─ build-environment.md
│  ├─ donor-verdict.md
│  └─ minimal-boot-plan.md
├─ remote-input/
│  ├─ framework-provider-contract.md
│  └─ iphone-google-tv-acceptance.md
└─ drm-netflix/
   ├─ collection-plan.md
   ├─ widevine-report.md
   ├─ drm-service-inventory.md
   ├─ secure-codec-inventory.csv
   ├─ hdcp-status.md
   └─ netflix-feasibility-verdict.md
```

Test9r2 runtime 与近期路线决策已放在
`docs/research/tv-gms-remote/`。官方客户端已经通过，不创建无必要的
receiver-client matrix；TV GMS gap 与原生 remote product contract 转入
M8.GMS/M8.INPUT 交付物。

## 数据边界

- 不提交账号、token、Cookie、完整设备证书、密钥、ESN、完整唯一标识、
  完整 BSSID/MAC 或 Wi‑Fi 密码。
- DRM 报告只保留 security level、接口版本、服务/文件路径、是否 provisioned
  等结论；System ID 若具有唯一性，只记录是否存在或脱敏形式。
- 闭源 Vendor blob、Google proprietary package、TEE/HDCP/Widevine 材料和
  大型构建产物不进入 Git。
- 供体结论必须区分“仓库声明”“ELF/产物证明”和“UBOX10 真机证明”。
- 外部项目进入实验前记录 URL、branch/tag/commit、许可证、版本/ABI/签名、
  构建方式和输入哈希。

## 第一批工作

1. 编写 ELF inventory 工具与小型 fixture；
2. 生成 Test8r2 图形、媒体、Wi‑Fi/BT、HAL/VINTF 和 Kernel module 只读报告；
3. 锁定 Android 12 `device/google/atv` commit，形成 M8A.1 差异合同；
4. 形成 M8.INPUT provider contract，继承 Test9r2 已证实的 system_ext RRO、
   最小 `BLUETOOTH_CONNECT`、Remote v2、uinput 与官方 iPhone 验收；
5. 形成 TV GMS component gap，单列 Play package visibility 与 Google API；
6. 形成 BPI H618 M8B.1 source-lock；用户确认前不下载；
7. 设计原厂/Test8r2 M8.DRM-0 采集；
8. 不开发 UBOX Input，不以 ADB/Web remote 代替官方 M8.INPUT 验收。
