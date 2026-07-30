# UBOX10 M8

这是 `codex/m8-development` 分支。M8 完成前不并入 `main`；M7 / Test8r2
继续作为稳定恢复基线。

新会话从 [docs/FILE_MAP.md](docs/FILE_MAP.md) 开始。

## 当前结论

- 当前阶段：`M8A.2 — ACTIVE`
- M8A：沿用现有 UBOX10 硬件栈，构建真正的 ARM32 Android 12 ATV product。
- M8B：只有找到并证明可用的 AArch64 图形供体后，才尝试
  AArch64/multilib。
- 当前设备运行 Test8r2，并额外安装了日常软件；ADB 可用。
- 下一阻塞项是准备至少 400 GB 可用的 Linux/ext4 AOSP 构建卷。

项目优先级：

```text
usable TV experience
→ stable enough for daily use
→ easy rollback
→ understandable failures
→ formal completeness
```

详细状态、阶段和下一步分别见：

- [当前状态](docs/m8/STATUS.md)
- [理念与架构](docs/m8/ARCHITECTURE.md)
- [当前 TODO](docs/m8/TODO.md)
- [candidate 索引](docs/m8/CANDIDATES.md)

## 常用检查

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python .\scripts\inventory-elf.py '@configs/m8-test8r2-elf.args'
.\scripts\capture-m8-runtime-readonly.ps1 -Device "<电视IP>:7896"
```

仓库保存脚本、配置、来源锁和脱敏结论，不提交官方固件、闭源 blob、Google
专有 APK、设备安全材料或大型构建产物。
