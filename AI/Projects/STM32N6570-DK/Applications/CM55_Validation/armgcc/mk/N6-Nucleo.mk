#
# Makefile additions for N6-Nucleo
#
C_DEFS += -DUSE_STM32N6xx_NUCLEO

# To prevent configuring external RAM (not present on Nucleo)
C_DEFS += -DNUCLEO_N6_CONFIG=1

# Board-specific includes/sources (BSP + memories management)
C_INCLUDES += -I$(BSP_PATH)/Components/mx25um51245g
C_INCLUDES += -I$(BSP_PATH)/STM32N6xx_Nucleo
C_INCLUDES += -I$(NUCLEO_DRIVER_PATH)

DRIVER_SOURCES += $(NUCLEO_DRIVER_PATH)/stm32n6xx_nucleo.c
DRIVER_SOURCES += $(NUCLEO_DRIVER_PATH)/stm32n6xx_nucleo_xspi.c
DRIVER_SOURCES += $(NUCLEO_DRIVER_PATH)/stm32n6xx_nucleo_bus.c
DRIVER_SOURCES += $(BSP_PATH)/Components/mx25um51245g/mx25um51245g.c