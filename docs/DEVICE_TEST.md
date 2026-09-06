# M8 device test and rollback

## 当前状态

- 最后报告的 Android 16 物理架构验收镜像：`out/candidates/a16-prototype-b-r7/x12-a16-prototype-b-r7.img`，1,641,773,056 bytes / SHA-256 `A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27`
- 当前项目状态：**ANDROID 16 ARM64 MIXED ARCHITECTURE — R7 PHYSICAL ARCHITECTURE PASS / FROZEN / GATE 3 `PASS_WITH_EXPLICIT_USER_WAIVER`**。唯一豁免是本轮未复验的遥控 `POWER`；用户明确授权以 prior-normal observation 透明关闭本 Gate，因此不是 bare/evidence-complete `PASS`。`a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd`（1,641,822,208 bytes / `9E9592BF420F40A386BC347B027A85B2F9ED0A44DDB132BDBAB9882905F75722`）保持 **PHYSICAL PASS — AUTHORIZED SDR 1080P YV12 ONLY / EXPERIMENTAL REPAIR / NOT r8 / NOT RELEASE**。Main10/HDR/AFBC/protected/4K未验证。
- Android 16 ARM32 control：`a16-prototype-a-r4` **FROZEN / PHYSICAL PASS**。`a16-dev-audio-r1` 已物理关闭 boot-time legacy audio P1；full VINTF 保持 inherited NFS exit 65 / **NOT PASS**。
- 保留的设备验收基线：`out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`，状态 **DEVICE ACCEPTED / REMOTE PASS**（继承 **AUDIO PASS / IME PASS**）。
- 大小 / SHA-256：1031723008 bytes / `F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`
- 用户当前在设备现场，可执行物理交互、重启、suspend/resume、HDMI 观察与恢复；任何新候选刷写仍需该候选的单独明确授权。

Wi-Fi ADB：

```powershell
C:\platform-tools\adb.exe -s <device-LAN-address>:7896 shell <read-only-command>
```

回滚到 accepted baseline 后的 ADB 检查入口：

```powershell
C:\platform-tools\adb.exe -s <device-LAN-address>:7896 shell getprop sys.boot_completed
C:\platform-tools\adb.exe -s <device-LAN-address>:7896 shell dumpsys media.player
C:\platform-tools\adb.exe -s <device-LAN-address>:7896 shell dumpsys media.audio_flinger
C:\platform-tools\adb.exe -s <device-LAN-address>:7896 shell dumpsys media.audio_policy
C:\platform-tools\adb.exe -s <device-LAN-address>:7896 logcat -d -b all
```

accepted baseline 已确认 Treble/VNDK、primary HAL/output、HEVC+AAC HDMI 音频、VP9 Allwinner/Cedar hardware runtime、Widevine 16.1.0 L3、LeanbackIME，以及 official Google TV iPhone Remote discovery/pair/navigation/phone text。刷入任何新候选仍须先获得该候选的单独明确授权。

## P2 — one-shot boot/runtime system audit

状态：**PHYSICAL CAPTURE ANALYZED / NO NEW P1 BLOCKER / ACTIVE DEBT RECORDED**。2026-09-03 exact
`a16-dev-audio-r1` one-shot cold-boot evidence已完成UART+read-only ADB T0→180秒idle→T1分析；没有重跑
Gate 3/audio-r1 media validation，也不是重复稳定性或压力测试。Collector本身没有做PASS/FAIL分类；
证据后的人工结果与canonical issue matrix见
`docs/m8/device-tests/20260903-a16-p2-boot-runtime-audit/README.md`。

同一boot ID `1f47a2b3-2618-44ec-866a-566c14ded851`下，zygote64/zygote32/system_server/
SurfaceFlinger/audioserver/ARM32 audio HIDL的PID/PPID/name在T0/T1一致，crash buffer为0，tombstone/ANR
无增量；没有fatal signal、critical restart、kernel fatal或历史`getAudioPortImpl` PC-zero回归。故P2
结论为 **ONE-SHOT AUDIT COMPLETE / NO NEW P1 / NO CRITICAL RESTART / NO PERSISTENT FATAL LOOP**，audio
P1保持CLOSED。主动债务为Thermal HAL缺失、KeyMint `earlyBootEnded`、cgroup memory controller合同和RTC/
联网前时钟；其中Thermal应在长时高负载4K/Main10 qualification前优先解决或建立明确监测边界。P2没有
启动P3，也没有扩展已证明的SDR 1080p YV12 scope。

### UART 与 ADB 分工

- UART 只作被动证据通道。使用项目已经验证可用的 UART setup；仓库虽记录 runtime console 为
  `ttyAS0,115200`，本计划不据此臆造接线、电平或 host serial 参数。
- 在物理上电前开始 host UART logfile，完成一次 cold boot；从 bootloader、kernel、init 持续记录到
  Android 稳定及 ADB collector 完成。整个过程不向 UART 输入命令。
- ADB 是 adbd 可用后的主要 runtime 通道；端点必须显式传入，端口固定为 `7896`，IP 不硬编码。
- PowerShell collector 不控制串口。ADB 完成后停止 UART capture，原始 logfile 保持 byte-for-byte，
  再用 host-only `-FinalizeOnly` 把它复制到 evidence root 并重建 SHA-256 manifest。

如果 cold boot 在 ADB 可用前失败，UART 即为决定性证据：停止，不自动重启或重试，先审阅首错。

### 未来一次性物理流程

1. 确认 exact `a16-dev-audio-r1` 仍已安装；无需重新 flash，也无需重复 audio-r1 验收。
2. 连接已验证 UART setup，在 host 开始 passive logging，然后物理执行**一次** cold boot。
3. 不输入 UART 命令；不自动 reboot，不建立 boot/playback/stress loop。
4. Android 网络 ADB 在 `:7896` 可达后，显式传当前 DHCP endpoint，运行 collector 一次。
5. T0 首先保存 boot ID、identity、关键 PID、all/crash logcat，然后完成 targeted read-only snapshot。
6. 设备保持完全 idle；180 秒内不播放媒体、不按遥控器、不切 Wi-Fi/HDMI、不触发 suspend。
7. T1 重采 boot ID、关键 PID、process/init/HAL、crash/tombstone/ANR、SELinux、audio/SF 与 logcat。
8. collector 输出 host-side `critical-pid-diff.txt` 和 command status，但不自动给出审计 verdict。
9. 停止 UART capture；用 finalize-only 加入 UART，复核 completeness 和 `SHA256SUMS.txt`。
10. evidence directory 保持完整，之后在 Git 外上传到类似
   `/work/physical-evidence/ubox10/a16-p2-audit/<timestamp>/`，再由独立任务分析。

Windows PowerShell 调用示例：

```powershell
Set-Location C:\path\to\ubox10-rom-customization
.\scripts\collect-a16-p2-audit.ps1 `
  -AdbPath 'C:\platform-tools\adb.exe' `
  -Endpoint '<current-device-LAN-IP>:7896'

# ADB capture结束并停止UART host logging后，使用collector打印的exact evidence root：
.\scripts\collect-a16-p2-audit.ps1 `
  -FinalizeOnly `
  -EvidenceRoot "$HOME\Downloads\UBOX10-A16-P2-AUDIT-YYYYMMDD-HHMMSS" `
  -UartLogPath 'C:\captures\ubox10-p2-uart.log'
```

默认 `-AdbPath` 为 `C:\platform-tools\adb.exe`、host output base 为 `$HOME\Downloads`、steady-state
wait 为 180 秒、单 command timeout 为 60 秒。输出 root 为
`UBOX10-A16-P2-AUDIT-YYYYMMDD-HHMMSS`，包括：

```text
00-Host/             host/collector/UART provenance
01-ADB-Entry/        adb version/devices/connect/get-state
10-BootSnapshot-T0/  decisive identity/PID plus early all/crash logcat
20-System/           getprop/process/init/service/kernel/dmesg/pstore
30-HAL-VINTF/        Treble/VNDK/VINTF/HIDL-AIDL visibility
30-Crash-Restart/    tombstone/ANR/Dropbox metadata
40-SELinux/          mode/domains/available AVC evidence
50-Display/          SurfaceFlinger/display/wm/Mali identity
60-Audio-Media/      audio policy/flinger and codec/service state; no playback
70-Network/          Wi-Fi/connectivity/IP/route/DNS state; no toggle
80-Power-Thermal/    power/battery/thermal/wakeup state; no suspend
90-Storage-Packages/ filesystems/storage/packages/features; no mutation
A0-SteadyState-T1/   selected idle-time recapture
B0-Final/            final all/crash logcat and host comparison
META/                COMMAND-STATUS.json and SHA256SUMS.txt
```

每条命令独立保存 sanitized stdout、stderr、start/end、exit code、timeout 与结果分类：`SUCCESS`、
`EMPTY_SUCCESS`、`NOT_AVAILABLE`、`PERMISSION_DENIED`、`COMMAND_FAILED` 或 `TIMEOUT`。Normal shell 无法
读取 dmesg、pstore、tombstone/ANR、wakeup sources 或某个 dumpsys 是有效审计证据；collector 不 root、
不提权，也不因非关键命令失败而丢弃其 stderr。输出在写盘前对 credential-like values、serial、
SSID、MAC 和 email 做保守脱敏。

硬安全合同：collector 不 reboot/root/remount，不改 property/settings/device_config/package/filesystem，
不 clear logcat，不切 network/HDMI，不注入 input，不启停/杀死 service/process，不触发 power/suspend，
不播放媒体，不运行 bugreport/stress workload，也不向 device push/pull/copy 文件。`-FinalizeOnly` 只操作
Windows host evidence files，不调用 ADB。

P2 不强制 AVC/HEVC/VP9、HDMI disconnect/reconnect、Wi-Fi OFF→ON、remote matrix 或 Gate3 rerun；只有
未来证据指向具体 regression 时才另行授权 targeted retest。

## P3-0 — thermal observability / HEVC 4K30 preparation

当前状态：**P3-A BOUNDED MAIN8 SDR 4K30 SURFACE PLAYBACK PASS；独立4K THUMBNAIL FAIL；P3-B MAIN10 NOT AUTHORIZED**。
September6 core evidence9/9哈希通过，14个compat1b shadow/import/texture成功，SF538和codec594
保持，用户确认完整流畅>10秒并有音频；不是持续负载qualification。详细thumbnail根因、未知点及
补充日志现已证明AFBC源被线性CPU copy误读；`a16-dev-p3a-thumbnail-r1`仅修此初始化合同，
已BUILT/OFFLINE CHECKED，尚未physical validation。下一步见
`docs/m8/device-tests/20260906-a16-p3a-thumbnail-r1-build/README.md`：另行授权flash后
BootGate FIRST→REVIEW→VLC/media准备→新文件thumbnail；随后复查1080 thumbnail和有界4K Surface。
须在VLC发现新文件前开始保留preparse日志，避免缓存假PASS；不自动播放/重复/重启。
以下RC-A/RC-A2/RC-B失败和测试计划
为历史推进记录，不撤销当前Surface播放PASS，也不授权新一轮设备操作。
完整source audit、dynamic read-only thermal observer、fixture contract、分层验收/失败分类和人工abort
边界见 `docs/m8/device-tests/20260903-a16-p3-thermal-4k30-plan/README.md`。

RC-A development candidate `a16-dev-p3a-omx-r1` 已执行一次有界实机复验。原`__anDrain` NULL未复发，
正式播放已完成`CODEC_POST_FBD`，故原RC-A repair对该路径**PHYSICAL EFFECTIVE**；但P3-A仍FAIL。VLC
medialibrary preparse在Executing→Idle销毁时另触发RC-A2：internal FBM为`VideoPicture::pMetaData`
分配4 KiB，而HEVC写入23,480-byte extended metadata，导致首次free时Scudo abort。正式播放另捕获精确
4K buffer `9891309682708` / backing store `2229088026704`：3840x2160 YV12、19,489,120-byte
auto-AFBC-big private allocation，绕过compat1a后在Mali以同类crop metadata ABI mismatch失败。
RC-A2的`READY_FOR_NARROW_BINARY_PATCH`证据现已落实为`a16-dev-p3a-fbm-r1`：仅将internal FBM
metadata allocation `0x1000`改为`0x6000`。新证据12/12哈希通过，4K preparse/Transform/teardown正常完成，
同boot和media.codec PID592连续；**RC-A2 PHYSICAL PASS / CLOSED**。正式播放仍在RC-B失败，PID592存活。
`a16-dev-p3a-compat1b-r1`现已仅实施精确4K replacement-buffer的metadata shadow分支，
构建时为**OFFLINE CHECKED / PHYSICAL VALIDATION PENDING**；现已按上述有界Surface scope物理通过。
候选和后续有界测试合同见`docs/m8/device-tests/20260905-a16-p3a-compat1b-r1-build/README.md`；
FBM原记录保留在`docs/m8/device-tests/20260905-a16-p3a-fbm-r1-build/README.md`。
未来必须先BootGate并review，再进行VLC/
media preparation；fixture进入VLC前启动live capture，单独保存preparse teardown，正式播放前完成
onboarding/scan，再开始正式AVCPre与AVC control并review，之后仅一次Main8 SDR 4K30手动播放。
捕获同buffer ID的`UBOX_P3_COMPAT1B eligible=1`、既有COMPAT1 shadow/translation/CLONE/import和
DIAG1 EGL/BackendTexture状态；thermal sampling必须覆盖播放窗口。任何失败立即stop/review，禁止自动重试。
构建时没有预先宣称成功；当前物理结果见本节开头。后续thumbnail调查不重开RC-B。完整历史取证见
`docs/m8/device-tests/20260905-a16-p3a-rca2-compat1b-forensics/README.md`。Main10继续NOT AUTHORIZED。

Retained H616 DT/kernel证明4路THS和CPU/GPU cooling；本次实机Discovery已证明normal-shell可读并取得
plausible live values，但absolute calibration和持续负载行为仍未qualification。因此当前仍是
**PARTIAL OBSERVABILITY — SHORT SMOKE ONLY**，不是Thermal HAL PASS。
一次授权的短HEVC Main 8-bit SDR 3840x2160p30实机尝试及RC-A单变量复验已完成。Discovery证明四路温度、CPUfreq、
GPU devfreq可读且baseline plausible，但采样窗口大多早于播放故under-load thermal仍NOT ESTABLISHED。
最早fatal为ARM32 `libOmxVdec.so::__anDrain+1212`对NULL current `VideoPicture*`的精确解引用；OMX重启后，
正式播放的3840x2160 YV12又因compat1a exact 1080p predicate不匹配而走original view，最终invalid Ganesh
texture触发SurfaceFlinger/zygote userspace restart。完整报告见
`docs/m8/device-tests/20260903-a16-p3a-4k30-failure-forensics/README.md`。先修复并验证OMX lifecycle，再根据
复验现已捕获精确4K handle/sidecar/EGL contract；同一metadata collision为very-high-confidence，但
archive未保留legacy `0x80..0xb7`逐字值，且翻译后仍可能暴露独立4K import limit，不得写成完整4K
playback已证明。parallel report见`docs/m8/device-tests/20260905-a16-p3a-rca2-compat1b-forensics/README.md`。
Main10/HDR/AFBC/protected仍未授权或证明；该forensic closure没有运行ADB、构建镜像或改变任何runtime。

### 后续分析合同

后续任务结合 passive UART 与 T0/T1 ADB evidence，生成字段为 ID、subsystem、severity、exact
signature、evidence file、first/last timestamp、count/frequency、boot-only/persistent、PID/service、
known/new、user impact、likely layer/root cause、priority、next action、confidence 的 issue matrix。
分类仅可使用：`P1 / BLOCKER`、`P2 / ACTIVE DEBT`、`P3 / NON-BLOCKING NOISE`、
`KNOWN INHERITED DEBT`、`EXPECTED / BY DESIGN`、`NEEDS MORE EVIDENCE`。当前 tooling 任务不预判
任何未采集日志。

## Gate 3 — Android 16 Mixed-Architecture Functional Preservation

状态：**`PASS_WITH_EXPLICIT_USER_WAIVER` — 2026-09-01 GOVERNANCE CLOSED；不是无条件PASS**。Gate 3
architecture/functional baseline仍是 exact frozen r7。Diag3a实机AVC PASS并证明HEVC decoder对extended
`sunxi_metadata`的合法初始化被Mali r20p0按legacy attr/crop ABI误读。Compat1不改producer sidecar、
decoder、gralloc、Mali blob或fatal；它只在Skia/Mali消费边界为exact 1920x1088 SDR YV12、non-AFBC、
non-protected buffer提供独立shadow view。结果严格使用`PASS`、`FAIL`或`NOT TESTED`。

2026-08-31 exact compat1a physical result：BootGate、正式初始AVC、primary单次SDR HEVC、第二次
HEVC interaction、正式AVC regression与Final crash census全部PASS。两次HEVC各14个buffer完整达到
sealed memfd shadow→23544→128/56-byte translation→CLONE→EGL import→valid BackendTexture；正式AVC
首测与regression各9个buffer保持`metadata_gate`/original view并成功import。Picture和HDMI audio正常，
pause/resume/seek/back正常，boot ID及SurfaceFlinger/zygote/system_server PID连续。第一次HEVC后的
非计划AVC只能分类为 **SUPPLEMENTAL / UNPLANNED AVC AFTER HEVC**，不是正式regression。

以下顺序保留为该物理结果的可复现实验合同；它不表示需要自动重跑。

### Compat1a physical gate — mandatory BootGate-first order

顺序不可折叠或调整：**flash → boot → BootGate → REVIEW BOOTGATE → VLC安装/验证 → 创建媒体目录 →
传输并验证两份fixture → 首次启动VLC并完成onboarding/权限/scan → AVCPre/Live/Post → REVIEW AVC →
HEVCPre/Live/Post → REVIEW HEVC → interaction → AVC regression → Final**。

BootGate前禁止安装VLC、复制媒体、首次启动VLC或播放任何媒体。BootGate失败立即停止。VLC和媒体
准备全部完成前禁止开始AVCPre；AVC未复核PASS前禁止HEVC；一次HEVC失败后禁止自动重复。
换言之，**AVC通过后才执行**唯一一次授权的SDR YV12 HEVC测试。

Windows PowerShell 7示例（必须显式传当前LAN IP；ADB不依赖PATH）：

```powershell
$Adb = 'C:\platform-tools\adb.exe'
$Ip = '<current-device-LAN-IP>'
& $Adb connect "${Ip}:7896"
$Helper = '.\scripts\capture-a16-prototype-b-r7-hevc-abi-compat1a-sdr-shadow-fd.ps1'

# Phase 0/1: flash、normal boot，然后第一件事就是BootGate。
& $Helper -Phase BootGate -DeviceIp $Ip
# 记录脚本打印的SessionRoot，先人工复核；失败则STOP。
& $Helper -Phase ReviewBootGate -DeviceIp $Ip -SessionRoot $SessionRoot -ConfirmBootGatePass

# Phase 2: 只有BootGate PASS后才安装VLC、建目录、push两文件、按host/device尺寸验证并首次启动VLC。
& $Helper -Phase PrepareMedia -DeviceIp $Ip -SessionRoot $SessionRoot `
  -VlcApk 'C:\fixtures\vlc-arm64.apk' `
  -AvcFixture 'C:\fixtures\diag1a-avc-aac-1080p30.mp4' `
  -HevcFixture 'C:\fixtures\diag1a-hevc-aac-1080p30.mp4'
# 完成welcome/onboarding、媒体权限和scan；确认两文件可见，且不要播放。
& $Helper -Phase ConfirmMediaReady -DeviceIp $Ip -SessionRoot $SessionRoot -ConfirmMediaReady

# PrepareMedia内部使用的显式ADB操作如下（用于审计；使用helper时不要另跑一遍）：
& $Adb connect "${Ip}:7896"
& $Adb -s "${Ip}:7896" get-state
& $Adb -s "${Ip}:7896" install -r 'C:\fixtures\vlc-arm64.apk'
& $Adb -s "${Ip}:7896" shell pm path org.videolan.vlc
& $Adb -s "${Ip}:7896" shell mkdir -p /sdcard/Movies/UBOX10-COMPAT1A/
& $Adb -s "${Ip}:7896" push 'C:\fixtures\diag1a-avc-aac-1080p30.mp4' /sdcard/Movies/UBOX10-COMPAT1A/diag1a-avc-aac-1080p30.mp4
& $Adb -s "${Ip}:7896" push 'C:\fixtures\diag1a-hevc-aac-1080p30.mp4' /sdcard/Movies/UBOX10-COMPAT1A/diag1a-hevc-aac-1080p30.mp4
& $Adb -s "${Ip}:7896" shell stat /sdcard/Movies/UBOX10-COMPAT1A/diag1a-avc-aac-1080p30.mp4 /sdcard/Movies/UBOX10-COMPAT1A/diag1a-hevc-aac-1080p30.mp4
& $Adb -s "${Ip}:7896" shell am start -n org.videolan.vlc/.StartActivity

# Phase 3: AVC control，一次手工播放，然后STOP复核。
& $Helper -Phase AVCPre -DeviceIp $Ip -SessionRoot $SessionRoot -ClearLogcat
& $Helper -Phase AVCLive -DeviceIp $Ip -SessionRoot $SessionRoot
& $Helper -Phase AVCPost -DeviceIp $Ip -SessionRoot $SessionRoot
& $Helper -Phase ReviewAVC -DeviceIp $Ip -SessionRoot $SessionRoot -ConfirmAvcPass

# Phase 4: 仅在AVC PASS后手工播放一次SDR YV12 HEVC，然后STOP复核。
& $Helper -Phase HEVCPre -DeviceIp $Ip -SessionRoot $SessionRoot -ClearLogcat
& $Helper -Phase HEVCLive -DeviceIp $Ip -SessionRoot $SessionRoot
& $Helper -Phase HEVCPost -DeviceIp $Ip -SessionRoot $SessionRoot
# STOP并复核；只有稳定PASS后才允许interaction和AVC regression。
& $Helper -Phase ReviewHEVC -DeviceIp $Ip -SessionRoot $SessionRoot -ConfirmHevcPass
& $Helper -Phase InteractionPost -DeviceIp $Ip -SessionRoot $SessionRoot
& $Helper -Phase AVCRegressionPre -DeviceIp $Ip -SessionRoot $SessionRoot -ClearLogcat
& $Helper -Phase AVCRegressionLive -DeviceIp $Ip -SessionRoot $SessionRoot
& $Helper -Phase AVCRegressionPost -DeviceIp $Ip -SessionRoot $SessionRoot
& $Helper -Phase Final -DeviceIp $Ip -SessionRoot $SessionRoot
```

如`am start -n org.videolan.vlc/.StartActivity`失败，人工执行
`& $Adb -s "${Ip}:7896" shell cmd package resolve-activity --brief org.videolan.vlc`，再用解析出的
activity启动；最后手段是人工执行`monkey -p org.videolan.vlc -c android.intent.category.LAUNCHER 1`。
任何fallback也必须在BootGate PASS之后、AVCPre之前。

`-ClearLogcat`只允许在Pre phase先保存baseline后，经用户输入确认再执行；failure之后绝不clear logcat，
也不clear pstore/tombstones。脚本不自动reboot、不自动控制播放器、不改HDMI/`wm size`、不fix
quarter-screen、不循环HEVC。
Formal helper通过`Write-Utf8NoBom`保证空crash stream也生成明确的0-byte `crash-buffer.txt`；本次
AVCPost、HEVCPost、InteractionPost、AVCRegressionPost和Final证据已实际证明该行为。Fixture校验仅为
host/device **size equality**，不是SHA-256或byte-for-byte内容证明。

### 2026-09-01 Gate 3 physical closure

外部只读证据位于`/work/evidence/ubox10/r7-gate3-20260901/unpacked`；原始
`SHA256SUMS.txt` **37/37 PASS**，ZIP内部测试通过且ZIP内清单与解包清单逐字节相同。ZIP当前实测
SHA-256为`82E63440C4AD0F98BECDA682E0FC73B17BA954CAD5E446D718CCF46D996E1D16`；任务文本和证据包均未
携带独立的host-reported SHA值，故外部host值比对准确记为 **NOT PERFORMABLE**，没有用重新计算值冒充。
Raw evidence与用户现场观察共同得出：

| Contract item | Result | Evidence boundary |
|---|---|---|
| 3A architecture regression | **PASS** | API36/Android16、`zygote64_32`/mixed ABI、两个zygote、system_server/SF alive、Mali/apollo；无architecture-blocking mapper/gralloc复发 |
| 3B media | **PASS** | compat1a formal AVC、SDR HEVC、interaction、formal AVC regression及HDMI audio PASS；formal VP9为`V_VP9+A_VORBIS`、`OMX.allwinner.video.decoder.vp9`→Cedar/VE、`bIsSoftDecoder=0`、640x480 FBM，正常结束 |
| 3C remote | **`PASS_WITH_EXPLICIT_USER_WAIVER`** | UP/DOWN/LEFT/RIGHT/OK/BACK/HOME/VOL±可见行为PASS；MENU physical/Linux/Android mapping存在而当前UI可见行为`NONE`，不据此称input failure；POWER本轮未复验且无伪造scan code，用户明确waive |
| 3D Wi-Fi lifecycle | **PASS** | 物理TV UI OFF→ON、断开/重连、saved `SINGTEL-UKC7`、BSSID `f4:ca:e7:70:66:f0`、supplicant COMPLETED、IPv4 `192.168.1.3`；用户报告external IPv4/DNS ping和ADB `:7896`恢复，post capture同boot/PID且无新crash/tombstone |
| 3E platform sanity | **PASS** | `/data/local/tmp`写/读/删、package、framework/VLC package、settings/provider、storage及final continuity PASS；USB/Ethernet为optional、用户defer并准确记NOT TESTED |

Formal VP9不能与更早的`c2.android.vp9` probe混淆；决定性播放路径是Allwinner OMX+Cedar hardware
runtime。所有Gate3采证阶段共享boot ID `21f681ad-1c90-4760-8086-629e1d076c2a`和关键PID
SurfaceFlinger 541、zygote32 488、system_server 775；post crash buffers为0 bytes，tombstone listing
保持`AC4B7286...3499F8`。VP9Pre仅含已知boot-time ARM32 audio `getAudioPort` crash；它没有在action后
新增或转化为loop/无声故障。

原合同要求intended remote matrix包含POWER，所以不把用户豁免静默改写成裸`PASS`。最终判定为
**Gate 3 `PASS_WITH_EXPLICIT_USER_WAIVER` / CLOSED**；唯一waiver是POWER current-session
revalidation，**remaining Gate3 blockers = none**。USB/Ethernet optional deferred不是blocker。机器记录为
`docs/m8/candidates/a16-prototype-b-r7-gate3-physical-result.json`。Canonical r7仍PASS/FROZEN/UNCHANGED；
r8仍**NOT AUTHORIZED / NOT BUILT**，development branch未创建。

### 3A — architecture regression confirmation

- Android 16/API36、`zygote64_32` 与 canonical mixed ABI lists；
- `sys.boot_completed=1`，primary `zygote64`、secondary `zygote`、ARM64-parented
  `system_server` 与 ARM64 SurfaceFlinger alive；
- crash buffer 不再出现 `gralloc-mapper is missing`；
- `ro.hardware.egl=mali`、`ro.board.platform=apollo` 与 Mali-G31 GLES active。

这是回归确认，不是新的 provider/architecture 研究。任一 regression 必须原样冻结，不能先做 r8。

### 3B — real media and HDMI audio

优先复用 `20260826-a16-prototype-a-r4-physical-validation` 与
`20260816-m8b-audio-r2-vp9-drm` 已知方法/fixture。至少逐项物理运行：

- H.264 + AAC；
- HEVC/H.265 + AAC；
- VP9（若 fixture 含 audio，另记 audible result）。

每项都记录真实 app、可见 video、存在 audio track 时的可听 HDMI audio、播放区间前后相关
process/log，以及是否出现新的 SurfaceFlinger/mapper/gralloc fatal 或 persistent media-service
restart loop。**PLAYBACK PASS 不自动等于 HARDWARE DECODE PATH PROVEN**；只有 exact codec/runtime
证据才能提升后者。

### 3C — physical remote matrix

依次测试 `UP`、`DOWN`、`LEFT`、`RIGHT`、`OK/DPAD_CENTER`、`BACK`、`HOME`、`MENU`、
`VOL+`、`VOL-`、`POWER`。每个键记录 physical scan code → Linux key → Android keycode →
framework-visible behavior。特殊 policy 或 intentional unsupported 必须按事实记录，不在 Gate 3
重做 kernel/keylayout。

### 3D — Wi-Fi lifecycle preservation

在 connected 状态记录基线，然后通过**电视端物理 UI/遥控**执行 Wi-Fi OFF→ON。Wi-Fi ADB 在 OFF
期间断开是预期 transport loss，不是 Wi-Fi FAIL；禁止依赖已断开的 host session发回 ON 命令。
重新关联后验证 DHCP/IP、external IPv4、DNS 与 ADB `:7896` recovery。若不能建立不依赖 Wi-Fi ADB
的安全 re-enable path，则本项 fail closed，不改 driver/kernel。

### 3E — storage and basic platform sanity

确认 `/data` writable、package manager responsive、settings/provider responsive。USB host/storage
和 Ethernet 仅在 fixture 可用时测试；fixture 缺失记 **NOT TESTED — FIXTURE UNAVAILABLE**，不伪造
PASS，也不单独阻断其他已完成项目。

### Crash/restart census

在所有 user actions 前后分别保存 crash buffer 与 timestamped critical census，覆盖 zygote、
system_server、SurfaceFlinger、mapper/gralloc/Mali/EGL、audioserver/vendor audio、media codec/
extractor/vendor media 与 Wi-Fi services。Known boot-time audio debt必须与新 regression分开；旧
buffered entry不能在缺少 timestamp/boot-context时当作新失败。

### Gate 3 verdict rule

Gate 3 只有在 3A 全部保持、三类 required media playback、intended remote matrix、Wi-Fi lifecycle、
`/data`/package/settings core sanity均 PASS，且 action前后没有 material new crash/restart regression时
才可记 **PASS**。Optional USB/Ethernet fixture可保持 NOT TESTED。与 r7 baseline一致的一次性、自动
恢复 audio startup debt本身不使 Gate 3失败；若变成 loop、service unavailable、无声或 playback
failure，则是 material regression。任一 required item FAIL 时先记 evidence-backed HOLD；不自动授权 r8。

### Gate 3 exclusions

Gate 3 不要求 SELinux enforcing、full-VINTF NFS cleanup、audio boot SIGSEGV repair、suspend/
resume、HDMI hotplug、CEC、Bluetooth deep lifecycle、Vulkan、HDR、4K60、commercial Widevine、
GMS/Play Store/Netflix、launcher/IME/settings polish、thermal tuning或 Wi-Fi statistics cleanup。

Windows PowerShell 只读采证入口：

```powershell
.\scripts\capture-a16-prototype-b-r7-functional-preservation.ps1 `
  -Device <device-LAN-address>:7896 -Phase Baseline

# Known-good media playback and manual observations, then:
.\scripts\capture-a16-prototype-b-r7-functional-preservation.ps1 `
  -Device <device-LAN-address>:7896 -Phase PostMedia

.\scripts\capture-a16-prototype-b-r7-functional-preservation.ps1 `
  -Device <device-LAN-address>:7896 -Phase Remote

# Capture connected state; then use the physical UI for OFF -> ON.
.\scripts\capture-a16-prototype-b-r7-functional-preservation.ps1 `
  -Device <device-LAN-address>:7896 -Phase WifiPre

# After ADB reconnects:
.\scripts\capture-a16-prototype-b-r7-functional-preservation.ps1 `
  -Device <device-LAN-address>:7896 -Phase WifiPost

.\scripts\capture-a16-prototype-b-r7-functional-preservation.ps1 `
  -Device <device-LAN-address>:7896 -Phase Final
```

脚本把 timestamped、sanitized raw command output写入 ignored `logs/device/`，不内置 Wi-Fi
credential、不更改 partition/property/SELinux，也不自动判断“画面可见”或“声音可听”；这些由
每个 capture directory 的 `manual-observations.txt` 明确填写。R7 architecture evidence见
`docs/m8/device-tests/20260829-a16-prototype-b-r7-physical-validation/`。

## Gate 2 physical result: a16-prototype-a-r4

Evidence：`docs/m8/device-tests/20260826-a16-prototype-a-r4-physical-validation/`。Original raw
r4 captures 未存在于本 VM；tracked record 是 reviewed external user confirmation，不伪造 raw
file/hash。本任务未重做物理测试。

| 阶段/功能 | r4 结果 |
|---|---|
| Android/EGL | **PASS**：Android16/API36/`zygote32`/5.4.302+/boot complete；无 UART/`setprop`；`persist.graphics.egl` empty、`ro.hardware.egl=mali`、`ro.board.platform=apollo`；Mali/UI PASS |
| Remote | **PASS / PHYSICALLY PROVEN**：`sunxi-ir.kl`；scanCode 352→`DPAD_CENTER(23)`；UP/DOWN/LEFT/RIGHT/OK/BACK/HOME PASS |
| HDMI | **PASS / STABLE IN THIS VALIDATION**：r3 black-cycle **NOT REPRODUCED**；r4 无 display delta，旧 root cause **NOT PROVEN** |
| Wi-Fi | **PASS**：module/scan/association/WPA/DHCP/IPv4/DNS/Android VALIDATED/real use；本轮 OFF→ON 因 Wi-Fi ADB transport self-disconnect **NOT COMPLETED / NOT FAIL** |
| Ethernet | **NOT RETESTED / NO ACTIVE CARRIER**：r4 exact preservation + prior physical PASS 保持 control |
| Direct HDMI audio | **PASS / AUDIBLE**：48 kHz/16-bit/stereo WAV 经 `tinyplay`/`ahubhdmi` 在 HDMI TV 物理听到 |
| VLC video/audio | **PASS / AUDIBLE**：normal picture/TV audio；AudioFlinger writes/session；service PIDs playback 前后稳定；clean interval crash buffer empty |
| Boot audio HAL | **KNOWN OPEN / REPRODUCED / AUTO-RECOVERED**：`getAudioPortImpl`/`getAudioPort` null-address SIGSEGV；steady-state impact not observed；exact source root cause not proven |

旧合同按 **vendor audio HAL startup stability** 得出 HOLD；该历史结论保留。用户随后明确把
Architecture Gate 2 定义为 functional viability gate。基于 real audible playback、stable
steady-state PIDs、auto-recovery 和 clean playback interval，formal result 更新为 **GATE 2
CLOSED / PASS**。Crash 仍为 **KNOWN / UNFIXED / AUTO-RECOVERED / POST-GATE P1**，不称 fixed。
Enforcing SELinux 属 later release hardening；full VINTF 仍因 inherited `CONFIG_NFS_FS=y` 对
FCM-6 `n` exit 65，不称 PASS。Exact r4 为 frozen rollback control；B1 只能按
`docs/m8/research/prototype-b-b0-readiness.md` 构建一个 bounded candidate。

## Gate 2 physical result: a16-prototype-a-r3

本轮仅对现场已运行的 r3 进行 Ethernet-ADB 采证，未 flash、reboot、build 或修改 image。
Evidence：`docs/m8/device-tests/20260825-a16-prototype-a-r3-physical-validation/`。

| 阶段/功能 | r3 结果 |
|---|---|
| Android identity | **PASS**：Android 16、API36、BP2A.250805.034、SPL 2025-08-05 |
| ABI/zygote/kernel | **PASS**：ARM32-only、empty ABI64、`zygote32`、Linux 5.4.302+、六项 Path-A config `=y` |
| APEX/core framework | **PASS**：boot complete、APEX ready/mount、三个 service manager、system_server/SystemUI |
| Original EGL selection | **FAIL**：无 `persist.graphics.egl`/`ro.hardware.egl`；用户提供的原始日志显示 `ro.board.platform=apollo` 驱动选择失败 |
| Graphics with pre-existing runtime override | **PASS WITH OVERRIDE**：`persist.graphics.egl=mali`，Mali-G31 GLES 3.2、SurfaceFlinger composition |
| TV/launcher/IME | **PASS**：TV/Leanback feature、HOME launcher 与 LeanbackIME present/default；文字输入本身不声明 |
| Ethernet | **PASS**：carrier、gateway/IP/DNS 4/4、Ethernet ADB |
| Wi-Fi | **PARTIAL**：BSP/framework/scan/OFF→ON reinit PASS；association/DHCP/L3/DNS **NOT TESTED**（无 saved network/无法输入凭据） |
| IR remote | **PARTIAL FAIL**：全部 Linux DOWN/UP PASS；OK scanCode 352→Android UNKNOWN，Generic.kl 仅 353→DPAD_CENTER |
| HDMI | **FAIL**：monitor 约 1 秒画面后约 5 秒黑屏循环；framework/extcon/display counters 的 bounded sample 未解释物理黑屏 |
| Audio | **FAIL / NOT TESTED SPLIT**：Apollo/ALSA/AudioFlinger topology 与 volume/mute framework effect 存在；HIDL HAL 在 `getAudioPort` null-pointer crash，stability FAIL；monitor 无 audio output，实际听音 **NOT TESTED** |

Exact gate wording：**CORE PATH-A ARCHITECTURE VIABILITY PHYSICALLY PROVEN / FORMAL CANDIDATE
CLOSURE PENDING**。依赖 runtime EGL override，因此 Gate 2 **NOT CLOSED**。下一候选才可持久加入
`ro.hardware.egl=mali`（保持 `ro.board.platform=apollo`）和 scanCode 352→DPAD_CENTER；二者在
本轮均 **NOT IMPLEMENTED / NOT BUILT / NOT PHYSICALLY VALIDATED**。HDMI/audio 只按现有 evidence
继续 diagnosis，不在本轮修改。Prototype B 继续关闭。

## Gate 2 physical result: a16-prototype-a-r1

用户已对 r1 授权并仅执行一次 PhoenixCard 刷写。写入日志 `logs/20260822-a-r1/uart-putty.log` 为 44,206 bytes / SHA-256 `C4823F59F09FA2ED60E5F35251641B0B0E9ABFAFEF1318F065DAFBED901E4D0C`；13 个 download parts、26 个 MBR parts、payload checksum、`sprite success` 与 `CARD OK` 均通过。

运行日志 `logs/20260822-a-r1/boot.log` 为 78,275 bytes / SHA-256 `18BF7217AFA25CAB2B7443B17A801D8825932FA4EB15ADCFC87D6FE1C3F46C7F`。它记录 7 次 accepted 5.4.125 kernel start 和 6 个完整周期；每个完整周期均进入 Android init，并以 `reboot: Restarting system with command 'bootloader,bootstrap-apexd-failed'` 结束。第 7 次在相同 early-init/cgroup 位置后截断。

后续诊断日志 `logs/20260822-a-r1-devkmsg/boot-devkmsg-on.log` 为 35,625 bytes / SHA-256 `E3EF999E109B837C5DBB3390E110EC80AD3D9DEFE02F0B0CAF581C46C4C2A517`。`printk.devkmsg=on` 只在 U-Boot RAM 中追加并在启动前回读确认，未改 boot image 或持久环境。它推翻了原先把 blkio 视为独立噪声的分类。

运行时边界：

| 阶段 | 结果 |
|---|---|
| kernel / accepted first-stage init / LP mapping | **PROVEN** |
| system mount；vendor/system_ext SELinux inputs 可读 | **PROVEN** |
| split SELinux compile/load；A16 second-stage init | **PROVEN**；cmdline 为 permissive，不证明 enforcing |
| A16 `CgroupSetup` | **FIRST REPRODUCIBLE BLOCKER**；required v1 blkio mount 因 kernel 无 `CONFIG_BLK_CGROUP` 失败，并在创建 v2 `apps`/`system` 子层级前返回 |
| ueventd / apexd-bootstrap | **FORKED BUT NOT EXEC'D**；父进程无法建立 `/sys/fs/cgroup/system/uid_0`，子进程在 `ExpandArgsAndExecv()` 前收到 fatal 状态 |
| bootstrap APEX activation | **NOT ATTEMPTED / NOT PROVEN** |
| servicemanager / zygote32 / system_server | **NOT REACHED / NOT PROVEN** |
| SurfaceFlinger / HWC | **NOT REACHED / NOT PROVEN** |

Exact A16 source path 为：`CgroupSetup()` 在 required blkio `mount()` 返回 `EINVAL` 后 false-return；`cgroup_v2_sys_app_isolation=true` 所需 `/sys/fs/cgroup/system` 因此尚未创建；`Service::Start()` fork 后的 parent `createProcessGroup()` 失败并通过 FIFO 发 `kActivatingCgroupsFailed`；child 在 task profile、credentials/caps 和 `execv` 之前 fatal exit。Exact retained kernel 同时缺少 `CONFIG_CPUSETS`，所以只开启 `CONFIG_BLK_CGROUP` 仍会在下一个 required controller 失败；最小 delta 是 BLK_CGROUP + CPUSETS（自动带出 PROC_PID_CPUSET）。A16 v2 memory controller 为 optional，故本轮不增加 MEMCG。

`Could not update logical partition` 和 early secilc `/linkerconfig/ld.config.txt` 仍是继续执行的 non-fatal early-boot 行为；missing `pid_163`/`pid_164/cgroup.procs` 是进程组创建失败后的清理 cascade；missing `misc` 只发生在 `reboot_on_failure` 已选择重启之后。该 r1 结果本身没有授权后继候选；r2 后来取得了单独授权，其唯一物理结果记录如下。Prototype B 仍不得启动。

## Gate 2 physical result: a16-prototype-a-r2

r2 先完成离线审核，随后由用户单独授权并完成一次 PhoenixCard/UART-first 物理测试。镜像为 `out/candidates/a16-prototype-a-r2/x12-a16-prototype-a-r2.img`，1,261,038,592 bytes / SHA-256 `114DF8677CD6984EB1431377723EDF61C80ACF26C15D8770BAE47DCFE7D1B6D0`。

它只把 retained kernel config 的 `CONFIG_BLK_CGROUP`、`CONFIG_CPUSETS` 及 Kconfig 自动产生的 `CONFIG_PROC_PID_CPUSET` 改为 `y`，并只替换 outer `boot.fex`/`Vboot.fex`。r1 system/APEX/LP/vendor、vendor_boot/ramdisk、AVB 元数据和其余 48/50 outer payload 原字节保持。Boot AVB、IMAGEWTY、ext4、cgroup contract、SHA256SUMS PASS；full VINTF 没有新增错误，仍只保留继承的 NFS config 例外。该历史 r2 结果使当时 Gate 2 继续 **CLOSED**；当前状态见文首 r5/r7 closure。

Flash capture `logs/20260822-a-r2/uart-flash-r2.log` 为 44,451 bytes / SHA-256 `832E3BEDC7BD50E3D9B562FFEE375189825EE3ECA1A3E67D8026157E4545DD2E`。13 个 download parts 均成功，最终为 `CARD OK` / `sprite success`。旧 GPT fallback、erase alignment 文字与既有 successful PhoenixCard 流程一致，不改变写入成功结论。

Boot capture `logs/20260822-a-r2/boot-r2-devkmsg-on.log` 为 67,394 bytes / SHA-256 `BF3196E9DB99AF4F70B5F7CEA5CBA166A40A92299E9670ED517357F2EEE5C4AC`。`printk.devkmsg=on` 仅在 U-Boot RAM 中追加并在 `run boot_normal` 前回读，未写入 boot image 或持久环境。它记录 5 次 kernel start 与 4 个完整、相同的周期。

运行时边界：

| 阶段 | r2 结果 |
|---|---|
| retained 5.4.125 kernel / first-stage init / LP / system handoff | **PROVEN** |
| split SELinux load / second-stage init | **PROVEN TO CURRENT BOUNDARY**；仍为 permissive，不声明 enforcing compatibility |
| required blkio/cpuset、cgroup-v2 root 与 `/sys/fs/cgroup/system` | **PROVEN FIXED**；r1 `uid_0` pre-exec blocker 消失 |
| ueventd | **EXECUTED**；shutdown trace identifies live PID 164 |
| bootstrap/full APEX progress | **ADVANCED**；无 `bootstrap-apexd-failed`，init 实际读取 `/apex/com.android.uprobestats/etc/init.rc` |
| servicemanager / hwservicemanager / vndservicemanager | **EXECUTED**；live PID 267/268/269 与 interface-control traffic 可见 |
| bpfloader / NetBpfLoad | **FIRST REPRODUCIBLE FATAL**；四次均报告 `Android 25Q4 requires kernel 5.10`，然后执行 `reboot_on_failure` |
| zygote32 / system_server / SurfaceFlinger / HWC | **NOT REACHED / NOT PROVEN** |

`cgroup2: Unknown parameter 'memory_recursiveprot'` 由 A16 source 明确重试无该选项，随后 boot 继续；IncFS module 缺失回退为 features v1/none；UprobeStats init 的 `CAP_PERFMON` 不支持发生在 APEX content import 后，该 service 本身 disabled，当前不是 fatal，但保留为真实后续兼容缺口。`/dev/stune/foreground/tasks` 与大量 process-group cleanup 是 bpfloader 已触发 shutdown 后的 secondary/cascade output。没有证据支持再改 cgroup 作为本轮首错。

r2 的 A16 物理授权已经消耗。当前不得再次刷写，不构建 A16 r3，不启动 Prototype B。后续只允许早期 A16 QPR0 与 retained-kernel LTS 路线的离线架构 checkpoint；任何新候选仍需重新离线审核和单独物理授权。

## Physical result: m8-kernel-5.4.302-r1

用户已另行授权并执行一次 Android 12 kernel-only r1 实机测试。现场结果：Linux
5.4.302 正常启动，Android `sys.boot_completed=1`；HDMI/UI、遥控、Ethernet 与 ADB
PASS。Wi-Fi FAIL，且启动中稳定重复：

```text
mmc2: new SDIO card
aicbsp_sdio_probe: matched chip: aic8800d
Set SDIO Clock 66 MHz
aicbsp_8800d_fw_init ... chip rev U04
cmd timed-out
tkn[...] result:-4 cmd:1037 - reqcfm(1038)
wifi start fail
aicbsp_sdio_remove
mmc2: card ... removed
```

`aic8800_fdrv.ko`、`aic8800_bsp.ko`、`aic8800_btlpm.ko` 与 firmware 文件均存在；
首个可重复 boundary 是 AIC firmware START_APP confirmation 缺失，不是 Android Wi-Fi
HAL/framework 或 simple missing payload。当前仓库没有随该报告提供 raw UART capture，故不记录
虚构的文件路径或 hash。r1 结论为 **PARTIAL PHYSICAL PASS / WIRELESS FAIL**。

## Completed physical diagnostic: m8-kernel-5.4.302-r2

候选：`out/candidates/m8-kernel-5.4.302-r2/x12-m8-kernel-5.4.302-r2.img`，
1,031,739,392 bytes / SHA-256
`A2963FD46685829774DBF5EA2E899ED5844BF44329BC8F46788F1D14D09AA036`。
它只把 pinned AIC BSP runtime request 从 70 MHz 改为 50 MHz，复用 r1 Image/boot/DT、
userspace 与 21 个 module bytes。用户已另行授权并完成测试，结果为
**PHYSICALLY FAILED — 50 MHZ HYPOTHESIS REJECTED**：

```text
mmc2: new SDIO card
aicbsp_sdio_probe: matched chip: aic8800d
Set SDIO Clock 50 MHz
cmd timed-out
tkn[476] flags:0012 result:-4 cmd:1037 - reqcfm(1038)
wifi start fail
mmc2: card ... removed
```

该序列在多次 power/re-enumeration 中稳定重复。Android 12 boot complete，Ethernet 与
ADB 正常；`aic8800_bsp`/`aic8800_btlpm` 保持，`aic8800_fdrv` 不保持，`wlan0` 不存在。
HAL service 存在，framework `CMD_STA_START_FAILURE`/`DisabledState` 是 firmware init
失败的下游结果。不要再测试任意 SDIO frequency。

后续离线 source diff 证明 retained→5.4.302 的 generic CMD52/CMD53、SDIO IRQ、request
completion、host claim/release 与 SUNXI host live path 未改变，没有一个 LTS delta 足以
支持行为回退。后续 r3 只增加 START_APP-gated AIC BSP observability，不改变这些行为。

## Physical diagnostic result: m8-kernel-5.4.302-r3

候选：`out/candidates/m8-kernel-5.4.302-r3/x12-m8-kernel-5.4.302-r3.img`，
1,031,739,392 bytes / SHA-256
`9E52B601F11F9368599098B4C5082037D010930D9B424D7CA2828977047C1B28`。
状态为 **PHYSICAL DIAGNOSTIC PASS / WI-FI FAIL / POST-TX PRE-AIC-HANDLER BOUNDARY PROVEN**。

r3 回到 r1 的 `FEATURE_SDIO_CLOCK=70000000` 功能基线，并严格复用 r1 Image、boot、DT、
userspace 和其他 21 个 module bytes；只有 `aic8800_bsp.ko` 加入动态 runtime token /
transaction-window trace。它在原有 START_APP success/timeout 后只输出一条
`AIC_STARTAPP_TRACE:`，用于回答：

1. final 1037 CMD53 TX 是否尝试并成功返回；
2. TX 后是否有可归属于该 transaction window 的 AIC IRQ，以及 block-count CMD52 结果；
3. CMD53 RX 是否发生、requested length/return 与 frame type/message ID；
4. 1038 是否进入 dispatch；
5. 1038 是否匹配当前 runtime token 并完成 waiter。

用户手动打开一次 Wi-Fi 后，第一次启动与 framework 的一次自动 self-recovery 均保留
`Set SDIO Clock 66 MHz`，并产生相同 runtime token 476 trace：`tx_bus_ret=0`、
`tx_cmd53_state=2`、`tx_cmd53_len=512`、`tx_cmd53_ret=0`，随后
`irq_count=0`、`rx_cmd53_count=0`、`cfm_seen=0`、`token_match=0`、`completion=0`，再发生
1037→1038 timeout 与 SDIO teardown。`irq_block_count_ret=-115` 和 `rx_cmd53_ret=-115` 是
未触发路径保留的 `-EINPROGRESS` sentinel，不是实际 I/O error。

证据为 `/work/device-evidence/m8-kernel-5.4.302-r3/20260823-wifi-on/` 下的
`r3-wifi-on-kernel.txt`（39,758 bytes / SHA-256
`2EB7A8581C0B201A282995D7BA07AA24550D767A764B7A12DAE66113EDF6B0A2`）与
`r3-wifi-on-all.txt`（5,673,014 bytes / SHA-256
`A0FBC16964616C0E8BF24D00365B36C6B4C8CC7370250EB4A8AEE53579E36287`）；目录中没有 UART
文件。Host-side CMD53 return 0 不证明 card/firmware 已消费 START_APP；`irq_count=0` 也不
单独证明 card 未断言中断或 host 丢失中断。当前 r3 缺少 card CCCR pending 的安全接口，
因此不得从该结果选择行为修复。后续任何新诊断候选仍需单独明确物理授权并保持 Test8r2
rollback 边界。

## Physical diagnostic result: m8-kernel-5.4.302-r4

候选：`out/candidates/m8-kernel-5.4.302-r4/x12-m8-kernel-5.4.302-r4.img`，
1,031,739,392 bytes / SHA-256
`18565E4F94FF1A843EA859254800E5E2BA732FBFE47410E86D6577038F85DFCA`。
状态为 **PHYSICAL DIAGNOSTIC PASS / WI-FI FAIL / NO PERSISTENT FUNCTION PENDING AT TIMEOUT**；
该历史 r4 结果使当时 Gate 2 保持 CLOSED，后续 r5 已关闭此 wireless checkpoint。

r4 保留 r1/r3 的 70 MHz、Image、boot、DT、Android 12 userspace 和其他 21 modules，只在
原 START_APP timeout 已成立后、teardown 之前，由 `aic8800_bsp.ko` 读取 read-only CCCR
`INTx`，再读取 `IENx`，并记录 function、host/core pending、IRQ claim 与 handler 安装状态。
没有改 START_APP timeout、retry、firmware、clock、MMC behavior 或 timeout 前控制流。
离线检查确认 AIC exported-symbol CRC 与 r1 完全一致，避免 preserved `aic8800_fdrv.ko`
发生 symbol-version mismatch；AVB/ext4/LP/IMAGEWTY 和 single-module preservation PASS。

用户手动打开一次 Wi-Fi 后，该次尝试及一次正常 framework `WifiSelfRecovery` 均记录 token
476、`tx_bus_len=24 tx_bus_ret=0`、`tx_cmd53_state=2 tx_cmd53_len=512 tx_cmd53_ret=0`，随后
`irq_count=0 rx_cmd53_count=0 cfm_seen=0 token_match=0 completion=0`。两次 timeout snapshot 都是
`timeout_func=1 host_cap_sdio_irq=1 host_irq_pending=0 irq_claimed=1 handler_installed=1`、
`cccr_intx=0x00/ret=0`、`cccr_ienx=0x03/ret=0`。这只证明没有标准 function-1 pending 状态
保留到两秒 snapshot；不证明 card 未短暂 assert、自清或产生 malformed IRQ，也不证明 firmware
failure。自然启动的一次 `aicwf_sdio_hal_irqhandler: Interrupt but no data` 证明更早状态下 AIC
handler 曾实际进入，但不证明 START_APP response IRQ 正确。

后续 exact firmware/source archaeology 找到 U04 `fmacfw.bin` 内 post-start 1037 handler：它
allocate/send 1038，并在 send 前输出 `DBG: FW started`。没有找到 exact U04 boot-ROM consumer、
AUTO handoff 或 source-proven read-only dequeue/boot/FMAC-ready state；`bootstatus` 只存在于缺失的
1038 payload 且被 host 当作 `hwinfo_r`。该 archaeology 本身没有产生 r5，但随后的
accepted-driver semantic audit 证明 working BSP 的 upload/START_APP base 是 `0x00120000`，r1-r4
则因 donor preprocessor guard/Makefile define 不一致而编译成 `0x00110000`。这使仅修正该 guard、
保留 r4 trace 的 r5 单变量 design 成立。当时尚未 build/实测；后续 r5 结果已在下节关闭该
边界。不同芯片 FNCALL/DUMMY 或随机寄存器读取仍不成立。完整历史证据与 lineage 限制见
`docs/m8/candidates/m8-kernel-5.4.302-r4.md`。

## Physical result: m8-kernel-5.4.302-r5

候选：`out/candidates/m8-kernel-5.4.302-r5/x12-m8-kernel-5.4.302-r5.img`，
1,031,739,392 bytes / SHA-256
`A185B0A3C7516FBC9D34F61B3218171F07BDA00B84903A644D2D71FBB1DCC28F`。
状态为 **PHYSICAL PASS / WI-FI PASS / PRESERVATION CHECKPOINT CLOSED**。

r5 只把 `RAM_FMAC_FW_ADDR` guard 从未实际定义的 `CONFIG_AIC_INTF_SDIO` 改为 build 已提供的
`AICWF_SDIO_SUPPORT`。Final packaged `aic8800_bsp.ko` 为 129,976 bytes / SHA-256
`2BF0F46C69968408544D8F1B344C0999C6B2E69E03C7E24A5EB8D2A23133D03A`；final-ELF audit 证明
FMAC upload=`0x00120000`、patch read=`0x00120180`、START_APP=`0x00120000`，与 accepted working
5.4.125 BSP 一致。r4 三值分别为 `0x00110000`、`0x00110180`、`0x00110000`。

r4 START_APP trace/timeout CCCR、70 MHz、timeout/retry、MMC/SUNXI、firmware、Image/boot/ramdisk/DT、
Android userspace 与其他 21 modules 保持。Relative r4 outer delta 仅 `super.fex`/`Vsuper.fex`；
AVB/FEC、ext4/e2fsck、LP/sparse round trip、IMAGEWTY 与 focused tests PASS。完整记录见
`docs/m8/candidates/m8-kernel-5.4.302-r5.md`。

用户已完成 physical validation。`uname -a` 为
`Linux localhost 5.4.302+ #1 SMP PREEMPT Thu Aug 13 22:30:00 +08 2026 armv8l`，
`sys.boot_completed=1`。AIC FMAC/BTLPM/BSP/rfkill modules 加载，initial probe/66 MHz/FMAC/
supplicant startup 成功；旧 error filter 为空。Physical Wi-Fi OFF→ON 后 old wlan0/SDIO/bus/
thread/subsystem teardown 完整，再 fresh init 成功。一次 `aicsdio: write retry: 20` 后继续到
functional/validated connection，按 non-fatal transient 记录。Android 完成 association、4-way/
group handshake、DHCP `192.168.1.8/24`、gateway `192.168.1.254` 与 validated L3；IP/DNS ping
均 4/4、0% loss，Wi-Fi ADB reconnect PASS。Post-cycle old error filter 再次为空。

Original raw ADB captures 由用户在设备外部收集且未在 VM 找到；tracked evidence 只含 reviewed
facts/excerpts，不虚构 raw file/hash。详见
`docs/m8/device-tests/20260825-m8-kernel-5.4.302-r5/`。Rollback 仍为 frozen
`m8b-remote-r1`/Test8r2；本结果不授权后续 r3 flash/physical action。

## Accepted physical result: m8b-remote-r1

当前运行镜像：

- path：`out/candidates/m8b-remote-r1/x12-m8b-remote-r1.img`
- size：1031723008 bytes
- SHA-256：`F3B09E5565AC4ED4E5EE326D392622E7B036A8519B8444B966E77CC4751B814A`
- direct predecessor / rollback：accepted `m8b-ime-r1`

现场与运行时结果：

- Projectivy、物理遥控、Wi-Fi、Bluetooth 与 LeanbackIME 基础回归 PASS。
- Remote Service 5.2.473254133 运行；`BLUETOOTH_CONNECT` 为 `GRANTED_BY_DEFAULT`，没有手工 `pm grant`。
- TCP 6466/6467 监听；system_ext RRO 存在，framework resource lookup 精确返回 Remote Service package。
- official Google TV iPhone discovery、pair、DPAD、BACK、HOME、Volume±、Mute 与真实 EditText phone keyboard PASS。
- 手机 text-input session 活跃时 `Use the keyboard on your mobile device` 是接受的 Remote 行为；物理遥控仍可导航，不视为 LeanbackIME regression。
- reboot persistence 未单独执行且不声明 PASS；接受为本里程碑非阻塞项。
- `com.android.vending`、`com.google.android.gms`、`com.google.android.gsf` 均不存在，故没有可执行的 Play runtime regression test。

完整最小证据见 `docs/m8/device-tests/20260816-m8b-remote-r1/`。LeanbackIME 首次调用延迟另列低优先级 controlled cold/warm investigation，不在当前 accepted baseline 上盲改。

## 强制回滚

| Role | Path | SHA-256 |
|---|---|---|
| r13 golden rollback | `out/candidates/m8a-initial-atv-r13/x12-m8a-initial-atv-r13.img` | `1D367F7091A7BD6A0791B2CFE45E7AAB551E0312D8C68136548A4927354A8E06` |
| Test8r2 rollback | `C:\Users\tiany\Documents\ubox10-rom改造\out\candidates\test8r2-restore-contacts-provider-r1\x12-test8r2-restore-contacts-provider.img` | `6A52F3388E9ABF6AFA8A701CFD7198FE6C0090F16531F6E3BD3949E760892EC8` |
| Stock recovery | `C:\Users\tiany\Documents\ubox10-rom改造\x12-1024.img` | `371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065` |

Physical flashing requires a separate explicit user authorization. Never overwrite, rename or modify rollback sources.
