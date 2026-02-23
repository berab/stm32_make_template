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
# Build configs are either N6-DK (default) or N6-DK-legacy, N6-Nucleo
BUILD_CONF ?= N6-Nucleo
# Generate lst files with gcc (set it to a value to generate listings)
GENERATE_LISTINGS=
# AI
# Processed on NPU or CM55
MODEL_DIR = onnx_models
MODEL = network
# MODEL = fff_v1
MODEL_OUTPUT_DIR = st_ai_output
AI_FLAGS = --st-neural-art

######################################
# building variables
######################################
OPT = -Os -g3

ifeq ($(SHORT_ENUM),y)
OPT += -fshort-enums
else ifeq ($(SHORT_ENUM),n)
# This option will generate link-time warnings with most versions of gcc -> use -Wl,--no-enum-size-warning if needed... 
OPT += -fno-short-enums
endif

#######################################
# paths
#######################################
AICORE_PATH = ./AI
PROJECT_PATH = .
CORE_PATH = $(PROJECT_PATH)/Core
VALIDATION_PATH = $(PROJECT_PATH)/X-CUBE-AI/App
MIDDLEWARES_PATH = $(AICORE_PATH)/Middlewares/ST
# --- ATON specific
ATON_PATH = $(PROJECT_PATH)/X-CUBE-AI/atonn
ATON_RT_PATH = $(AICORE_PATH)/Middlewares/ST/AI/Npu/ll_aton
# --- Drivers specific
BSP_PATH = $(PROJECT_PATH)/Drivers/BSP
CMSIS_PATH = $(PROJECT_PATH)/Drivers/CMSIS
N6_DRIVER_PATH = $(PROJECT_PATH)/Drivers/STM32N6xx_HAL_Driver
DK_DRIVER_PATH = $(BSP_PATH)/STM32N6570-DK
NUCLEO_DRIVER_PATH = $(BSP_PATH)/STM32N6xx_Nucleo

######################################
# source
######################################
# C sources
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/aiPbIO.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/aiPbMemRWServices.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/aiPbMgr.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/aiTestHelper.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/aiTestUtility.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/ai_device_adaptor.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/lc_print.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/pb_common.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/pb_decode.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/pb_encode.c
VALIDATION_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/stm32msg.pb.c
VALIDATION_SOURCES += $(VALIDATION_PATH)/$(MODEL).c

ATON_SOURCES += $(ATON_RT_PATH)/ll_aton.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_aton_cipher.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_aton_dbgtrc.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_aton_debug.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_aton_lib.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_aton_lib_sw_operators.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_aton_rt_main.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_aton_runtime.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_aton_util.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_sw_float.c
ATON_SOURCES += $(ATON_RT_PATH)/ll_sw_integer.c
ATON_SOURCES += $(ATON_RT_PATH)/ecloader.c
ATON_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/ai_wrapper_ATON.c
ATON_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/aiValidation_ATON.c
ATON_SOURCES += $(MIDDLEWARES_PATH)/AI/Validation/Src/ai_io_buffers_ATON.c

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
APP_PATH = $(CORE_PATH)/Src
APP_SOURCES += $(APP_PATH)/main.c
APP_SOURCES += $(APP_PATH)/stm32n6xx_it.c
APP_SOURCES += $(APP_PATH)/md5.c
APP_SOURCES += $(APP_PATH)/system_clock_config.c
APP_SOURCES += $(APP_PATH)/misc_toolbox.c
APP_SOURCES += $(MIDDLEWARES_PATH)/AI/Npu/Devices/STM32N6xx/npu_cache.c
APP_SOURCES += $(MIDDLEWARES_PATH)/AI/Npu/Devices/STM32N6xx/mcu_cache.c
APP_SOURCES += $(APP_PATH)/sysmem.c
APP_SOURCES += $(MIDDLEWARES_PATH)/AI/Misc/Src/syscalls.c

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
C_DEFS += -DLL_ATON_DUMP_DEBUG_API
C_DEFS += -DLL_ATON_PLATFORM=LL_ATON_PLAT_STM32N6
C_DEFS += -DLL_ATON_OSAL=LL_ATON_OSAL_BARE_METAL
C_DEFS += -DLL_ATON_RT_MODE=LL_ATON_RT_ASYNC
C_DEFS += -DLL_ATON_SW_FALLBACK
C_DEFS += -DLL_ATON_EB_DBG_INFO
C_DEFS += -DLL_ATON_DBG_BUFFER_INFO_EXCLUDED=1

# C includes
C_INCLUDES += -I$(CMSIS_PATH)/Core/Include
C_INCLUDES += -I$(CMSIS_PATH)/Device/ST/STM32N6xx/Include
C_INCLUDES += -I$(CMSIS_PATH)/Device/ST/STM32N6xx/Include/Templates
C_INCLUDES += -I$(CMSIS_PATH)/DSP/Include
C_INCLUDES += -I$(N6_DRIVER_PATH)/Inc
C_INCLUDES += -I$(CORE_PATH)/Inc
C_INCLUDES += -I$(ATON_PATH)
C_INCLUDES += -I$(ATON_RT_PATH)
C_INCLUDES += -I$(MIDDLEWARES_PATH)/AI/Inc
C_INCLUDES += -I$(VALIDATION_PATH)
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
else ifeq ($(BUILD_CONF),N6-DK-RELOC)
-include mk/N6-DK.mk
-include mk/reloc.mk
else ifeq ($(BUILD_CONF),N6-DK-USB)
-include mk/N6-DK.mk
-include mk/USBx.mk
else ifeq ($(BUILD_CONF),N6-DK-USB-RELOC)
-include mk/N6-DK.mk
-include mk/USBx.mk
-include mk/reloc.mk
else ifeq ($(BUILD_CONF),N6-Nucleo-USB)
-include mk/N6-Nucleo.mk
-include mk/USBx.mk
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
# link script
LDSCRIPT = ./STM32N657xx.ld

# For relocatable builds, a different linker script is to be used (to give more space available to install models)
RELOC_BUILDS=N6-DK-RELOC N6-DK-USB-RELOC
ifneq ($(filter $(RELOC_BUILDS),$(BUILD_CONF)),)
LDSCRIPT = ./STM32N657xx-reloc.ld
endif

LDFLAGS_OTHERS = -Wl,--wrap=malloc --verbose

# libraries
LIBS = -lc -lm -lnosys -l:NetworkRuntime1100_CM55_GCC.a
LIBDIR = $(AICORE_PATH)/Middlewares/ST/AI/Lib/GCC/ARMCortexM55
LDFLAGS = $(MCU) -specs=nano.specs -T$(LDSCRIPT) -L$(LIBDIR) $(LIBS) $(LDFLAGS_OTHERS) -Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref -Wl,--gc-sections
# Uncomment to enable %f formatted output
# LDFLAGS += -u _printf_float
LDFLAGS += -Wl,--print-memory-usage

#######################################
# build the application into BUILD_DIR (all .o end up in a directory based on their "category")
#######################################
OBJECTS += $(addprefix $(BUILD_DIR)/,$(notdir $(ASM_SOURCES_S:.S=.o)))

APP_OBJ = $(addprefix $(BUILD_DIR)/app/,$(addsuffix .o,$(basename $(notdir $(APP_SOURCES)))))
DRIVER_OBJ = $(addprefix $(BUILD_DIR)/drivers/,$(addsuffix .o,$(basename $(notdir $(DRIVER_SOURCES)))))
ATON_OBJ = $(addprefix $(BUILD_DIR)/aton/,$(addsuffix .o,$(basename $(notdir $(ATON_SOURCES)))))
VALIDATION_OBJ = $(addprefix $(BUILD_DIR)/validation/,$(addsuffix .o,$(basename $(notdir $(VALIDATION_SOURCES)))))
USB_OBJ = $(addprefix $(BUILD_DIR)/usb/,$(addsuffix .o,$(basename $(notdir $(USB_SOURCES)))))
ASM_OBJ = $(addprefix $(BUILD_DIR)/asm/,$(addsuffix .o,$(basename $(notdir $(ASM_SOURCES)))))

OBJECTS+=$(APP_OBJ) $(DRIVER_OBJ) $(ATON_OBJ) $(VALIDATION_OBJ) $(ASM_OBJ) $(USB_OBJ)

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
$(foreach i,$(shell seq 1 1 $(words $(ATON_SOURCES))),$(eval $(call make_obj_c_rule,$(word $(i),$(ATON_OBJ)),$(word $(i),$(ATON_SOURCES)))))
$(foreach i,$(shell seq 1 1 $(words $(VALIDATION_SOURCES))),$(eval $(call make_obj_c_rule,$(word $(i),$(VALIDATION_OBJ)),$(word $(i),$(VALIDATION_SOURCES)))))
$(foreach i,$(shell seq 1 1 $(words $(USB_SOURCES))),$(eval $(call make_obj_c_rule,$(word $(i),$(USB_OBJ)),$(word $(i),$(USB_SOURCES)))))
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

$(MODEL_OUTPUT_DIR):
	stedgeai generate -m $(MODEL_DIR)/$(MODEL)_uint8.onnx --target stm32n6 $(AI_FLAGS) --name $(MODEL)
	cp $(MODEL_OUTPUT_DIR)/* $(VALIDATION_PATH)/ -r

# Converting meomry files to .hex / not sure why xd
convert:
	$(CP) --change-addresses 0x71000000 -Ibinary -Oihex $(MODEL_OUTPUT_DIR)/$(MODEL)_atonbuf.xSPI2.raw $(MODEL_OUTPUT_DIR)/$(MODEL)_atonbuf.xSPI2.hex

reset:
	$(st_prog) -q -c port=SWD mode=powerdown freq=2000 ap=1

flash:
	$(st_prog) -q -c port=SWD mode=hotplug ap=1 --extload $(st_prog_bin)/ExternalLoader/MX25UM51245G_STM32N6570-NUCLEO.stldr --download st_ai_output/$(MODEL)_atonbuf.xSPI2.hex --verify

gdb_server:
	$(stlink) -d --frequency 2000 --apid 1 -v --port-number 61234 -cp $(st_prog_bin)

debug:
	$(GDB) -batch --command=AI/Projects/STM32N6570-DK/Applications/NPU_Validation/armgcc/n6_commands.gdb AI/Projects/STM32N6570-DK/Applications/NPU_Validation/armgcc/build/N6-Nucleo/Project.elf

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
	@echo  ATON_SOURCES = $(ATON_OBJ)
	@echo
	@echo  ASM_SOURCES = $(ASM_SOURCES)
	@echo
	@echo  USB_SOURCES = $(USB_SOURCES)
	@echo
	@echo  C_SOURCES = $(C_SOURCES)
#######################################
# dependencies
#######################################
-include $(call rwildcard,$(BUILD_DIR),*.d)
