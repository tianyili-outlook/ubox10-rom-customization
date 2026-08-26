# Prototype B r1 keeps the exact generic Android 16 arm64+arm board shape and
# assigns only the accepted Allwinner board-platform name needed to build the
# matching gralloc.apollo provider.
include device/generic/arm64/BoardConfig.mk

TARGET_BOARD_PLATFORM := apollo
