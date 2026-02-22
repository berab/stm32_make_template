# STM32N6 Makefile template for Edge AI 

## Clone the repository with all submodules:
```bash
git submodule pull  --recursive
```

## Requirements:
- a STM32N6 board that is on development boot mode: BOOT0 (JP1), BOOT1 (JP2): 1 (or smt like this, check the manual xd)
- STM Cube IDE (for STLink gdb server)
- STLINK v3 (update via the IDE)
- Arm GNU Toolchain 15.2.1
- STEdgeAI (and change GCC_Path in NPU_Validation/armgcc/Makefile)
- ONNX 6

## RUN
### NPU model generation and validation
```bash
stedgeai generate -m mymodel.onnx --target stm32n6
python ./AI/scripts/N6_scripts/n6_loader.py

```

### CM55 model generation and validation
```bash
stedgeai generate -m mymodel.onnx --target stm32n6
stedgeai generate -m mymodel.onnx --target stm32n6 --binary --address 0x71000000
# stedgeai generate -m mymodel.onnx --target stm32n6 --memory-pool AI/Projects/STM32N6570-DK/Applications/CM55_Validation/mypool_N6.json --type onnx
```

### Contact:
beran.kilic@gmail.com

