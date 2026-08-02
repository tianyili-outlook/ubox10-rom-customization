# M8A ATV package evidence

Installed-files evidence confirms:

| Component | Destination |
|---|---|
| TvProvider | system/priv-app |
| SystemUI, TvSettings | system_ext/priv-app |
| TvFrameworkOverlay, TvSettingsProviderOverlay, TvWifiOverlay | product/overlay |
| atv-component-overrides.xml | product/etc/sysconfig |
| TvFrameworkPackageStubs, remoteprovider | installed |

The candidate merges system_ext into system_a at /system_ext because stock has no system_ext logical partition. This preserves the AOSP symlink /system/system_ext -> /system_ext.

AwTvProvision is configured in ubox10.mk but absent from installed-files evidence. It is configured, not delivered. Projectivy, launcher/default HOME, and IME are absent or unproven. These are first-boot/device-only risks, not M8A.2b completion claims.
