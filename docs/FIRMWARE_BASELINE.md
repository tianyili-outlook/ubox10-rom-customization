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

Test9w1 已退役；Test9r1 因 RRO 扫描路径错误失败；Test9r2 的 remote 技术链
通过但 Play Store 回归，整机只为 `PARTIAL`。三者最终镜像均已删除。Test9r1
和 Test9r2 的配置、输入哈希、生成脚本、最终镜像 SHA-256 与历史结论仍可
复现；Test9r2 固定 SHA-256 为
`27B54FB83E96D3863FAE2EF2718E8EC9ADDD863E5ED123082D5E6C8CA6FFFD52`。

四个官方逻辑分区构建缓存长期保留，不再随候选清理；若缺失，执行
`python scripts/prepare-candidate-inputs.py` 可从官方原件恢复并验证。
Test9r1/Test9r2 的本地 donor/AOSP 输入由
`prepare-tv-remote-experiment.py` 验证和生成，候选再由配置驱动构建器
复现。完整保留集见 `STORAGE_AND_REPRODUCTION.md`。

设备侧 USB、启动与候选结果记录于 `DISCOVERIES.md`；早期 M6 调试记录已归档到 `archive/m6/M6_DEBUG_LOG.md`。
