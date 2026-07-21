# 里程碑

- [x] **M0：原始镜像基线** — 记录身份、建立仓库与风险控制。
- [x] **M1：只读容器清单** — 解析 PhoenixCard 条目、偏移、大小、CRC/哈希；不提取、不改写。
- [x] **M2：分区与启动链审计** — 提取副本并分析 boot/vendor_boot/dtbo/vbmeta/super 与 A/B 语义。
- [x] **M3：系统行为归因** — APK、init、属性、SELinux、网络路径的证据图谱。
- [/] **M4：ROM 重打包与 AVB 签名** — 离线编译完成；ext4 语义保真、AVB 根信任及运行时加载待验证。
- [/] **M5：固件封装与一致性验证** — 容器重打包和伴生校验和通过；端到端 Android 启动待验证。
- [/] **M6a：无修改启动链取证** — Fastboot 协议与其只读变量能力已确认；待 UART 冷启动日志与 Recovery/slot/BCB 假设确认。
- [ ] **M6b：零内容改动重建对照** — PhoenixCard、super、System ext4 逐层 round-trip；依赖 M6a。
- [ ] **M6c：最小变更回归** — 每次仅验证一个删除、属性变更或 APK 预装；先以 manifest 确认 Projectivy 与目标应用的来源、许可证和分区归属；依赖 M6b。
- [ ] **M7：候选发布** — 可复现构建、合法组件处理说明、发行说明、回滚包和完整硬件/网络功能矩阵。
