# Netflix 可行性

| 等级 | Test8r2 状态 | 原因 |
|---|---|---|
| N0 能力审计 | `PARTIAL` | Widevine/codec/HDCP 已知；官方 ROM、Play Protect、Netflix App 和实际播放未测 |
| N1 基础播放 | `UNKNOWN` | L3 可能支持基础受保护播放，但必须用本人账号实测 |
| N2 HD | `BLOCKED` | Widevine L3、HDCP NONE、无 secure decoder |
| N3 4K/HDR | `BLOCKED` | N2 未通过 |

当前合理目标是先验证 N1；没有证据支持 Netflix HD/4K。M8A 可继续做产品层
工作，但第一次刷写前应保留本报告并补官方 ROM 对照。
