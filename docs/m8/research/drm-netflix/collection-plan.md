# M8.DRM-0 采集计划

目标只区分实际能力，不导出密钥、证书、ESN、deviceUniqueId 或完整 System ID。

## 自动采集

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\run-m8-drm-probe.ps1 `
  -Device 192.168.1.5:7896 `
  -OutputFile logs/device/<date>-m8-<baseline>-drm-api.txt
```

脚本临时安装无权限调试 APK，读取 scheme、版本、security level、HDCP、
container support、secure-decoder requirement 和 session 上限后立即卸载。
它不打开 DRM session、不请求 license/provisioning，也不读取 deviceUniqueId；
System ID 只输出是否存在。

## 基线

| 基线 | 状态 |
|---|---|
| Test8r2 | API、service、codec、HDCP 已采集 |
| 官方 ROM | 待单独刷回后运行同一探针 |
| Netflix N1 | 待本人账号实际安装、登录和播放 |

当前不需要继续搜索互联网；官方 ROM 结果出来后再决定是否查具体 Widevine/
HDCP 实现问题。
