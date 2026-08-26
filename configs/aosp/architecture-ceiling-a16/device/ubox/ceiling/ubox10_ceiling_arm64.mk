# DISPOSABLE ARCHITECTURE PROTOTYPE: Android 16 TV with AArch64 primary and
# ARM32 secondary userspace. Generic ARM64 supplies the mixed ABI board shape.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, device/google/atv/products/gsi_tv_base.mk)

# Model this as an upgrade of an Android 12 / VNDK 31 device, not as a new
# Android 16 launch device. Keep only the legacy VNDK snapshot we need.
PRODUCT_SHIPPING_API_LEVEL := 31
PRODUCT_EXTRA_VNDK_VERSIONS := 31

# The retained 5.4 BSP kernel has no pKVM contract and this prototype does not
# build boot, vendor, super, or userdata images.
PRODUCT_BUILD_PVMFW_IMAGE := false

# Carry the exact physically accepted Prototype A r4 system composition into
# the mixed product.  The accepted vendor keeps the Apollo board identity;
# only the EGL suffix is selected here.
DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE += \
    device/ubox/ceiling/compatibility_matrix.xml

PRODUCT_SYSTEM_PROPERTIES += \
    ro.hardware.egl=mali

PRODUCT_COPY_FILES += \
    device/ubox/ceiling/sunxi-ir.kl:system/usr/keylayout/sunxi-ir.kl

PRODUCT_ARTIFACT_PATH_REQUIREMENT_ALLOWED_LIST += \
    system/usr/keylayout/sunxi-ir.kl

PRODUCT_NAME := ubox10_ceiling_arm64
PRODUCT_DEVICE := ubox10_ceiling_arm64
PRODUCT_BRAND := UBOX10Research
PRODUCT_MODEL := UBOX10 A16 mixed architecture prototype
PRODUCT_MANUFACTURER := UBOX10Research
