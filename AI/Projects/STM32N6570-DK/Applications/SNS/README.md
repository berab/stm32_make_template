# Example overview

Using "execution in place" from flash memory, perform an inference using the NPU, in a non-secure context.

The description below is done for a N6 in "DEV" boot mode.

# Description

This project is composed of three sub-projects:

- one for the First Stage BootLoader (FSBL)
- one for the secure application part (App_Secure)
- one for the non-secure application part (App_NonSecure).

This application uses Trustzone: the system always boots in SECURE mode, and the secure application is responsible for launching the non-secure app
after proper configuration of the security-related peripherals.

Configuration of the security-related peripherals include:
- Configuring the TrustZone-related components:
	- SAU (by default all memory addresses are tagged as "secure")
	- MPU (can be activated to add an even finer control on memory accesses)
- Configuring the ST IPs:
	- RIFSC (For non-rif-aware peripherals: configures the r/w accesses possible)
	- RISAF (Refines even further the memory ranges defined by SAU)
	- IAC (To gather illegal accesses errors and generate events from it)

Most of the configuration to be done is based on memory partitioning to be done.

## Temporal description of operations

The timeline of operations is as follows:
- FSBL is loaded in RAM by the debugger and started  <- The FSBL executes from RAM (@ 0x3418'0000, this address allows for easy transfer to a "boot-from-flash" scenario)
- The FSBL main tasks are:
	- Configure basic clocks to, at least have a 200MHz clock to drive XSPI2 (external flash)
	- Configure XSPI2 to access external flash, and make the external flash memory-mapped.
	- (optional: Configure the MPU and enable it: make the external flash region executable/read only for example)
	- Jump to Secure App
- The Secure App main tasks are:
	- Configure TrustZone SAU (done through the "partition_stm32n657xx.h" file - [see below](#Memory-partitioning))
	- Configure the NPU for use by the Non-secure part:
		- Power-up the NPU
		- Configure RIFSC for the NPU (tagging its transactions non-secure on the AXI bus / allowing non-secure requests to configure it)
	- Configure RISAF - [see below](#Memory-partitioning)
		- Configure internal RAMs - to allow program stacks to be stored, to allow non-secure accesses to it if the NPU inference needs it for example
		- Configure "NPU RAMs" - to allow NPU (non-secure) to access it.
		- Configure external flash - with a secure part, for executing the secure firmware, and a non-secure part to execute the non-secure firmware + store information for the NPU inference
		- (Configure GPIOs RIFSC to allow the non-secure firmware to toggle LEDs)
	- Activate the IAC IRQ to handle Illegal Accesses correctly (and be able to determine what access caused a fault)
	- Prepare for jumping to the Non-Secure firmware
	- Jump to Non-Secure firmware
- The Non-Secure App main tasks are:
	- Forever:
		- Change the current LED status
		- Perform an inference on the NPU

## Memory partitioning

### MPU
Only for demonstration purposes: all the external flash range is set to Read-Only, and execution is allowed.

### SAU
The IDAU of the stm32n6 can be found in the reference manual: all addresses >= 0x6000'0000 are Non-Secure, otherwise addresses with even MSByte are Non-Secure, addresses with odd MSByte are secure.

The SAU is configured to "promote" some of the IDAU-non-secure zones as secure. Once activated, the SAU will automatically mark all memory as "SECURE", 
as such, it is needed to declare all the ranges that should be non-secure, including the ones from the IDAU.

The SAU configuration is in the "partition_stm32n657xx.h" of the secure project, and is done in the "SystemInit" code of the secure app (TZ_SAU_Setup).
- Region 1: 0x2000'0000 - 0x2FFF'FFFF : Non-secure (SRAM)
- Region 2: 0x4000'0000 - 0x4FFF'FFFF : Non-secure (Peripherals)
- Region 3: 0x7018'0000 - 0x7FFF'FFFF : Non-secure (part of the external flash)

The Region 0 is also configured and its extent is defined at link-time: this section contains veneers for non-secure callables and must be placed in an NSC region.

All other memory addresses are then considered as secure.

### RISAF
RISAF allow further refined control over accesses to any memory address.

The RISAF are configured as follows:
| RISAF                    |   Configuration                   |  Usage                                                                   |
|--------------------------|-----------------------------------|--------------------------------------------------------------------------|
| RISAF 2 (AXISRAM1)       | SEC/NSEC                          | S.App uses it for storing its stack / Not used by NS, but could be       |
| RISAF 3 (AXISRAM2)       | SEC/NSEC                          | NS.App uses it for storing its stack / Not used by S, but could be       |
| RISAF 4 (NPUMaster1)     | NSEC                              | NS.App controls the NPU                                                  |
| RISAF 5 (NPUMaster2)     | NSEC                              | NS.App controls the NPU                                                  |
| RISAF 6 (NPURAMs)        | NSEC                              | NS.App uses it for storing inference activations                         |
| RISAF 7 (FlexRAM)        | SEC/NSEC                          | Not used by S, but could be / Not used by NS, but could be               |
| RISAF 12 (XSPI2/extflsh) | SEC @ 0x7010'0000 - 0x7017'FFFF   | Secure app code                                                          |
| RISAF 12 (XSPI2/extflsh) | NSEC @ 0x7018'0000 - 0x7FFF'FFFF  | Non-Secure app code  + possible weights used by the inference            |

# How to use it ?

In order to make the program work, you must do the following :

 - Set the boot mode in development mode (BOOT1 switch position is 1-3, BOOT0 switch position doesn't matter)
 - Open your preferred toolchain
 - Compile the projects in the following order, each compilation will yield both a .elf file and a .bin file. *The order here is important, because the "non-secure" project relies on the "secure" project symbols (for the NSC part)*
    - FSBL Project
    - Secure app project
    - Non-Secure app project
 - Resort to CubeProgrammer to add a header to the generated App_Secure binary Project.bin with the following command
   - *STM32MP_SigningTool_CLI.exe -bin Project.bin -nk -of 0x80000000 -t fsbl -o Project-trusted.bin -hv 2.1 -dump Project-trusted.bin*
       - The resulting binary is Project-trusted.bin.
 - Do the same with App_NonSecure
    - *STM32MP_SigningTool_CLI.exe -bin Project_ns.bin -nk -of 0x80000000 -t fsbl -o Project_ns-trusted.bin -hv 2.1 -dump Project_ns-trusted.bin*
       - The resulting binary is Project_ns-trusted.bin.
 - Next, in resorting again to CubeProgrammer, load the secure application binary and its header (Project-trusted.bin) in DK board external Flash at address 0x7010'0000 and the non-secure application binary and its header (Project_ns-trusted.bin) at address 0x7018'0000.

 To run the FSBL with boot configuration of the N6 in "DEV" mode,
 - Load the FSBL binary in internal RAM using the IDE
 - Run the example

## Scripts

Scripts have been written to automate those steps:
 - Build projects FSBL / Secure / Non-Secure using the IDE
 - `load_flash.sh` automates the signing/loading process in flash (some variables shall be set to match the running computer config)
 - `debug.sh` can then be used to start debug with GDB  (some variables shall be set to match the running computer config)

## Extra possibility: boot from flash
To run the template in boot from flash mode,
 - Resort to CubeProgrammer to add a header to the generated binary FSBL.bin with the following command
   - *STM32MP_SigningTool_CLI.exe -bin FSBL.bin -nk -of 0x80000000 -t fsbl -o FSBL-trusted.bin -hv 2.1 -dump FSBL-trusted.bin*
       - The resulting binary is FSBL-trusted.bin.
 - With CubeProgrammer, load the FSBL binary and its header (FSBL-trusted.bin) in DK board external Flash at address 0x7000'0000.
 - Set the boot mode in boot from external Flash (BOOT0 switch position is 1-2 and BOOT1 switch position is 1-2).
 - Press the reset button. The code then executes in boot from Flash mode.

## Recommendations
- When doing "execute in place", as in this example, it is safer to use cut2.0+ chips.