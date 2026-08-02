# UBOX10 ARM32 ATV product plan

M8A.2a product construction and M8A.2b candidate assembly are COMPLETE - VERIFIED OFFLINE.

The candidate preserves the stock hardware-facing stack and changes the Android product layer only:

1. Build locked ARM32 Android TV system, product, and system_ext.
2. Merge system_ext into system_a because stock LP/fstab has no system_ext mount.
3. Replace product_a; preserve vendor/vendor_dlkm and other stock payloads.
4. Rebuild required LP/AVB/IMAGEWTY metadata and validate offline.
5. Only after explicit physical authorization, test M8A.2c boot/init/framework/ADB/HDMI.
6. Then test M8A.2d TV UI, launcher/HOME/IME/provisioning, remote, and media behavior.

The candidate is not a claim of bootability. The test-root trust boundary, AwTvProvision absence, and launcher/IME/default HOME remain material device-only risks.
