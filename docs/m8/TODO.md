# M8 TODO

## Next test

- [ ] Obtain explicit authorization to flash `m8a-initial-atv-r6`.
- [ ] Verify the image size and SHA-256 in [STATUS](STATUS.md).
- [ ] Flash once in PhoenixCard Product mode, remove the card, and capture the cold boot at 115200 8N1.
- [ ] Record the earliest stable failure or first successful Android milestone; recover to Test8r2 if needed.

## Only after Android starts

- [ ] Confirm HDMI, ADB, framework, SystemUI, TvSettings, launcher/HOME, IME, and provisioning.
- [ ] Run practical remote, Wi-Fi, Ethernet, Bluetooth, audio/video, CEC, reboot, cold-boot, and rollback checks.
- [ ] Then address Google TV Remote/Play integration and Netflix/Widevine according to observed behavior.

## Parked

- [ ] Resume AArch64/M8B only after a matching 64-bit Mali/Gralloc/Mapper/HWC/Vulkan provider is proven for this board.
