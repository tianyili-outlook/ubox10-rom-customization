# M8B LeanbackIME remote proof

Date: 2026-08-16

Baseline: running `m8b-audio-r2`, accepted as **DEVICE ACCEPTED / AUDIO PASS**, network ADB `192.168.1.8:7896`.

Result: **LIVE USERDATA APK PASS** for AOSP LeanbackIME and **m8b-ime-r1 OFFLINE CHECKED / DEVICE PERSISTENCE PENDING**. No flash, reboot, suspend, service/network restart, property change, ROM mutation, or accepted-stack change occurred.

The source-built IME was installed reversibly with the locked AOSP EditText probe. InputMethodManager discovered and selected the exact Leanback component. DPAD_CENTER opened the IME and inserted `t`; DPAD_RIGHT moved keyboard focus and DPAD_CENTER inserted `y`; UI hierarchy read back focused EditText text `ty`. BACK hid the IME and DPAD focus/reopen worked. No IME/probe PID change, exit record, fatal exception, or persistent retry was found. Physical visual quality is not claimed.

Both temporary APKs were uninstalled. Final read-only check: device `device`, boot complete `1`, `ime list -a` empty, enabled setting `null`, default empty, both packages absent.

The offline candidate adds only the standard product LeanbackIME tree and attributable NOTICE update. Accepted product properties and all non-product logical partitions are exact; product/system AVB, LP reconstruction, outer preservation and IMAGEWTY verification pass.

See `commands.txt` and `decisive-excerpts.txt` for the bounded reproduction record. APK binaries, screenshots, raw UI XML and candidate images remain ignored local artifacts.
