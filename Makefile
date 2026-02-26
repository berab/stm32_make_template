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
GDB_CONFIG := .gdbinit
GDB = gdb-multiarch
DEBUG_PORT := 61234
RESULT_DIR := results
# Generate lst files with gcc (set it to a value to generate listings)
GENERATE_LISTINGS=
# AI
# Processed on NPU or CM55
MODEL_OUT_DIR = st_ai_output
MODEL_DIR = onnx_models
MODEL = network
ifndef ONNX_MODEL
	ONNX_MODEL = $(MODEL)
endif
MODEL_OUTPUT_DIR = st_ai_output
MODEL_WS_DIR = st_ai_ws

######################################
# building variables
######################################
OPT = -Os -g3

#######################################
# paths
#######################################

# ST
stlink =  /opt/st/stm32cubeide_2.0.0/plugins/com.st.stm32cube.ide.mcu.externaltools.stlink-gdb-server.linux64_2.2.300.202509021040/tools/bin/ST-LINK_gdbserver
st_prog_bin = /home/kilic/apps/STM32CubeProgrammer/bin
st_prog = $(st_prog_bin)/STM32_Programmer_CLI
AICORE_PATH = /home/kilic/apps/STEdgeAI/4.0

CORE_PATH = Core
VALIDATION_PATH = X-CUBE-AI/App
MIDDLEWARES_PATH = $(AICORE_PATH)/Middlewares/ST
# --- Drivers specific
BSP_PATH = Drivers/BSP
CMSIS_PATH = Drivers/CMSIS
N6_DRIVER_PATH = Drivers/STM32N6xx_HAL_Driver
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
VALIDATION_SOURCES += $(VALIDATION_PATH)/app_x-cube-ai.c
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
# Makefile additions for N6-Nucleo
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

# Build path
BUILD_DIR = build

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
LIBS = -lc -lm -lnosys -l:NetworkRuntime1200_CM55_GCC.a
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
# all: $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin
all: $(MODEL_OUT_DIR) $(MODEL_WS_DIR) $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin
debug: gdbinit reset run_stlink run_gdb
flash: all reset flash_program

# Numbers to be used as list indices below (up to 200 files per directory !)
NUMBERS := 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 \
   51 52 53 54 55 56 57 58 59 60 61 62 63 64 65 66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100 \
   101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123 124 125 126 127 128 129 130 131 132 133 134 135 136 137 138 139 140 141 142 143 144 145 146 147 148 149 150 \
   151 152 153 154 155 156 157 158 159 160 161 162 163 164 165 166 167 168 169 170 171 172 173 174 175 176 177 178 179 180 181 182 183 184 185 186 187 188 189 190 191 192 193 194 195 196 197 198 199 200

# Generate index sequences for each source list
APP_IDX        := $(wordlist 1,$(words $(APP_SOURCES)),$(NUMBERS))
DRIVER_IDX     := $(wordlist 1,$(words $(DRIVER_SOURCES)),$(NUMBERS))
VALIDATION_IDX := $(wordlist 1,$(words $(VALIDATION_SOURCES)),$(NUMBERS))
ASM_IDX        := $(wordlist 1,$(words $(ASM_SOURCES)),$(NUMBERS))

# For each element of the list [1...length(app_sources)], create a rule by calling make_obj with arguments: $1=APP_OBJ[i], $2=APP_SOURCES[i]
$(foreach i,$(APP_IDX),$(eval $(call make_obj_c_rule,$(word $(i),$(APP_OBJ)),$(word $(i),$(APP_SOURCES)))))
$(foreach i,$(DRIVER_IDX),$(eval $(call make_obj_c_rule,$(word $(i),$(DRIVER_OBJ)),$(word $(i),$(DRIVER_SOURCES)))))
$(foreach i,$(VALIDATION_IDX),$(eval $(call make_obj_c_rule,$(word $(i),$(VALIDATION_OBJ)),$(word $(i),$(VALIDATION_SOURCES)))))
$(foreach i,$(ASM_IDX),$(eval $(call make_obj_asm_rule,$(word $(i),$(ASM_OBJ)),$(word $(i),$(ASM_SOURCES)))))

$(MODEL_OUT_DIR) $(MODEL_WS_DIR): #
	stedgeai generate -m $(MODEL_DIR)/$(ONNX_MODEL)_uint8.onnx --target stm32n6 --c-api legacy --name $(MODEL) --output $(MODEL_OUT_DIR) --memory-pool mypool_N6.json 
	stedgeai generate -m $(MODEL_DIR)/$(ONNX_MODEL)_uint8.onnx --target stm32n6 --c-api legacy --binary --address 0x71000000 --memory-pool mypool_N6.json
	cp $(MODEL_OUT_DIR)/$(MODEL)*{.c,.h,.json,.txt} $(VALIDATION_PATH)/App/ -r

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

$(BUILD_DIR): #
	mkdir -p $@

$(GDB_CONFIG):# 
	@echo " creating .gdbinit..."
	@printf "file $(BUILD_DIR)/$(TARGET).elf\ntarget remote localhost:$(DEBUG_PORT)\nload\nbreak main\ncontinue\nlay next\nlay next\nlay next\nlist\nnext" > $(GDB_CONFIG)

# Converting meomry files to .hex / not sure why xd
convert:
	$(CP) --change-addresses 0x71000000 -Ibinary -Oihex $(MODEL_OUT_DIR)/$(MODEL)_atonbuf.xSPI2.raw $(MODEL_OUT_DIR)/$(MODEL)_atonbuf.xSPI2.hex

reset:
	$(st_prog) -q -c port=SWD mode=powerdown freq=2000 ap=0

flash_model:
	$(st_prog) -q -c port=SWD mode=hotplug ap=0 --extload $(st_prog_bin)/ExternalLoader/MX25UM51245G_STM32N6570-NUCLEO.stldr --download $(MODEL_OUT_DIR)/$(MODEL)_atonbuf.xSPI2.hex --verify

flash_program:
	$(st_prog) -q -c port=SWD -w $(BUILD_DIR)/$(TARGET).elf -rst

run_stlink:
	$(stlink) --frequency 2000 --port-number $(DEBUG_PORT) -cp $(st_prog_bin) --apid 1 -d -v &

run_gdb:
	$(GDB) -batch

gdbinit: $(GDB_CONFIG)

bearme: clean bear

bear:
	@echo "Generating compile_commands.json..."
	bear -- make

tcount: # Put delay in case you don't want to push reset button every time
	@echo "Reading timer count from device..."
	ADDR=$$(arm-none-eabi-nm $(BUILD_DIR)/$(TARGET).elf | grep g_elapsed_ms | awk '{print $$1}' | tr 'a-f' 'A-F'); \
	echo "Reading the timer count at 0x$$ADDR..."; \
	TIME_HEX=$$($(st_prog) -q -c port=SWD -r32 0x$$ADDR 0x1 | grep "$$ADDR : " | cut -d' ' -f3); \
	TIME_DEC=$$(printf "%d" 0x$$TIME_HEX); \
	echo "Value at 0x$$ADDR: hex=$$TIME_HEX, dec=$$TIME_DEC"; \
	echo "$(DEPTH),$(LEAF_WIDTH),$$TIME_DEC" >> $(OUT_DIR)/$(TASK).csv

# gdb_server:
# 	$(stlink) -d --frequency 2000 --apid 1 -v --port-number 61234 -cp $(st_prog_bin)

# run_gdb:
# 	$(GDB) -batch --command=n6_commands.gdb $(BUILD)/$(TARGET).elf

#######################################
# clean up
#######################################
clean:
	-rm -fR $(BUILD_DIR) $(MODEL_WS_DIR)

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

