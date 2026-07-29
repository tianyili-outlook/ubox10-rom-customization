# M8A 分区容量

| 范围 | 当前值 | 可用 |
|---|---:|---:|
| Test8r2 system ext4 | 1,625,026,560 B | 500,756,480 B（477.6 MiB） |
| 当前 product ext4 | 109,252,608 B | 327,680 B（320 KiB） |
| `sb_a` dynamic group | 3,212,836,864 B | 1,324,830,720 B（1263.5 MiB） |

当前逻辑分区合计 1,888,006,144 B。容量不是 M8A 阻塞项，但原 product
不能原尺寸重建；从 dynamic group 空闲量扩容即可，vendor 与 vendor_dlkm
尺寸保持不变。

最终 system/product 大小按首次静态构建实测确定，每个 ext4 至少保留
64 MiB 或 10% 空闲量中的较大值，并为 AVB footer 留出空间。不预先猜测
AOSP 模块大小，也不为容量核对增加固件 SHA-256。
