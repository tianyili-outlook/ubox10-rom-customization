# Widevine 基线

采集：2026-07-30，Test8r2。

| 项目 | 结果 |
|---|---|
| scheme | supported，MediaDrm 可打开 |
| 实现 | Google Widevine CDM `16.1.0` |
| security level | `L3` |
| container | MP4、WebM、audio MP4 均报告支持 |
| System ID | 存在；值未记录 |
| session | 采集时 0，上限 16；探针未打开 session |
| secure decoder | AVC、HEVC、VP9 均为 `false` |

结论：Test8r2 的 Widevine 不是“只有文件”，而是可由 framework 实际打开；
但当前只证明 L3 软件保护路径，不支持宣称 L1、Netflix HD 或 4K。

ClearKey 1.2 同样可打开，属于功能对照，不改变 Widevine 结论。
