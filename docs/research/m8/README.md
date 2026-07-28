# M8 研究索引

状态：`M8.0 PLANNED`。当前只建立研究合同，不下载 BSP/AOSP，不制作 64 位候选。

## 输入

| 输入 | 用途 | Git 策略 |
|---|---|---|
| 官方 `x12-1024.img` | 唯一恢复源、分区和安全状态基线 | 不提交 |
| Test8r2 最终镜像与配置 | 当前稳定行为和文件系统基线 | 镜像不提交，配置提交 |
| Test9r1 donor/构建/真机证据 | M8.INPUT remoteprovider、RRO、权限、发现/配对合同 | Google APK 不提交，只提交哈希、脚本和脱敏结论 |
| ADB/UART 只读输出 | service/HAL/module/DRM 运行时状态 | 只提交脱敏报告 |
| BPI H618 BSP | 供体能力审计 | 大型源码放 WSL/独立盘，只提交 source-lock 和报告 |
| Android 12 AOSP ATV | 产品定义参考 | 构建树不提交，只提交差异报告 |

## 计划交付物

```text
docs/research/m8/
├── README.md
├── current-device/
│   ├── elf-inventory.csv
│   ├── elf-dependency-summary.md
│   ├── hal-inventory.json
│   ├── kernel-module-inventory.csv
│   ├── graphics-stack.md
│   ├── media-stack.md
│   ├── wifi-bt-stack.md
│   └── arm64-blockers.md
├── bpi-h618/
│   ├── source-lock.md
│   ├── download-manifest.txt
│   ├── build-environment.md
│   └── donor-verdict.md
├── aosp-atv12/
│   ├── source-lock.md
│   ├── product-package-diff.md
│   ├── overlay-diff.md
│   ├── remote-input-component-map.md
│   └── ubox10-atv-product-plan.md
├── remote-input/
│   ├── test9r1-verdict.md
│   ├── framework-provider-contract.md
│   └── iphone-google-tv-acceptance.md
└── drm-netflix/
    ├── collection-plan.md
    ├── widevine-report.md
    ├── drm-service-inventory.md
    ├── secure-codec-inventory.csv
    ├── hdcp-status.md
    └── netflix-feasibility-verdict.md
```

目录在产生真实交付物时创建，不用空 `.gitkeep` 占位。

## 数据边界

- 不提交账号、token、Cookie、完整设备证书、密钥、ESN、完整唯一标识、完整 BSSID/MAC 或 Wi‑Fi 密码。
- DRM 报告只保留 security level、接口版本、服务/文件路径、是否 provisioned 等结论；System ID 若具有唯一性，只保留是否存在或经脱敏形式。
- 闭源 Vendor blob、Google proprietary package、TEE/HDCP/Widevine 材料和大型构建产物不进入 Git。
- 供体结论必须明确区分“仓库声称”“ELF/产物证明”和“UBOX10 真机证明”。

## 第一批工作

1. ELF inventory 工具及小型 fixture。
2. Test8r2 当前设备图形/媒体/Wi‑Fi-BT 只读报告。
3. BPI H618 commit/oversized files/构建环境 source-lock；用户确认前不下载。
4. 将 Test9r1 的 AOSP remoteprovider、provider package RRO、权限和真机结论
   写入 M8.INPUT component map；不开发 UBOX Input。
5. M8.DRM-0 采集设计；原厂 ROM 与 Test8r2 必须分别记录，不能用一方推断另一方。

架构、阶段和退出条件见 `docs/architecture/M8_ARM64_AOSP_TV_MIGRATION.md`。
