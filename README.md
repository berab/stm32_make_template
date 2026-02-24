# STM32N6 Makefile template for Edge AI 

## Clone the repository with all submodules:
```bash
git submodule update --recursive
```

## Requirements:
- a STM32N6 board that is on development boot mode: BOOT0 (JP1), BOOT1 (JP2): 1 (or smt like this, check the manual xd)
- STM Cube IDE (for STLink gdb server)
- STLINK v3 (update via the IDE)
- Arm GNU Toolchain 15.2.1
- STEdgeAI (and change GCC_Path in NPU_Validation/armgcc/Makefile)
- ONNX 6

## RUN
To run on NPU:
```bash
make clean all PROC=NPU
```

or on CM55:
```bash
make clean all PROC=CM55
```

### Contact:
beran.kilic@gmail.com