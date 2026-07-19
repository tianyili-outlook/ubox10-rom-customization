# 工具锁定清单

在 M1 选型后逐项记录：名称、版本/提交、来源、许可证、下载文件 SHA-256、适用平台、调用命令和验证结果。不得使用未记录版本来生成可交付镜像。

## 锁定工具列表

### 1. sunxi_image_tool.py
* **名称**：Allwinner IMAGEWTY (PhoenixCard) 固件解析与验证工具
* **版本/提交**：v1.0.0 (Initial M1 release)
* **来源**：自研代码 (In-house development)
* **许可证**：Apache-2.0 (随项目整体授权)
* **文件 SHA-256**：`8E121C8B5978080A2929A703B79E7811843D4D6A0CB7E74C1CD377A79C615F8F`
* **适用平台**：跨平台 (Python 3.13+)
* **调用命令**：
  * 解析：`python tools/sunxi_image_tool.py list <image_path>`
  * 校验：`python tools/sunxi_image_tool.py verify <image_path>`
  * 提取：`python tools/sunxi_image_tool.py extract <image_path> [-o <out_dir>] [-f <file>]`
* **验证结果**：经测试成功解析 `x12-1024.img` 目录区并完美验证所有伴生 `V*.fex` 校验和。
