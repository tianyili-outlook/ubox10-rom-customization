# HDCP 状态

采集时 HDMI 已连接，Widevine MediaDrm 返回：

| 项目 | Test8r2 |
|---|---|
| connected HDCP | `NONE` |
| max HDCP | `NONE` |

内核存在 `hdcp22_workqueue`，display 也声明 secure/protected-buffer flag；这些
只说明代码或图形能力存在，不能覆盖 MediaDrm 的实际 `NONE` 结果。
