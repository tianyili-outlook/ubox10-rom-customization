# 固件基线

| 字段 | 值 |
|---|---|
| 文件 | `x12-1024.img` |
| 大小 | 2,018,890,752 bytes |
| SHA-256 | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |
| 文件头（ASCII） | `IMAGEWTY` |
| 容器判断 | 已确认：Allwinner IMAGEWTY v3 / PhoenixCard 容器 |
| 容器目录 | 已由 `work/manifest.json` 解析；下载映射见 `firmware/extracted/sys_partition.fex` |
| 采集日期 | 2026-07-19 |

该记录确认原件身份和容器格式。官方镜像同时是 PhoenixCard 恢复入口、IMAGEWTY 封装模板和全部候选的唯一来源，不能因空间清理而删除。

当前另保留：

- Test8r2 稳定基线：`6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8`
- Test9w1 实验候选：`2D43D4A6B64702F1D0265EDC27B33EB424B4B56A721DC8068B5CCEBB4A310CC5`

其他逻辑分区和候选镜像属于可再生成缓存。执行 `python scripts/prepare-candidate-inputs.py` 可从官方原件恢复四个构建分区及语义清单；候选再由配置驱动构建器复现。完整保留集见 `STORAGE_AND_REPRODUCTION.md`。

设备侧 USB、启动与候选结果记录于 `DISCOVERIES.md`；早期 M6 调试记录已归档到 `archive/m6/M6_DEBUG_LOG.md`。
