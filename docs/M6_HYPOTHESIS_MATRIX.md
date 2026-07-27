# M6 启动失败假设矩阵

> 历史资料：用于解释旧候选启动失败；测试版 1 已改用官方分区直接修改路线。当前结论见 `DISCOVERIES.md`。

## 目的与证据边界

本表将“Android System 未启动”拆分为可证伪假设。它不用于挑选下一次刷写内容；被动 UART 冷启动日志现已取得，但在完成 `metadata` 初始化责任的离线审计前，所有候选镜像刷写仍暂停。

| ID | 假设 | 当前支持证据 | 当前反证/限制 | 最小下一证据 | 当前状态 |
|---|---|---|---|---|---|
| H-01 | BCB / `misc` 指示进入 Recovery | 历史上曾观察到 Recovery；离线 `misc.fex` 以零开始 | 当前 UART 先显示内核因 p20 ext4 失败请求 `reboot ... 'bootloader'`，随后才在第二次 U-Boot 出现 `bootmode[2]:0x5f`；这不支持 BCB/Recovery 是本次首个触发者 | 若以后需要解释历史 Recovery，仅读取或日志化 BCB 选择路径；当前不做设备操作 | 降为次要 |
| H-02 | 当前 A/B 槽位、slot-successful 或下载映射不匹配 | 离线 `sys_partition.fex` 倾向 a 槽，设备为 Android 12 A/B 动态分区 | Fastboot 槽位变量不支持；但当前日志已经进入内核并先失败于 p20，尚无槽位错误迹象 | p20 责任解决后，再依据启动日志审计槽位 | 暂缓 |
| H-03 | AVB 根信任、描述符或 hashtree/FEC 差异使 System 不可启动 | 原件与候选 vbmeta 公钥、算法和 FEC 存在离线差异 | 本次日志没有 AVB/dm-verity 拒绝，且内核已启动；`secure: yes` 仍不能证明 AVB 结果 | p20 通过后再以单变量零内容 AVB 对照和日志验证 | 暂缓但保留 |
| H-04 | super 内 ext4 重建丢失 symlink / ownership / SELinux xattr 或根目录层级等语义 | 提取器使用 `.symlink` 存根，当前重建未恢复元数据；U3.2 已确认候选 `system_a` 把官方 `/system` 子树扁平化到 ext4 根，且 D-0037 已确认 `repack-rom.py` 选择错误源根 | 这是候选离线缺陷，不证明该候选已装入设备，也不能单独解释 p20 本身为何没有 ext4 | M6b.0/M6b.1/M6b.2 设计已完成；经授权锁定 Linux oracle 并以真实 synthetic ext4 正反 fixture 验证完整语义解析。未通过前不修补脚本或生成候选 | 候选缺陷与本地构建根因已确认；运行时因果开放 |
| H-05 | init、挂载或 Framework 启动失败后转 Recovery/Fastboot | Android System 未进入；日志显示 `Kernel init done` 后 p20 ext4 失败，并在约 177 ms 后请求 bootloader 重启 | 没有 Android userspace/Framework 启动证据；AOSP Android 12 init 致命重启默认目标就是 bootloader，故该命令不能单独归因于 p20 或 U-Boot | U3.2 静态比对 init/reboot/fs_mgr 路径；如仍不足，再提出只读单变量日志方案 | 高优先级、部分支持 |
| H-06 | Fastboot 本身能够提供完整启动状态 | Fastboot 协议已验证，`product=sunxi`、`secure=yes` | userspace、slot-count、current-slot 与所有 has-slot 变量均不支持 | 不再扩展 Fastboot；使用 UART | 已否定为充分路径 |
| H-07 | `metadata`（p20）没有可识别 ext4，是重启前的关键早期失败条件 | UART 在 `Kernel init done` 后首先记录 `EXT4-fs (mmcblk0p20): VFS: Can't find ext4 filesystem`，约 177 ms 后 `reboot ... 'bootloader'`；fstab 指定 `/metadata` 为 ext4 | 不能从该报错判断分区是否全零、何时被擦除、谁应格式化，或单独证明它就是发起重启的调用者 | U3.2 离线核对 GPT、fstab、ramdisk 格式化能力、AOSP 语义和封装责任 | 早期失败信号已确认 |
| H-08 | `metadata` 的格式化责任在当前 PhoenixCard/启动链中未执行、被拒绝或执行时序不符合预期 | GPT/`sys_partition.fex` 声明 16 MiB metadata，但提取容器无 metadata 有效载荷，封装脚本也没有该映射；重新解包确认官方与当前候选 boot 都保留相同的 `mke2fs`、`e2fsdroid`、`libfs_mgr`、`init` 和 metadata fstab | 原始容器同样没有 metadata 文件，不能推断官方镜像必然有问题；工具/符号存在不等于本机 init 调用，且不能把 AOSP 的 `formattable` 当作本机实际格式化行为 | 完成候选容器来源审计，并追溯实际 logical system/init 代码；必要时仅离线生成控制样本 | 高优先级、开放 |
| H-09 | p20 错误后的 `bootloader` 重启是 init 致命路径的默认恢复，而非独立 bootloader 决策 | UART 显示内核 `reboot ... 'bootloader'` 后才出现第二次 U-Boot；AOSP Android 12 `init/reboot_utils.cpp` 的默认 fatal reboot target 为 bootloader；重新解包确认原件/候选 boot 的 `init` 二进制相同且含 `InitFatalReboot` | 未捕获到 init 的致命错误/栈或触发它的具体条件；厂商可改动该行为；二进制相同不等于设备实装该输入或运行到该路径 | 审计候选容器来源和逻辑 system 的 rc/服务，再决定是否需要更长的只读日志方案 | 高优先级、开放 |
| H-10 | 未挂载 `/metadata` 使 `apexd-bootstrap` 或同阶段服务失败并触发 bootloader 重启 | 工作树 APEXd/init 已归属官方 `system_a`；官方 `apexd.rc` 确有 `reboot_on_failure reboot,bootloader,bootstrap-apexd-failed`，`apexd` 含 `/metadata/apex/sessions` 字符串 | 重新解包的 boot/vendor_boot 不含这些文件；候选的相同内容位于根相对路径而非官方 `/system/...`；UART 没有 apexd/失败原因日志，不能证明服务已执行 | 候选已存在独立的 root-hierarchy 缺陷；先通过 M6b 真实 fixture 与官方只读语义基线，再重新评估启动时序与 `metadata` 假设 | 线索，未验证 |
| H-11 | 候选 `system_a` 的根目录层级错位使预期的 `/system/...` 路径不可用 | 候选根目录没有 `system`，但根相对的 `bin/init`、`bin/apexd`、`etc/init/*.rc` 等与官方 `system/...` 文件逐字节相同；D-0037 已证实 `make_ext4fs` 的源根选为 `work/system_extracted/system` | 尚未证明设备实际启动候选，也未证明具体 mount namespace/first-stage 路径或 p20 错误由此触发 | M6b 设计已完成；下一步以真实 synthetic fixture 验证完整层级/元数据解析，再建立官方零内容对照。不得只改路径后直接构建/刷写 | 候选离线缺陷与构建根因已确认；设备因果开放 |

## 当前决策

U2 已完成且信息增益耗尽，U3.1 被动 UART 也已完成。U3.2 已确认候选 boot/vendor_boot 的历史调试注入、候选容器来源、候选 super 的 `/system` 根层级错位，以及其直接本地构建根因：`repack-rom.py` 将 `work/system_extracted/system` 作为 `make_ext4fs` 的 system 源根。[M6b.0](M6B_ZERO_CONTENT_ROOT_HIERARCHY_CONTROL.md) 设计、M6b.1 JSON guard 和 [M6b.2 oracle 路线](M6B_EXT4_FIXTURE_ORACLE_DESIGN.md) 已完成。D-0043/D-0045/D-0046/D-0052/D-0054 已依次确认 CPU 能力、恢复准备、SVM 单变量、WSL/VMP Apply 和 B1 post-reboot/Ubuntu 环境；D-0055 已按 ADR-0011 锁定 Linux `e2fsprogs 1.47.2` 工具链。下一项是只使用项目自创内容的真实 synthetic ext4 fixture。它不是修改历史路径、不是生成 super，也不是设备侧实验；该工作仍不能替代设备分区读回，`metadata` 的格式化责任和 UART 重启调用者保持开放。

## 禁止的推断与操作

- 不把 `secure: yes` 当作 AVB、bootloader lock 或当前系统完整性的证明。
- 不把 Fastboot 不支持槽位变量当作“设备没有 A/B”的证明。
- 不执行 `getvar all`、`flash`、`erase`、`download`、`boot`、`continue`、`reboot`、`set_active`、`oem` 或 `unlock`。
- 不把 `EXT4-fs ... Can't find ext4 filesystem` 解释成“分区全零”、eMMC 物理损坏、PhoenixCard 必然擦坏、官方镜像不可用，或已证明其单独发起 `bootloader` 重启。
- 不在没有格式化责任、精确镜像哈希和用户明确授权前生成可刷写 metadata/boot/vendor_boot/vbmeta/Recovery 镜像。
