# M8A Android 12 ATV source lock

Status: **LOCKED and used for the verified offline M8A.2a build**.

| Item | Locked value |
|---|---|
| ATV upstream | `device/google/atv`, `android12-release` |
| ATV HEAD | `3ce48358b7e06ab1f1a1b713fb0f285aaa0983ca` |
| Manifest | `platform/manifest`, `android12-release` |
| Manifest HEAD | `8e7a52179c1704bc445f83efde08a6025acbf358` |
| Superproject | `51d9636ffdf52084355cc4dc3641ff9b0790c678` |
| Verified local tree | `/home/tianyi/ubox10-aosp` |

The Android TV product layers are source reference only: no emulator/goldfish/generic_x86 hardware or vendor configuration enters the UBOX10 product. While the existing WSL tree is retained, the lock confirms its source identity and supports rebuilding that tree. The Git checkout alone is not an independent reproduction record: it lacks `device/ubox/ubox10`, a resolved repo manifest, product-config digest, and exact build command record. Neither record proves runtime/boot compatibility.
