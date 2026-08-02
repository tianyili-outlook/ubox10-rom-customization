# Build environment

## Verified offline environment

- WSL distribution: Ubuntu-24.04.
- AOSP tree: `/home/tianyi/ubox10-aosp`.
- Product output: `/home/tianyi/ubox10-aosp/out/target/product/ubox10`.
- Locked ATV HEAD: `3ce48358b7e06ab1f1a1b713fb0f285aaa0983ca`.
- Locked manifest HEAD: `8e7a52179c1704bc445f83efde08a6025acbf358`.
- Host tooling: Windows PowerShell/Python, WSL e2fsprogs/OpenSSL, repository avbtool, lpmake/lpdump, sparse-image tools, and IMAGEWTY tooling.

The build-volume blocker is resolved. The free-space measurement is operational context, not an invariant.

## Locked AOSP inputs

| Image | Sparse bytes | SHA-256 | Expanded bytes |
|---|---:|---|---:|
| system.img | 562741564 | EAEA0D2D914628AEB0C035E27ED5DFE52ECC37F0E3CCB95424835E3C8994E847 | 1625026560 |
| product.img | 75628656 | AA832873DDC12C14219466F2764F2AAD458EF0E1D4C752955829877CE306C09D | 268435456 |
| system_ext.img | 55066724 | 64999E94A72CCD1F99DFC8C25E1D7324D61C85634E7A504ABBD449DB52DA592B | 268435456 |

M8A.2a proves product construction only. M8A.2b additionally validates the assembled candidate offline. Neither proves runtime Binder, bootloader key acceptance, boot, or device behavior.
