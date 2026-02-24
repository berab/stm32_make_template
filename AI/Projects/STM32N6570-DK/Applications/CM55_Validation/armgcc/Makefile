######################################
# helpers
######################################
# Recursive wildcard: returns all files matching a given pattern
# $(call rwildcard,$(BUILD_DIR),*.d) -> returns a list of files in $(BUILD_DIR) matching the pattern *.d
rwildcard=$(foreach d,$(wildcard $(1:=/*)),$(call rwildcard,$d,$2) $(filter $(subst *,%,$2),$d))

######################################
# target
######################################
TARGET = Project
# Build configs are either N6-DK (default) or N6-Nucleo
BUILD_CONF ?= N6-DK
# Generate lst files with gcc (set it to a value to generate listings)
GENERATE_LISTINGS=

######################################
# building variables
######################################
OPT = -Os -g3

#######################################
# paths
#######################################
BASE_PATH = ../../..
PROJECT_PATH = $(BASE_PATH)/Applications/CM55_Validation
CORE_PATH = $(PROJECT_PATH)/Core
VALIDATION_PATH = $(PROJECT_PATH)/X-CUBE-AI/App
MIDDLEWARES_PATH = $(BASE_PATH)/../../Middlewares/ST
# --- Drivers specific
BSP_PATH = $(PROJECT_PATH)/../Drivers/BSP
CMSIS_PATH = $(PROJECT_PATH)/../Drivers/CMSIS
N6_DRIVER_PATH = $(PROJECT_PATH)/../Drivers/STM32N6xx_HAL_Driver
DK_DRIVER_PATH = $(BSP_PATH)/STM32N6570-DK
NUCLEO_DRIVER_PATH = $(BSP_PATH)/STM32N6xx_Nucleo

######################################
# source
######################################
# C sources
# 
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/aiPbIO.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/aiPbMemRWServices.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/aiPbMgr.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/aiTestHelper.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/aiTestUtility.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/aiValidation.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/ai_device_adaptor.c
# VALIDATION_SOURCES += $(VALIDATION_PATH)/app_x-cube-ai.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/lc_print.c
VALIDATION_SOURCES += $(VALIDATION_PATH)/network.c
VALIDATION_SOURCES += $(VALIDATION_PATH)/network_data.c
VALIDATION_SOURCES += $(VALIDATION_PATH)/network_data_params.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/pb_common.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/pb_decode.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/pb_encode.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/stm32msg.pb.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/syscalls.c
DRIVER_SOURCES += $(CMSIS_PATH)/Device/ST/STM32N6xx/Source/Templates/system_stm32n6xx_fsbl.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_bsec.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_cacheaxi.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_cortex.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_gpio.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_i2c.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_i2c_ex.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_pwr.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_pwr_ex.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_rcc.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_rcc_ex.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_rif.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_uart.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_xspi.c
# CMSIS STUFF #
#DRIVER_SOURCES += $(wildcard $(CMSIS_PATH)/DSP/Source/SupportFunctions/*.c)

# EndOfCMSIS #
APP_SOURCES += $(CORE_PATH)/Src/main.c
APP_SOURCES += $(CORE_PATH)/Src/stm32n6xx_it.c
APP_SOURCES += $(CORE_PATH)/Src/md5.c
APP_SOURCES += $(CORE_PATH)/Src/system_clock_config.c
APP_SOURCES += $(CORE_PATH)/Src/misc_toolbox.c
APP_SOURCES += $(MIDDLEWARES_PATH)/AI/Npu/Devices/STM32N6xx/mcu_cache.c
#C_SOURCES += $(CORE_PATH)/Src/sysmem.c
C_SOURCES += $(APP_SOURCES)
C_SOURCES += $(VALIDATION_SOURCES)
C_SOURCES += $(ATONN_SOURCES)
C_SOURCES += $(DRIVER_SOURCES)


#C_SOURCES += Src/check_malloc.c
#C_SOURCES += Src/stm32n6xx_hal_msp.c
#C_SOURCES += Src/system_stm32n6xx_s.c
#C_SOURCES += Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_cortex.c
#C_SOURCES += Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_pwr.c
#C_SOURCES += Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_pwr_ex.c
#C_SOURCES += Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_rcc.c
#C_SOURCES += Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_rcc_ex.c
#C_SOURCES += Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal.c
#C_SOURCES += Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_uart.c
#C_SOURCES += Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_gpio.c

# ASM sources
ASM_SOURCES += ./startup_stm32n657xx.s


#######################################
# binaries
#######################################
PREFIX = arm-none-eabi-
# The gcc compiler bin path can be either defined in make command via GCC_PATH variable (> make GCC_PATH=xxx)
# either it can be added to the PATH environment variable.
ifdef GCC_PATH
CC = $(GCC_PATH)/$(PREFIX)gcc
AS = $(GCC_PATH)/$(PREFIX)gcc -x assembler-with-cpp
CP = $(GCC_PATH)/$(PREFIX)objcopy
SZ = $(GCC_PATH)/$(PREFIX)size
else
CC = $(PREFIX)gcc
AS = $(PREFIX)gcc -x assembler-with-cpp
CP = $(PREFIX)objcopy
SZ = $(PREFIX)size
endif
HEX = $(CP) -O ihex
BIN = $(CP) -O binary -S

#######################################
# CFLAGS
#######################################
CPU = -mcpu=cortex-m55 -mcmse -mthumb
FPU = -mfpu=auto -mfloat-abi=hard


# mcu
MCU = $(CPU) $(FPU)

# others c flags
CFLAGS_OTHERS = -std=c11

# C defines
C_DEFS += -DSTM32N657xx

C_DEFS += -DUSE_FULL_ASSERT
C_DEFS += -DUSE_FULL_LL_DRIVER
C_DEFS += -DUSER_VECT_TAB_ADDRESS
C_DEFS += -DVECT_TAB_SRAM

# C includes
C_INCLUDES += -I$(CMSIS_PATH)/Core/Include
C_INCLUDES += -I$(CMSIS_PATH)/Device/ST/STM32N6xx/Include
C_INCLUDES += -I$(CMSIS_PATH)/Device/ST/STM32N6xx/Include/Templates
C_INCLUDES += -I$(CMSIS_PATH)/DSP/Include
C_INCLUDES += -I$(N6_DRIVER_PATH)/Inc
C_INCLUDES += -I$(CORE_PATH)/Inc
C_INCLUDES += -I$(ATONN_PATH)
C_INCLUDES += -I$(ATONN_RT_PATH)
C_INCLUDES += -I$(VALIDATION_PATH)
C_INCLUDES += -I$(VALIDATION_PATH)/..
C_INCLUDES += -I$(VALIDATION_PATH)/../Target
C_INCLUDES += -I$(MIDDLEWARES_PATH)/AI/Npu/Devices/STM32N6xx
C_INCLUDES += -I$(MIDDLEWARES_PATH)/AI/Inc
C_INCLUDES += -I$(MIDDLEWARES_PATH)/AI/Misc/Inc
C_INCLUDES += -I$(MIDDLEWARES_PATH)/AI/Validation/Inc


# DEPENDING ON THE TARGET BUILD, add extra files/defines:
ifeq ($(BUILD_CONF),N6-DK-legacy)
-include mk/N6-DK-legacy.mk
else ifeq ($(BUILD_CONF),N6-Nucleo)
-include mk/N6-Nucleo.mk
else ifeq ($(BUILD_CONF),N6-DK)
-include mk/N6-DK.mk
else
$(error Please use a known build configuration (N6-DK, N6-Nucleo, ...))
endif

# Build path
BUILD_DIR = build/$(BUILD_CONF)

ASFLAGS = $(MCU) $(AS_DEFS) $(AS_INCLUDES) $(OPT) -Wall -fdata-sections -ffunction-sections
CFLAGS = $(CFLAGS_OTHERS) $(MCU) $(C_DEFS) $(C_INCLUDES) $(OPT) -Wall -fdata-sections -ffunction-sections
# Generate dependency information
CFLAGS += -MMD -MP -MF"$(@:%.o=%.d)"

#######################################
# LDFLAGS

#######################################
# link script
LDSCRIPT = ./STM32N657xx.ld

LDFLAGS_OTHERS = -Wl,--wrap=malloc --verbose


# libraries
LIBS = -lc -lm -lnosys -l:NetworkRuntime1100_CM55_GCC.a
LIBDIR = $(MIDDLEWARES_PATH)/AI/Lib/GCC/ARMCortexM55
LDFLAGS = $(MCU) -specs=nano.specs -T$(LDSCRIPT) -L$(LIBDIR) $(LIBS) $(LDFLAGS_OTHERS) -Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref -Wl,--gc-sections
# Uncomment to enable %f formatted output
# LDFLAGS += -u _printf_float
LDFLAGS += -Wl,--print-memory-usage

#######################################
# build the application into BUILD_DIR (all .o in build dir with same structure as in original tree)
#######################################

OBJECTS += $(addprefix $(BUILD_DIR)/,$(notdir $(ASM_SOURCES_S:.S=.o)))

APP_OBJ = $(addprefix $(BUILD_DIR)/app/,$(addsuffix .o,$(basename $(notdir $(APP_SOURCES)))))
DRIVER_OBJ = $(addprefix $(BUILD_DIR)/drivers/,$(addsuffix .o,$(basename $(notdir $(DRIVER_SOURCES)))))
VALIDATION_OBJ = $(addprefix $(BUILD_DIR)/validation/,$(addsuffix .o,$(basename $(notdir $(VALIDATION_SOURCES)))))
ASM_OBJ = $(addprefix $(BUILD_DIR)/asm/,$(addsuffix .o,$(basename $(notdir $(ASM_SOURCES)))))

OBJECTS+=$(APP_OBJ) $(DRIVER_OBJ) $(VALIDATION_OBJ) $(ASM_OBJ)

## Function to "pretty"-print steps in the logfile - 1 argument=string to print
define PRINT_STEP
@echo ""
@echo ""
@echo "--- $(1)"
endef

ifeq ($(GENERATE_LISTINGS),1)
define COMPILE_C
	@mkdir -p $(dir $@)
	$(call PRINT_STEP,Compiling $$@)
# Generate info from the assembler 
# The -a option tells the assembler to generate a listing file, and the -ad option tells the assembler to include debugging information in the listing file.
# he -alms option is a specific option for the GNU assembler (as) that tells it to generate a listing file
	$(CC) -c $(CFLAGS) -Wa,-a,-ad,-alms=$(dir $$@)/$(notdir $(<:.c=.lst)) $$< -o $$@
endef
else
define COMPILE_C
	@mkdir -p $(dir $1)
	$(call PRINT_STEP,Compiling $1)
	$(CC) -c $(CFLAGS) $2 -o $1
endef
endif

## Function to create make rules for each file -- this will allow to create a clean build directory
## Heavy use of $$ to prevent eval expansion at eval time.
define make_obj_c_rule
$1: $2 Makefile
	$$(call COMPILE_C,$$@,$$<)
endef

define make_obj_asm_rule
$1: $2 Makefile
	@mkdir -p $$(dir $$@)
	$$(call PRINT_STEP,Compiling $$@ $$<)
	$(AS) -c $$(CFLAGS) $$< -o $$@
endef
############################ Targets ##########################
.PHONY: clean test
# default action: build all
all: $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin

# For each element of the list [1...length(app_sources)], create a rule by calling make_obj with arguments: $1=APP_OBJ[i], $2=APP_SOURCES[i]
# Using seq <start> <step> <end> to generate the list of indices --step is mandatory on some flavors of seq (eg macOS)
$(foreach i,$(shell seq 1 1 $(words $(APP_SOURCES))),$(eval $(call make_obj_c_rule,$(word $(i),$(APP_OBJ)),$(word $(i),$(APP_SOURCES)))))
$(foreach i,$(shell seq 1 1 $(words $(DRIVER_SOURCES))),$(eval $(call make_obj_c_rule,$(word $(i),$(DRIVER_OBJ)),$(word $(i),$(DRIVER_SOURCES)))))
$(foreach i,$(shell seq 1 1 $(words $(VALIDATION_SOURCES))),$(eval $(call make_obj_c_rule,$(word $(i),$(VALIDATION_OBJ)),$(word $(i),$(VALIDATION_SOURCES)))))
$(foreach i,$(shell seq 1 1 $(words $(ASM_SOURCES))),$(eval $(call make_obj_asm_rule,$(word $(i),$(ASM_OBJ)),$(word $(i),$(ASM_SOURCES)))))

$(BUILD_DIR)/%.o: %.S Makefile | $(BUILD_DIR)
	@mkdir -p $(dir $@)
#	$(call PRINT_STEP,Compiling $@)
ifdef GENERATE_LISTINGS
	$(CC) -c $(CFLAGS) -Wa,-a,-ad,-alms=$(BUILD_DIR)/$(notdir $(<:.c=.lst)) $< -o $@
else
	$(CC) -c $(CFLAGS) $< -o $@
endif

$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS) Makefile
	$(call PRINT_STEP,Linking $@)
	$(CC) $(OBJECTS) $(LDFLAGS) -o $@
	$(SZ) $@

$(BUILD_DIR)/%.hex: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
	$(HEX) $< $@

$(BUILD_DIR)/%.bin: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
	$(BIN) $< $@

$(BUILD_DIR):
	mkdir -p $@

#######################################
# clean up
#######################################
clean:
	-rm -fR $(BUILD_DIR)

test: 
#$(foreach var,$(.VARIABLES),$(info $(var) = $($(var))))
#	@echo OBJECTS = $(OBJECTS)
	@echo  APP_SOURCES = $(APP_OBJ)
	@echo
	@echo  VALIDATION_SOURCES = $(VALIDATION_OBJ)
	@echo
	@echo  DRIVER_SOURCES = $(DRIVER_OBJ)
	@echo
	@echo  ASM_SOURCES = $(ASM_SOURCES)
	@echo
	@echo  C_SOURCES = $(C_SOURCES)
#######################################
# dependencies
#######################################
-include $(call rwildcard,$(BUILD_DIR),*.d)

