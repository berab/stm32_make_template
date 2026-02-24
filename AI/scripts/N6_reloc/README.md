----
title: Package for runtime loadable model support (ST Neural-ART NPU)
----


package version: 1.0


# Overview

This package contains scripts to generate a runtime loadable model (also called a relocatable model)
for an AI runtime environment based on the ST Neural-ART NPU
(see *"ST Neural-ART NPU - Runtime loadable model support"* article for more details).


## Requirements

+ STEdgeAI core tools (including the ST Neural ART module). Set the system environment
  variable `STEDGEAI_CORE_DIR` to indicate the root location of installation folder.

	$ export STEDGEAI_CORE_DIR=/c/ST/STEdgeAI/2.1/

+ Python 3.9+  
+ Make utility and GCC-based Embedded Arm toolchain (supporting the Cortex-m55)  
+ Requested Python modules

    pyelftools==0.27
    colorama==0.4.6
    tabulate==0.9.0


## Limitations

+ Only the STM32N6-based target are supported. 
+ Addresses of the internal mememory pools are fixed/absolutes.   


# Quick HowTo to generate a runtime loadable model  

## Generate/compile the model

The standard e2e flow is used to generate the network.c file and associated memory initializers from a
TFLite or ONNX quantized model file. To create a relocatable model, only the following specific configurations are required.:

+ Memory pool descriptor file
  + `"mode":   "USEMODE_RELATIVE“` for external memory pools only (flash and ram)
  + `"fformat": "FORMAT_RAW“` for all memory initializers

+ NPU compiler:
  + `--all-buffers-info`. To generate the info describing the buffers used by the different epoch. They are used
    by the `prepare_network.py` script to compute the used size of the different memory pools.

```batch
$ stedgai generate -m <model_path> --target stm32n6\
    --st-neural-art <profile>@<conf_file>.json <optional-options>
```

Note that for the non-secure execution context, the internal memory pools should be aligned with the non-secure addresses.


## Generate a runtime loadable model (binary file)

The `npu_driver.py` is the entry point for executing the steps required to generate
the loadable model. The `--input/-i` is used to specify the location of the generated `network.c`
and associated memory initializers (`*.raw files`). The default value is `st_ai_output`.
The `--output\-o` option is used to specify the output folder (default: `./build`).

```bash
$ python $STEDGEAI_CORE_DIR/scripts/N6_reloc/npu_driver.py -i st_ai_output/network.c -o build

...
   XIP size      = 28,472    (0x6f38) data+got+bss sections
   COPY size     = 169,488   (0x29610) +ro sections
   PARAMS offset = 172,032   (0x2a000)
   PARAMS size   = 1,793,272 (0x1b5cf8)

   ┌────────────────────────┬────────────────────────────────┬────────┬──────────┬─────────┐
   │ name (addr)            │ flags                          │ foff   │ dst      │ size    │
   ├────────────────────────┼────────────────────────────────┼────────┼──────────┼─────────┤
   │ xSPI2 (2000a3bf)       │ 01010500 RELOC.PARAM.0.RCACHED │ 0      │ 00000000 │ 1793265 │
   │ AXISRAM5 (2000a3c5)    │ 03020200 RESET.ACTIV.WRITE     │ 0      │ 342e0000 │ 352800  │
   │ <undefined> (00000000) │ 00000000 UNUSED                │ 0      │ 00000000 │ 0       │
   └────────────────────────┴────────────────────────────────┴────────┴──────────┴─────────┘
    Table: mempool c-descriptors (off=400055b4, 3 entries, from RAM)

   Generating files...
    creating "build\network_rel.bin" (size=1,965,304)
```

The following options can be specified:

+ `--no-secure`: to indicate that the generated runtime loadable model is executed in non-secure context.  
+ `--split`: to indicate that the params\weights should be generated in a separeted binary file. 
+ `--pack-dir`: in the case where the `STEDGEAI_CORE_DIR` is not defined, this option can be use to
  specificy the root location of the stedgeai core installation folder. 


```bash
$ python scripts/npu_driver.py --help
usage: npu_driver.py [-h] [--input STR] [--output STR] [--name STR] [--no-secure] [--split]
                     [--pack-dir STR] [--gen-c-file] [--parse-only] [--no-clean] [--log [STR]]
                     [--verbosity [{0,1,2}]] [--debug] [--no-color]

NPU Utility - Relocatable model generator v1.0

optional arguments:
  -h, --help            show this help message and exit
  --input STR, -i STR   location of the generated c-files (or network.c file path)
  --output STR, -o STR  output directory
  --name STR, -n STR    basename of the generated c-files (default=network)
  --no-secure           generate binary model for secure context
  --split               generate a separate binary file for the params/weights
  --pack-dir STR        installation directory of the STEdgeAI Core (ex. ~/ST/STEdgeAI/2.1)
  --gen-c-file          generate c-file image (DEBUG PURPOSE)
  --parse-only          parsing only the generated c-files
  --no-clean            Don't clean the intermediate files
  --log [STR]           log file
  --verbosity [{0,1,2}], -v [{0,1,2}]
                        set verbosity level
  --debug               Enable internal log (DEBUG PURPOSE)
  --no-color            Disable log color support
```

## Deploy and use the generated runtime loadable model

STM32N6-DK development environment can be used to deploy a relocatable model.
	- https://www.st.com/en/evaluation-tools/stm32n6570-dk.html
	
The STM32CubeIDE tools is required.
	- https://www.st.com/en/development-tools/stm32cubeide.html

Set the `STM32_CUBE_IDE_DIR` environment variable to indicate the installation
directory: `<INST_TOOLS>/STM32CubeIDE_1.18.0/STM32CubeIDE` else the
`--cube-ide-dir` option can be used.


```bash
$ python $STEDGEAI_CORE_DIR/scripts/N6_reloc/st_load_and_run.py -i build/network_rel.bin
NPU Utility - ST Load and run (dev environment) (version 1.0)
Creating date : Thu Apr 10 22:51:49 2025

Entry point    : 'build\network_rel.bin'
Board          : 'stm32n6570-dk'
no splitted model

Resetting the board.
Flashing 'build\network_rel.bin' at address 0x71000000 (size=1965304)..
Loading & start the validation application 'stm32n6570-dk-validation-reloc-copy'..
Deployed model is started and ready to be used.
Executing the deployed model (desc=serial:921600)..
...
  ----------------------------------------------------------------------------------
  total                 12.963                   [ 1,997,228  7,881,453    491,939 ]
                   77.14 inf/s                   [     19.3%      76.0%       4.7% ]
  ----------------------------------------------------------------------------------
...
```

Note that if the `--split` option is used, the script expects to find the `build/network_rel_params.bin`
to flash also the weights/params.


```
$ python $STEDGEAI_CORE_DIR/scripts/N6_reloc/st_load_and_run.py --help
usage: st_load_and_run.py [-h] [--input STR] [--board STR] [--address STR] [--mode STR]
                          [--cube-ide-dir STR] [--log [STR]] [--verbosity [{0,1,2}]] [--debug]
                          [--no-color]

NPU Utility - ST Load and run (dev environment) v1.0

optional arguments:
  -h, --help            show this help message and exit
  --input STR, -i STR   location of the generated c-files or network.c (default: build/network_rel.bin)
  --board STR           ST development board (default: stm32n6570-dk)
  --address STR         destination address - net(,params) (default: 0x71000000,0x71800000)
  --mode STR            extra option to select the variants: copy,xip[no-flash,no-run,max-speed]
  --cube-ide-dir STR    installation directory of STM32CubeIDE tools (ex. ~/ST/STM32CubeIDE_1.18.0/STM32CubeIDE)
  --log [STR]           log file
  --verbosity [{0,1,2}], -v [{0,1,2}]
                        set verbosity level
  --debug               Enable internal log (DEBUG PURPOSE)
  --no-color            Disable log color support
```
