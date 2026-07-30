# M8 恢复与实验运行手册

## 稳定恢复点

- 官方 `x12-1024.img`：最终恢复源和 IMAGEWTY 模板。
- Test8r2：日常稳定基线，也是 M8 candidate 的默认回退点。

两份镜像的路径、大小和必要校验值只在
[FIRMWARE_BASELINE.md](FIRMWARE_BASELINE.md) 与
[STORAGE_AND_REPRODUCTION.md](STORAGE_AND_REPRODUCTION.md) 维护。

## 刷写前

1. candidate 已在 [m8/CANDIDATES.md](m8/CANDIDATES.md) 记录基线、单一主要
   变量和预期结果。
2. 确认官方镜像、Test8r2 和 PhoenixCard 4.2.7 可用。
3. 只在确认目标 TF 卡后制作 Product 模式刷机卡。
4. 不同时改变 Kernel、Vendor、System、DTB、TEE。
5. 不触碰 Widevine、TEE、HDCP、keybox 或设备证书。
6. 如需保留 userdata，先人工备份；刷机可能清除 userdata/metadata。

## 刷写后

先看用户可见结果，再抓最小证据：

1. HDMI 是否出画；
2. UART 是否重复出现同一 fatal；
3. ADB 是否出现；
4. Launcher / Settings 是否可进入；
5. 实体遥控、网络、音频和代表性视频；
6. 只抓本轮相关的 service、linker、VINTF、SELinux 或 tombstone。

常用只读入口：

```powershell
.\scripts\capture-m8-runtime-readonly.ps1 -Device "<电视IP>:7896"
.\scripts\capture-uart-readonly.ps1
```

UART 接线、参数和采集细节见 [UART_RUNBOOK.md](UART_RUNBOOK.md)。

## 故障归因

记录：

```text
Candidate:
Last visible state:
First repeated fatal:
Affected layer:
Difference from base:
Next single fix:
```

一次只修一个原因。linker namespace、VINTF/HAL、SELinux denial、overlay、
provision 和默认 HOME 问题都允许在首次刷机后定位；能稳定回退时，不为完整
预审长期阻塞实验。

## 回退

1. 断电并插入已确认的 PhoenixCard 恢复卡。
2. 优先刷回 Test8r2；若它不能恢复，再使用官方镜像。
3. 恢复后验证 HDMI、Projectivy/Home、Settings、实体遥控、Wi‑Fi、音频和
   蓝牙。
4. 若设备无显示或循环重启，先保留 UART 日志，不修改更多分区后再重试。

旧 Test9r2 刷回 Test8r2 的完整实例保存在
[archive/m8/pre-pragmatic/RUNBOOK.md](archive/m8/pre-pragmatic/RUNBOOK.md)；
它是历史记录，不是当前阶段入口。
