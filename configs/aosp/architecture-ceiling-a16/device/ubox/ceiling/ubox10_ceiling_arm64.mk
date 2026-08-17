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

PRODUCT_NAME := ubox10_ceiling_arm64
PRODUCT_DEVICE := generic_arm64
PRODUCT_BRAND := UBOX10Research
PRODUCT_MODEL := UBOX10 A16 mixed architecture prototype
PRODUCT_MANUFACTURER := UBOX10Research
