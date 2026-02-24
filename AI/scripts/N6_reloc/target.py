###################################################################################
#   Copyright (c) 2025 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Utility functions to describe the STM32 target
"""

import os
from pathlib import Path
from typing import Tuple, List
from dataclasses import dataclass


from exceptions import ToolsError, FirmwareFileNotFoundError


_SUPPORTED_LL_ATON_RT_VERSION = (1, 1, 3)  # see ll_aton_version.h file


class DevicePropertyDesc():
    """Target descriptor"""

    def __init__(self, target: str = 'stm32n6'):
        """Constructor"""

        if target != 'stm32n6':
            raise ToolsError('Only the \'stm32n6\' target is supported')

        self._target: str = target

    @property
    def ext_base_address(self) -> int:
        """Return the base @ of the external memory"""
        return 0x60000000

    @property
    def mcu_core_type(self) -> str:
        """Return MCU core type"""
        return 'cortex-m55'

    @property
    def name(self) -> str:
        """Return name of the target"""
        return self._target

    @property
    def family(self) -> str:
        """Return family of the target"""
        return 'STM32N6xx'

    @property
    def core_lib_selector(self) -> str:
        """Return core library selector of the target"""
        return 'ARMCortexM55'


@dataclass
class ExternalFlashPropertyDesc():
    """External flash descriptor"""
    loader_name: str = 'MX66UW1G45G_STM32N6570-DK.stldr'
    page_size: int = 4 * 1024
    sector_size: int = 64 * 1024
    header_addr: int = 0x70FFF000  # fixed address for the eflash loader header
    base_addr: int = 0x71000000  # base address of the external flash
    params_addr: int = 0x71800000


@dataclass
class RamPropertyDesc():
    """Available RAM descriptor"""
    exec_int: int = (512 + 128) * 1024  # maxsize of internal RAM for execution
    exec_ext: int = 4 * 1024 * 1024  # maxsize of external RAM for execution
    acts_ext: int = 27 * 1024 * 1024   # maxsize of external RAM for data storage


class BoardPropertyDesc():
    """Board descriptor"""

    def __init__(self, board: str = 'stm32n6570-dk'):
        """Constructor"""

        if board != 'stm32n6570-dk':
            raise ToolsError('Only the \'stm32n6570-dk\' board is supported')

        self._board: str = board
        self._device: DevicePropertyDesc = DevicePropertyDesc('stm32n6')

    @property
    def name(self) -> str:
        """Return name of the board"""
        return self._board

    @property
    def device(self) -> DevicePropertyDesc:
        """Return device descriptor"""
        return self._device

    @property
    def ext_flash(self) -> ExternalFlashPropertyDesc:
        """Return external flash descriptor"""
        return ExternalFlashPropertyDesc()

    @property
    def ram(self) -> RamPropertyDesc:
        """Return RAM available descriptor"""
        return RamPropertyDesc()

    @property
    def baudrate(self) -> str:
        """Return baudrate of the board"""
        return '921600'

    @property
    def ll_aton_rt_version(self) -> List[Tuple[int, int, int]]:
        """Return list of supported ll_aton runtime version"""
        return [_SUPPORTED_LL_ATON_RT_VERSION]

    @property
    def max_model_size(self) -> int:
        """Return the maximum number of models supported on the target"""
        return 4

    def firmware_name(self, mode: str = 'copy') -> Tuple[Path, ExternalFlashPropertyDesc]:
        """."""
        current_ = Path(os.path.dirname(os.path.realpath(__file__))) / 'test'
        if 'usbc' in mode:
            if 'llvm' in mode:
                f_name = f'{self.name}-validation-reloc-usbc-llvm.elf'
            else:
                f_name = f'{self.name}-validation-reloc-usbc.elf'
        else:
            if 'llvm' in mode:
                f_name = f'{self.name}-validation-reloc-llvm.elf'
            else:
                f_name = f'{self.name}-validation-reloc.elf'
        app_ = current_ / f_name

        if not app_.is_file():
            msg_ = f'The \'{app_}\' is not available'
            raise FirmwareFileNotFoundError(msg_)

        return app_, self.ext_flash

    def __str__(self) -> str:
        """String representation"""
        eflash_ = self.ext_flash
        ram_ = self.ram
        addrs_ = (f'0x{eflash_.header_addr:08X},'
                  f'0x{eflash_.base_addr:08X},'
                  f'0x{eflash_.params_addr:08X}')
        return (f'\'{self.name}\' baudrate={self.baudrate} '
                f'eflash_loader=\'{eflash_.loader_name}\' '
                f'eflash[sec/pg]={eflash_.sector_size/1024}KB/{eflash_.page_size/1024}KB '
                f'exec_ram[int/ext]={ram_.exec_int:,d}/{ram_.exec_ext:,d} '
                f'ext_ram={ram_.acts_ext:,d} '
                f'addrs={addrs_}')
