# UBOX10 ROM 改造运行手册 (Runbook)

本手册详细规范了 UBOX10 固件的反定制净化、编译、重签名与容器重打包的标准工作流。

---

## 🛠️ 构建流程 (Build Pipeline)

### 第一阶段：反定制净化与预集成

1. 将预集成第三方 APK 放入 `work/preinstall_apks/` 目录。
2. 运行净化裁剪脚本：
   ```powershell
   python scripts/purify-rom.py
   ```

### 第二阶段：ROM 分区编译与 AVB 签名

1. 运行重打包脚本：
   ```powershell
   python scripts/repack-rom.py
   ```
   *注意：需安装 `pycryptodome` 库。脚本先生成 Raw 镜像再调用 `img2simg` 转换为 Sparse 格式。*

### 第三阶段：全志 Image 封装与校验和计算

1. 运行固件容器打包脚本：
   ```powershell
   python tools/pack_image.py
   ```
2. 校验固件完整性：
   ```powershell
   python tools/sunxi_image_tool.py verify x12-purified.img
   ```
   *期待输出：`Verification complete: 10 partitions OK, 0 mismatches/errors.`*

---

## 💾 烧录步骤 (Flash)

1. 打开 **PhoenixCard** 工具 (推荐 v4.2.x 或 v4.9.x)。
2. 选择 **`x12-purified.img`** 固件。
3. 插入 MicroSD 卡，选择 **Product (量产卡模式)**。
4. 烧录完成后（进度 100%）拔掉 TF 卡，重新上电。

*如遇格式化报错 242，使用 Windows `diskpart` 执行 `clean` 并重建 FAT32 分区。*

---

## 🔍 启动验证 (Boot Validation)

观察以下启动阶段：

1. ✅ Boot logo 显示
2. ❓ Boot animation 是否出现
3. ❓ 是否进入 Android System 或 Recovery

记录所有异常行为。

---

## 🧪 调试原则 (Debugging Rules)

- 每次实验只测试一个假设。
- 尽可能只修改一个变量。
- 记录每次实验结果。
- 不在缺乏新证据的情况下重复实验。
- 每次失败的实验至少应排除一个假设。
