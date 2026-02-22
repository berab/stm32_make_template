hello_world project
-------------------

# Overview
This project is meant to be simple to show how to make an inference, using the output of the atonn compiler.

More advanced use-cases are also useable in this project, as it also can be used to make first baby steps into the epoch controller-process.

# Project build configs
The project contains two build configs:
- N6-DK: Minimal project to perform an inference and output the inference time on the UART

# Use cases

## Template / minimal working example
The "standard" way of using the project is by using the defaults compilation flags for the N6-DK config.

### Possible compilation options
- LL_ATON_RT_MODE
  - LL_ATON_RT_ASYNC: Use IRQ to signal end of an epoch (useful for low-power examples)
  - LL_ATON_RT_POLLING: Use polling from the MCU to find that an epoch is over

Some other configurations can be adapted in the `app_config.h` file:
- VDDCORE_OVERDRIVE
  - 0: use the maximum documented performances of the MCU (CPU@600MHz)
  - 1: "overclock" the MCU (CPU@800MHz): *do not use...*
- USE_UART_BAUDRATE: Used to setup the baudrate to be used on the uart (printf-redirection)
- USE_MCU_DCACHE/ICACHE: Use MCU data-cache / instruction-cache
- USE_EXTERNAL_MEMORY_DEVICES: shall be left to 1 when testing on DK boards, this will ensure external memories (flash and ram) are properly configured
- USE_RETARGET_IO_ON_UART: shall be left to 1 when printf redirection is needed, can be set to 0 if the uart is used for other purposes.
- USE_NPU_CACHE: Use the NPU cache or not.

## Using epoch controller
For using the epoch controller, no additional configuration shall be used, the network.c containing the EC blobs shall be used as a standard network.c file.