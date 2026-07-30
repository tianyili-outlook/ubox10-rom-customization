# Candidate 索引

## 当前基线

| 项目 | 状态 | 用途 |
|---|---|---|
| 官方 `x12-1024.img` | RECOVERY | 最终恢复源与 IMAGEWTY 模板 |
| Test8r2 | STABLE | M7 稳定基线，也是所有 M8 实验的回退点 |
| M8 candidate | NONE | 尚未生成 |

只有基线镜像需要固定校验值；见
[FIRMWARE_BASELINE.md](../FIRMWARE_BASELINE.md)。普通日志和临时输出不额外
维护 SHA-256。

## 历史 candidate

| Candidate | 结果 | 记录 |
|---|---|---|
| Test1–Test7 | 历史增量链；Test7 实机通过 | [配置目录](../../configs/candidates/) / [CHANGELOG](../CHANGELOG.md) |
| Test8 | RETIRED；ContactsProvider/PBAP 导致蓝牙回归 | [配置](../../configs/candidates/test8-remove-vendor-home-wizard-cast.json) |
| Test8r2 | STABLE；恢复 ContactsProvider | [配置](../../configs/candidates/test8r2-restore-contacts-provider.json) |
| Test9a / Test9b | FAIL；Play Store 不兼容 | [历史验收](../archive/m8/pre-pragmatic/VALIDATION_PLAN.md) |
| Test9w1 | RETIRED；未证明 Wi-Fi 改善 | [历史验收](../archive/m8/pre-pragmatic/VALIDATION_PLAN.md) |
| Test9r1 | FAIL；RRO 扫描路径错误 | [报告](../archive/m7/TEST9R1_ANDROID_TV_REMOTE_SERVICE.md) |
| Test9r2 | PARTIAL；Remote v2 通过，Play Store 回归 | [报告](../archive/m7/TEST9R2_RRO_SCAN_PATH.md) |
| Test9.3 | PASS；M7 userdata 应用层，不是固件 candidate | [报告](../archive/m7/TEST9_3_USERDATA_APPS.md) |

`configs/candidates/` 保留可复现定义；淘汰镜像和中间产物无需保留。

## M8 记录格式

新 candidate 使用 `m8a-<阶段>-<目的>-rN`。首次记录只需：

```text
ID:
Base:
Single primary change:
Expected result:
Rollback:
Build/config:
Device result:
Status: DRAFT | BUILT | TESTING | PROMOTED | RETIRED
```

实机结果放在 `docs/m8/candidates/<ID>.md`；只有产生真实 candidate 时才创建
该目录和文件。

## 晋级

最低实测：

- 3 次冷启动；
- 5–10 次重启；
- 数小时正常使用；
- Launcher / Settings、实体遥控、网络、音频；
- 一种以上代表性视频播放；
- 回退仍可用。

启动基本可靠、日常体验可用、无关键回归、故障容易定位或回退且用户体验
优于前一基线，即可晋级。CTS/VTS、24 小时压力、完整 ABI 审计、SELinux
enforcing 和全警告清零不是每个 candidate 的要求。

同一 candidate 不同时修改 Kernel、Vendor、System、DTB、TEE，也不合并多个
独立高风险实验。完整边界见 [ARCHITECTURE.md](ARCHITECTURE.md)。
