#
# Makefile additions for relocatable mode
#
C_DEFS += -DLL_ATON_RT_RELOC
C_DEFS += -DUSE_RELOC_MODE=1
C_DEFS += -DUSE_RELOC_XIP_MODE=0
C_DEFS += -DUSE_RELOC_EXT_EXEC_RAM=0

ATON_SOURCES += $(ATON_RT_PATH)/ll_aton_reloc_network.c
