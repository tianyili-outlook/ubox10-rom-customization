# Test8r2 兼容性运行时快照

采集时间：2026-07-30。设备运行 Test8r2，存在用户安装软件；采集只读且输出
已脱敏。

结论：轻量运行时信息已足够，M8A 可以直接进入源码同步和 product 构建，
不再补泛化运行时审计。

| 范围 | 结果 |
|---|---|
| 身份 | SDK 31，`armeabi-v7a,armeabi`，Pixel 3 / `blueline` 身份 |
| linkerconfig | 10 个生成文件；[完整快照](linkerconfig-test8r2.txt)已保存 |
| APEX | 21 个 active/factory APEX，21 个对应挂载 |
| classpath | BOOT 25 项、SYSTEMSERVER 7 项、DEX2OATBOOT 12 项 |
| shared library | 注册 17 项；18 个 package 声明 required/optional library，required 缺失 0 |
| VINTF | 36 个文件全部为结构有效的 XML |
| `checkvintf` | 设备没有该命令；本次不能宣称正式兼容性 PASS |

采集器执行 18 项命令，15 项成功、0 超时。3 项非零均用于确认接口缺失：
`apexservice` 未暴露，`checkvintf` 不在设备 PATH 且无法执行。

## linkerconfig

已保存：

```text
/linkerconfig/apex.libraries.config.txt
/linkerconfig/com.android.adbd/ld.config.txt
/linkerconfig/com.android.art/ld.config.txt
/linkerconfig/com.android.conscrypt/ld.config.txt
/linkerconfig/com.android.media.swcodec/ld.config.txt
/linkerconfig/com.android.media/ld.config.txt
/linkerconfig/com.android.os.statsd/ld.config.txt
/linkerconfig/com.android.runtime/ld.config.txt
/linkerconfig/com.android.sdkext/ld.config.txt
/linkerconfig/ld.config.txt
```

主配置包含 `default`、`system`、`sphal`、`vndk`、`vndk_product`、`rs` 以及
adbd、ART、Conscrypt、media、statsd、runtime、tethering 等 APEX namespace。
它是开机时生成的诊断基线，不应直接复制进 M8A 镜像。

## APEX

活动模块：

```text
com.android.adbd                 com.android.appsearch
com.android.art                  com.android.conscrypt
com.android.extservices          com.android.i18n
com.android.ipsec                com.android.media
com.android.media.swcodec        com.android.mediaprovider
com.android.neuralnetworks       com.android.os.statsd
com.android.permission           com.android.resolv
com.android.runtime              com.android.scheduling
com.android.sdkext               com.android.tethering
com.android.tzdata               com.android.vndk.v31
com.android.wifi
```

`cmd apexservice list --active` 在本机不可用；`apex-info-list.xml` 与实际挂载
一致，已足够描述当前基线。

## classpath

```text
BOOTCLASSPATH
/apex/com.android.art/javalib/core-oj.jar
/apex/com.android.art/javalib/core-libart.jar
/apex/com.android.art/javalib/okhttp.jar
/apex/com.android.art/javalib/bouncycastle.jar
/apex/com.android.art/javalib/apache-xml.jar
/system/framework/framework.jar
/system/framework/framework-graphics.jar
/system/framework/ext.jar
/system/framework/telephony-common.jar
/system/framework/voip-common.jar
/system/framework/ims-common.jar
/apex/com.android.i18n/javalib/core-icu4j.jar
/apex/com.android.appsearch/javalib/framework-appsearch.jar
/apex/com.android.conscrypt/javalib/conscrypt.jar
/apex/com.android.ipsec/javalib/android.net.ipsec.ike.jar
/apex/com.android.media/javalib/updatable-media.jar
/apex/com.android.mediaprovider/javalib/framework-mediaprovider.jar
/apex/com.android.os.statsd/javalib/framework-statsd.jar
/apex/com.android.permission/javalib/framework-permission.jar
/apex/com.android.permission/javalib/framework-permission-s.jar
/apex/com.android.scheduling/javalib/framework-scheduling.jar
/apex/com.android.sdkext/javalib/framework-sdkextensions.jar
/apex/com.android.tethering/javalib/framework-connectivity.jar
/apex/com.android.tethering/javalib/framework-tethering.jar
/apex/com.android.wifi/javalib/framework-wifi.jar

SYSTEMSERVERCLASSPATH
/system/framework/com.android.location.provider.jar
/system/framework/services.jar
/system/framework/ethernet-service.jar
/system/framework/pppoe-service.jar
/apex/com.android.appsearch/javalib/service-appsearch.jar
/apex/com.android.media/javalib/service-media-s.jar
/apex/com.android.permission/javalib/service-permission.jar
```

`DEX2OATBOOTCLASSPATH` 是 BOOTCLASSPATH 前 12 项，止于
`/apex/com.android.i18n/javalib/core-icu4j.jar`。

## uses-library

当前注册的 17 个 shared library：

```text
android.ext.shared
android.hidl.base-V1.0-java
android.hidl.manager-V1.0-java
android.net.ipsec.ike
android.test.base
android.test.mock
android.test.runner
com.android.future.usb.accessory
com.android.location.provider
com.android.media.remotedisplay
com.android.mediadrm.signer
com.google.android.gms
com.google.android.maps
com.google.android.media.effects
com.google.android.trichromelibrary
javax.obex
org.apache.http.legacy
```

实际 required 集合为 `android.hidl.base-V1.0-java`、
`android.hidl.manager-V1.0-java`、`android.test.base`、
`com.android.location.provider`、`javax.obex` 和
`org.apache.http.legacy`，均已注册。可选但未注册的车载、Wear、Samsung 和
部分 Google vendor library 不构成当前启动门禁。

## VINTF

采集到 vendor 22 份、system/system_ext 13 份、product 1 份，共 36 份
manifest/matrix fragment；全部能独立解析为 XML。framework matrix level
覆盖 3、4、5、6，device/vendor/product 另有未显式标 level 的矩阵。

设备没有 `/system/bin/checkvintf`。等 M8A 构建树提供 host 工具后，只对
实际新增或修改的 VINTF/HAL 运行检查；这不阻塞首个可恢复 candidate。

## 对 M8A 的用法

- 首版保留上述 provider、required shared library 和 system-server classpath
  合同，除非有明确替换理由。
- linker namespace、APEX 或 classpath 出错时，以本快照做差异定位，不要求
  新 product 逐行复刻 Test8r2。
- 只在相关 ELF、HAL、APEX 或 framework 变更后重采；不做周期性全量审计。

采集入口：
[`capture-m8-runtime-readonly.ps1`](../../../../scripts/capture-m8-runtime-readonly.ps1)。
完整脱敏命令输出保留在本地 `logs/device/`，不进入 Git。
