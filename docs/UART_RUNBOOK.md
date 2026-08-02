# UBOX10 UART 日志捕获操作指南

## 1. 硬件接线（只收不发）

在设备断电状态下完成两线被动接线：

```text
UBOX10 J21 GND ──────── FT232RL GND
UBOX10 J21 TX  ──────── FT232RL RXD

UBOX10 J21 RX       不连接
UBOX10 3.3V/VCC     不连接
FT232RL TXD         不连接
FT232RL VCC/5V/3V3  不连接
```

## 2. COM 端口枚举

在 PowerShell 中执行以下命令，确认 FT232RL 对应的实际串口编号（例如 COM3）：

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,PNPDeviceID
```

## 3. 启动捕获

切换至项目根目录，将下方命令中的 `COM3` 替换为实际串口号，运行 900 秒捕获：

```powershell
Set-Location -LiteralPath 'C:\Users\tiany\Documents\ubox10-rom改造\work\m8-development'
powershell -NoProfile -ExecutionPolicy Bypass `
  -File 'C:\Users\tiany\Documents\ubox10-rom改造\work\m8-development\scripts\capture-uart-readonly.ps1' `
  -PortName COM3 -BaudRate 115200 -DurationSeconds 900 `
  -ReceiveOnlyWiringConfirmed
```

## 4. 上电、停止与保存

1. 终端显示 `UART receive-only capture armed` 后，接通 UBOX10 原装电源。
2. 观察串口日志输出，待捕获完成（或手动按 `Q` / `Ctrl+C` 停止）。
3. 采集日志将自动保存至 `logs/device/<run-id>/` 目录。
4. 断开 UBOX10 电源后，拔出电脑端 USB 串口模块。
