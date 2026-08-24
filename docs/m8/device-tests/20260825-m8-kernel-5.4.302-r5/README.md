# m8-kernel-5.4.302-r5 physical validation — 2026-08-25

Candidate: `m8-kernel-5.4.302-r5`

Verdict: **PHYSICAL PASS / WI-FI PASS**

## Proven result

The physical device booted Linux `5.4.302+`, completed Android startup and passed HDMI,
Wi-Fi association, Wi-Fi ADB, physical remote, Leanback framework, TV input method and launcher
checks. The AIC8800D stack loaded the expected BSP/BTLPM/FMAC modules and initialized at the
retained 66 MHz SDIO setting.

A physical Wi-Fi OFF → ON cycle cleanly removed the old `wlan0`/SDIO runtime and created a new
one. Android then completed association, the four-way and group handshakes, DHCP and validated
L3 connectivity on `wlan0`. IPv4 and DNS pings had zero loss, and Wi-Fi ADB reconnected.

The former r1-r4 signature, `START_APP 1037 -> reqcfm(1038) timeout`, did not recur during the
initial startup or the physical reinitialization. Both supplied filtered captures for
`timeout|wifi start fail|reqcfm|1037|1038` had **no matches**. One
`aicsdio: write retry: 20` occurred during reinitialization; initialization continued to a
functional, validated connection, so this record classifies it as a non-fatal transient
observation rather than reopening generic MMC/SDIO diagnosis.

## Evidence provenance and limit

The user collected the ADB evidence externally on the physical UBOX and supplied the reviewed
facts and exact excerpts. A search of the accessible VM/repository did not find the original raw
captures. Accordingly, this tracked directory preserves only the supplied result, command facts
and decisive excerpts. It does **not** claim that raw ADB files are archived in Git, and no
invented raw filename or SHA-256 is assigned to them.

The single-variable result strongly corroborates the accepted engineering root cause: r1-r4
placed the unchanged FMAC image at `0x00110000` because the donor source guard did not match the
actual build define, while r5 restored the working 5.4.125 BSP contract at `0x00120000`. This
proves the address-contract correction restores this device's observed Wi-Fi behavior; it does
not claim unobserved boot-ROM or firmware internals.

The same-lineage Linux 5.4.302 kernel/wireless preservation checkpoint is therefore
**CLOSED / PASS**. This result does not itself make Android 16 Gate 2 pass.
