# Active M8 decisions

- Preserve stock device-specific boot, kernel, vendor, vendor_dlkm, TEE, DRM, media, graphics, and wireless dependencies.
- M8A remains ARM32 Android 12 ATV. M8B is parked pending compatible AArch64 graphics evidence.
- M8A.2b replaces only system_a and product_a content. system_ext is merged into system_a because stock LP/fstab has no system_ext logical partition.
- Candidate outer changes are restricted to super.fex, vbmeta.fex, vbmeta_system.fex and their V companions. Forty other stored payloads are exact.
- AVB/dm-verity remains enabled with flags 0. Rebuilt system/product have no FEC; retained vendor/vendor_dlkm retain stock FEC. The mixed stock-vendor/test-root chain validates offline.
- The largest device-only risk is bootloader acceptance of the test root key. No offline result proves it.
- AwTvProvision is configured but absent. Projectivy, launcher/default HOME, and IME are absent or unproven.
- A built candidate is not boot-tested, promoted, or flash-authorized by documentation; no bootability claim is made.
