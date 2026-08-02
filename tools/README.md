# M8 tools

Only tools used by the current M8 build, inspection, or DRM probe remain here.

| Tool | Role | Source/version |
|---|---|---|
| `sunxi_image_tool.py` | IMAGEWTY list, extract, verify | Project tool |
| `pack_image_preserving.py` | Replace selected IMAGEWTY payloads without rebuilding unrelated entries | Project tool |
| `avbtool.py` | AVB metadata and hashtree operations | Bundled Android AVB tool |
| `lpunpack.py` | Extract logical partitions from raw super | `unix3dgforce/lpunpack` |
| `lpmake.exe`, `lpdumps.exe`, `simg2img.exe`, `img2simg.exe` | Build, inspect, and convert LP/sparse images | `Rprop/aosp15_partition_tools`, android-15.0.0_r25 |
| `testkey_rsa2048.pem` | Non-production test signing for M8A and the temporary DRM probe | Project test material; never treat as a production secret |
| `m8-drm-probe/` | Temporary no-permission MediaDrm capability probe | Project tool |

Locked binary SHA-256 values:

| File | SHA-256 |
|---|---|
| `lpmake.exe` | `602D59D2670F6DCCFEF81D854444AAFE2CAC7995D07E22158271BEF65ACCAF3D` |
| `lpdumps.exe` | `1DC8385534CD9A849750E42BE04CE0AF2AF1CE0C89074E8B88947CBD36035D23` |
| `simg2img.exe` | `5D840C8352D3790712B68077AB5E224D190737DD6ADD80541E6A871B6B205546` |
| `img2simg.exe` | `FE9FF41802F61FF1E510F2E012C398D1B2BF7E2C90392967182FD594B9AF5B65` |

Git pins the exact bytes of the Python tools and test material. Candidate configs additionally hash-lock every external image input they consume.
