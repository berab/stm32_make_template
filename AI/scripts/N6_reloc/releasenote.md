----
title: Release note
----

Current version: 1.3


# 1.3

**Top of ST Edge AI Core - Release v2.2.0**  


## Bug Fixes

[X] fix: Support for using `st_ai_output` as the build folder.


## New features

[X] LLVM/Clang: keep the default enum size by default. `--compatible-mode` option can be used to force `-fshort-enums` definition.
    Note that the makefile to generate the network-runtime lib has also been updated to keep the default enum size.
[X] Support for setting the network C name (`--name` option).
[X] Alignment with ST Edge AI Core 2.2 release.  
[X] Removed limitation for absolute addresses in external memory pools (RAM).  
[X] Added test firmwares with USB-C support. 
[X] XIP-mode optimization: Merge epoch blob (const data) with weights/param buffer (`--ecblob-in-params`).
[X] Update the documentation  


## TODO

[ ] Limit default log verbosity. 
[ ] Improve memory alignment constraints for MCU D$ line size (8B → 32B).


# 1.2

New patched version (Top of ST Edge AI Core - Release v2.1.0) after feedback.
The previous `--clang` option has been replaced by `--st-clang` to support the ST-CLANG tool-chain.
`--llvm` is now used for the LLVM-CLANG toolchain.


## Bug fixes

[x] Fix crash when two models are re-installed/used sequentially in COPY mode:
    -> added Invalidate ICache range operation on the exec_ram memory region after installation.
[X] Correct ST Edge AI path on Mac ARM  
[X] Remove compilation warnings in ll_aton_reloc_xx files with LLVM-CLANG 
[X] Linker script: Removed READONLY attribute in clang/st-clang build files. 
[X] Runtime libraries: Completed/fixed requested libc functions, including memcpy, and added new LLVM-CLANG tools target.
[X] Handle spaces in path names.  


## New features

[X] Create specific st-clang build files  
[X] Add option for custom build (remove hard-coded path): See [customization options](#custom-build), and [llvm quickstart](#quickstart-for-llvm).
[X] Add option to not compile with LL_ATON_EB_DBG_INFO c-define (`--no-dbg-option`)


## TODO

[ ] Add support to allow absolute address for memory-pools located in external memory (RAM).  
[ ] XIP-mode optimization - exec-size: Merge epoch blob (const data) with weights/param buffer. 
[ ] Add support of different network c-name (currently only default name 'network' is supported).
[ ] Fix to support a simple output/build directory. 
[ ] Limit default log verbosity. 
[ ] Improve memory alignment constraints for MCU D$ line size (8B → 32B).
[ ] Update the documentation. 


# 1.1

Add initial st-clang support (Top of ST Edge AI Core - Release v2.1.0)


# 1.0

Initial version (ST Edge AI Core - Release v2.1.0)


# Comments

## `--ecblob-in-params` option

Since 1.3

The `--ecblob-in-params` option indicates that the ecblobs (const part) are placed in the
params/weights memory section. This feature allows to reduce the requested exec memory region
to execute the model in COPY mode. The ecblobs are fetched from the external flash if not copied
in exec ram for update. Ecblobs are placed in the beginning of the params/weights memory section.
The `--split` option is always supported, the params file includes the ecblobs.


## `--name/-n` option

Since 1.3

The `--name/-n` option can be used to specify/overwrite the expected c-name/file-name of the loadable runtime model.
By default, the name of the generated network files is used.

Default behavior.

```
$ python npu_driver.py -i <gen-dir>/network.c 
...
Generating files...
    creating "build\network_rel.bin" (size=..)

$ python npu_driver.py -i <gen-dir>/my_model.c
...
Generating files...
    creating "build\network_rel.bin" (size=..)
```

```
$ python npu_driver.py -i <gen-dir>/network.c -n toto
...
Generating files...
    creating "build\toto_rel.bin" (size=..)
```


## llvm target

Since 1.2

+ The `-fshort-enums` option is used to ensure interoperability between user IAR/GCC/ST-CLANG-based application
  and the relocatable model generated with LLVM-CLANG. This means that if the user application is compiled
  with the LLVM-CLANG tool-chain, the `-fshort-enums` option should be also used. An additional runtime
  check (`ll_aton_reloc_install` function) has been added to compare the size of the main C structures.

Since 1.3

+ for `--llvm` target, the `-fshort-enums` option is no more enabled by default. The `--compatible-mode` option should be used
  to enable this compilation option.


## Custom build

Since 1.2

+ It is possible to specify some extra options / information for the script through a "custom build" configuration file.
+ The configuration file is a regular JSON file, with a given set of available configurations listed below:
  + `runtime_network_lib`: can be used to specify the path to the network runtime lib (overriding the default path in the stedgeai installation)
  + `stedgeai_install_path`: can be used to specify the path to the stedgeai installation (overrides the environment variable if it exists)
  + Only available when using `--llvm` (this affects variables used in the `makefile_llvm`):
    + `llvm_install_path`: provides the script with the installation directory of the LLVM compiler to use (this path should be the root of the install, *NOT* the bin/ directory !)
    + `target_triplet`: can be used to override the target triplet (otherwise defaults to thumbv8m.main-unknown-none-eabihf)
    + `llvm_sysroot`: can be used to override the sysroot used by the compiler (otherwise defaults to <install_path>/lib/clang-runtimes/newlib/arm-none-eabi/armv8m.main_hard_fp)
+ The default name for the file (used when using `--custom`) is `custom.json`.
+ The filename can also be specified by passing the `--custom <filename>` option.

## `--no-dbg-option` option

Since 1.2

This option can be used to compile the relocatable model without the `LL_ATON_EB_DBG_INFO` c-define.
Note that if this option is used, the application should also compiled w/o the `LL_ATON_EB_DBG_INFO` c-define.


## Add-ons and fixes for the article "ST Neural-ART NPU - Runtime loadable model support" 

Since 1.2

+ It is recommended to align the provided `exec_ram/ext_ram` addresses and size to 32 Bytes.

+ In the provided snippet code, there is an error in the provided example, the `config.ext_param_addr` parameter
  should be set to `NULL` or `0` if the model is not split; otherwise, it should be set to the address of the
  flashed params/weights buffer.

```c
/* Create and install an instance of the relocatable model */
  ll_aton_reloc_config config;
  config.exec_ram_addr = exec_ram_addr;
  config.exec_ram_size = rt.rt_ram_copy;
  config.ext_ram_addr = ext_ram_addr;
  config.ext_ram_size = rt.ext_ram_sz;
  config.ext_param_addr = NULL;         // !!!! 
  config.mode = AI_RELOC_RT_LOAD_MODE_COPY; // | AI_RELOC_RT_LOAD_MODE_CLEAR;

  res = ll_aton_reloc_install(file_ptr, &config, &nn_instance);
```

## Quickstart for llvm

Since 1.2

To use a llvm compiler, the following minimal steps are advised:

- Create a `custom.json` file (if needed, customize even more by using the supported keywords presented [above](#custom-build))
```
{
    "llvm_install_path": "/Applications/my_compiler"
}
```
- Call the `npu_driver.py` script with `--llvm`, and `--custom` to use the customization-json-file:
```
python npu_driver.py -i network.c -o output_reloc/ --llvm --custom
```