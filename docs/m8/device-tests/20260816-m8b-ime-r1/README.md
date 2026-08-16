# M8B LeanbackIME remote proof

Date: 2026-08-16

Baseline: running `m8b-audio-r2`, accepted as **DEVICE ACCEPTED / AUDIO PASS**, network ADB `192.168.1.8:7896`.

Initial result: **LIVE USERDATA APK PASS** for AOSP LeanbackIME and an offline-checked `m8b-ime-r1` candidate. That reversible phase performed no flash, reboot, suspend, service/network restart, property change, ROM mutation, or accepted-stack change.

The source-built IME was installed reversibly with the locked AOSP EditText probe. InputMethodManager discovered and selected the exact Leanback component. DPAD_CENTER opened the IME and inserted `t`; DPAD_RIGHT moved keyboard focus and DPAD_CENTER inserted `y`; UI hierarchy read back focused EditText text `ty`. BACK hid the IME and DPAD focus/reopen worked. No IME/probe PID change, exit record, fatal exception, or persistent retry was found. Physical visual quality was not claimed from this remote phase.

Both temporary APKs were uninstalled. Final read-only check: device `device`, boot complete `1`, `ime list -a` empty, enabled setting `null`, default empty, both packages absent.

The offline candidate adds only the standard product LeanbackIME tree and attributable NOTICE update. Accepted product properties and all non-product logical partitions are exact; product/system AVB, LP reconstruction, outer preservation and IMAGEWTY verification pass.

## Physical candidate acceptance

The user subsequently flashed `m8b-ime-r1` and supplied the acceptance result. Fresh-data first boot completed into Projectivy; the physical remote and Wi-Fi worked; LeanbackIME appeared automatically in the Wi-Fi password EditText without an ADB enable/set step. After network ADB became available at `192.168.1.8:7896`, `sys.boot_completed=1`, the APK path was `/product/app/LeanbackIME/LeanbackIME.apk`, and IME inventory, enabled setting, and default setting all named `com.android.inputmethod.leanback/.service.LeanbackImeService`. Physical DPAD focus/navigation, OK selection, text entry, BACK dismissal, and 1920×1080 TV appearance were normal.

Final result: **m8b-ime-r1 DEVICE ACCEPTED / IME PASS**. A separate reboot-persistence exercise was deliberately not performed; fresh-data automatic enable/default plus physical use was accepted as sufficient, so reboot persistence is not claimed as a separate PASS.

See `commands.txt` and `decisive-excerpts.txt` for the bounded reproduction record. APK binaries, screenshots, raw UI XML and candidate images remain ignored local artifacts.
