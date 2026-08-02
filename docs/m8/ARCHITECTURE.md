# M8 architecture

M8A uses ARM32 Android 12 ATV userspace with the retained stock device stack. It keeps boot, kernel, vendor, vendor_dlkm, DTBO, TEE, DRM, media, graphics, wireless, and partition dependencies.

## Candidate layout

Stock LP/fstab has no system_ext logical partition or mount. The candidate therefore:

- replaces system_a with AOSP system plus the AOSP system_ext root at `/system_ext`;
- preserves `/system/system_ext -> /system_ext`;
- replaces product_a;
- does not add system_ext_a;
- preserves vendor_a, vendor_dlkm_a, and stock vbmeta_vendor exactly.

Logical A sizes are system 1651167232, vendor 119066624, product 272629760, vendor_dlkm 6680576. Group use/free is 2049544192/1163292672.

M8A.2b validates this layout offline. The mixed test-root/stock-vendor AVB chain and flags 0 do not prove bootloader trust. Runtime Binder, HAL, SELinux, VINTF, graphics, media, DRM, Wi-Fi, Bluetooth, remote, CEC, audio, Ethernet, and first boot are device-only.

M8B remains parked until compatible AArch64 graphics-provider evidence exists.
