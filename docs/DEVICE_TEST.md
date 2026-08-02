# r6 device test and rollback

Physical flashing requires explicit user authorization. This guide does not authorize it.

## Files

| Role | Path | Bytes | SHA-256 |
|---|---|---:|---|
| r6 candidate | `out/candidates/m8a-initial-atv-r6/x12-m8a-initial-atv-r6.img` | 996582400 | `8796B4FC9ABA2D213B044043F979992CE9C5996425D52273A088A04EA3BE5D93` |
| Test8r2 rollback | `C:\Users\tiany\Documents\ubox10-rom改造\out\candidates\test8r2-restore-contacts-provider-r1\x12-test8r2-restore-contacts-provider.img` | 2005954560 | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| Stock recovery | `C:\Users\tiany\Documents\ubox10-rom改造\x12-1024.img` | 2018890752 | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |

## Receive-only UART

Connect with the box powered off:

- J21 GND -> FT232RL GND
- J21 TX -> FT232RL RXD
- Leave J21 RX, adapter TXD, and all VCC/5V/3V3 pins disconnected.

Enumerate the COM port, then arm capture from the repository root:

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/capture-uart-readonly.ps1 `
  -PortName COM3 -BaudRate 115200 -DurationSeconds 900 `
  -ReceiveOnlyWiringConfirmed
```

## One focused test

1. Verify the selected image size and SHA-256.
2. In PhoenixCard 4.2.7, write the image to the TF card in **Product** mode.
3. Power off the UBOX10, insert the card, arm UART, and power on.
4. Wait for `CARD OK`; power off, remove the card, then cold boot while UART remains active.
5. Record the earliest stable failure or the first Android/HDMI/ADB milestone in `docs/m8/STATUS.md` and the candidate record.

## Rollback

If r6 fails, repeat the Product-mode procedure with Test8r2. If Test8r2 does not recover, repeat with stock `x12-1024.img`. Do not overwrite or rename either rollback source.
