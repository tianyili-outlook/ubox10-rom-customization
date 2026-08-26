# DISPOSABLE ARCHITECTURE PROTOTYPE: Android 16 TV on the accepted ARM32
# userspace contract. This deliberately builds only a GSI-style system image.
$(call inherit-product, device/google/atv/products/gsi_tv_base.mk)

# Model this as an upgrade of an Android 12 / VNDK 31 device, not as a new
# Android 16 launch device. Keep only the legacy VNDK snapshot we need.
PRODUCT_SHIPPING_API_LEVEL := 31
PRODUCT_EXTRA_VNDK_VERSIONS := 31

# The retained 5.4 BSP kernel has no pKVM contract and this prototype does not
# build boot, vendor, super, or userdata images.
PRODUCT_BUILD_PVMFW_IMAGE := false

# The accepted API-31 vendor manifest exposes two Allwinner display HALs that
# are device-specific rather than part of the platform FCM. Declare them in the
# device framework matrix so the exact-board VINTF audit can distinguish those
# HALs from the retained BSP kernel's separate CONFIG_NFS_FS deviation.
DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE += \
    device/ubox/ceiling/compatibility_matrix.xml

# The accepted vendor keeps the Apollo platform identity for gralloc/HWC but
# names its ARM32 GLES implementation libGLES_mali.so.  Use the read-only EGL
# suffix contract proven by the r3 field diagnosis; do not bake the temporary
# persist.graphics.egl override into the image.
PRODUCT_SYSTEM_PROPERTIES += \
    ro.hardware.egl=mali

# EventHub canonicalizes the physical input device name "sunxi-ir" to this
# device-specific layout.  It is the exact r7 Generic.kl mapping set plus the
# one proven KEY_OK correction (Linux scanCode 352 -> DPAD_CENTER).
PRODUCT_COPY_FILES += \
    device/ubox/ceiling/sunxi-ir.kl:system/usr/keylayout/sunxi-ir.kl

# This product deliberately contributes the one board-specific layout to the
# inherited ATV GSI system artifact set.
PRODUCT_ARTIFACT_PATH_REQUIREMENT_ALLOWED_LIST += \
    system/usr/keylayout/sunxi-ir.kl

PRODUCT_NAME := ubox10_ceiling_arm
PRODUCT_DEVICE := generic
PRODUCT_BRAND := UBOX10Research
PRODUCT_MODEL := UBOX10 A16 ARM32 architecture prototype
PRODUCT_MANUFACTURER := UBOX10Research
