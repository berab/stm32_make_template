#
# Makefile additions for N6-DK (Current version)
#
C_DEFS += -DUSE_STM32N6570_DK

# N6-DK build conf handles CR5 boards
C_DEFS += -DSTM32N6570_DK_REV=STM32N6570_DK_C01

# Board-specific includes/sources (BSP + memories management)
C_INCLUDES += -I$(BSP_PATH)/Components/mx66uw1g45g
C_INCLUDES += -I$(BSP_PATH)/Components/aps256xx
C_INCLUDES += -I$(BSP_PATH)/STM32N6xx_DK
C_INCLUDES += -I$(DK_DRIVER_PATH)

DRIVER_SOURCES += $(DK_DRIVER_PATH)/stm32n6570_discovery.c
DRIVER_SOURCES += $(DK_DRIVER_PATH)/stm32n6570_discovery_xspi.c
DRIVER_SOURCES += $(DK_DRIVER_PATH)/stm32n6570_discovery_bus.c
DRIVER_SOURCES += $(BSP_PATH)/Components/aps256xx/aps256xx.c
DRIVER_SOURCES += $(BSP_PATH)/Components/mx66uw1g45g/mx66uw1g45g.c