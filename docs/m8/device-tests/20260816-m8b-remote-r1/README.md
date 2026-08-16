# M8B Remote v2 device acceptance

Date: 2026-08-16

Candidate: `m8b-remote-r1`, `out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`, 1031723008 bytes, SHA-256 `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`.

Final result: **DEVICE ACCEPTED / REMOTE PASS**, inheriting **AUDIO PASS / IME PASS**.

The user flashed the candidate and physically confirmed normal Projectivy boot, physical remote navigation, Wi-Fi, Bluetooth and LeanbackIME. The official Google TV iPhone app discovered and paired with the device; DPAD, BACK, HOME, Volume+, Volume-, Mute and phone-keyboard text entry into a real TV EditText all passed.

A bounded read-only ADB confirmation found `sys.boot_completed=1`, Remote Service 5.2.473254133 at the intended system priv-app path, `BLUETOOTH_CONNECT` granted with `GRANTED_BY_DEFAULT`, the Remote process running, TCP 6466/6467 listening, the system_ext RRO installed, and the effective framework resource resolving to `com.google.android.tv.remote.service`. LeanbackIME remained installed, enabled and default. No service, setting, property, network or log state was changed.

When the paired mobile Remote owned the text-input session, Android TV displayed `Use the keyboard on your mobile device` and directed input to the phone while physical remote navigation remained functional. This is accepted Remote input-session ownership, not a LeanbackIME regression and not a requirement for both keyboards to display simultaneously.

A separate reboot-persistence test was not performed. The milestone accepts that omission as non-blocking but does not claim reboot persistence PASS. `com.android.vending`, `com.google.android.gms` and `com.google.android.gsf` were absent, so there was no meaningful Play runtime regression test; the candidate still excludes the historical Test9r2 Play/GMS changes.

Separate observation: LeanbackIME first invocation after boot appeared slower than warm invocation and sometimes prompted two or three OK presses. This is recorded only as a low-priority usability investigation; no defect or root cause is claimed.

See `commands.txt` and `decisive-excerpts.txt`. Temporary APKs, proprietary Google binaries, candidate images and raw logs remain local/ignored.
