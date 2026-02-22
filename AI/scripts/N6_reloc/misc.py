###################################################################################
#   Copyright (c) 2025 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Misc functions
"""

import logging
from pathlib import Path
from typing import List, Union, Optional
from dataclasses import dataclass


from exceptions import ToolsError
from logging_utilities import get_logger


def size_int_to_str(size: int, kb_only: bool = False) -> str:
    """Convert int to str"""
    if kb_only:
        return f'{size / 1024:.2f} KB'
    if 0 <= size < 1024:
        return f'{size} B'
    if 1024 <= size < 1024 * 1024:
        return f'{size / 1024:,.2f} KB'
    if size >= 1024 * 1024:
        return f'{size / (1024 * 1024):,.2f} MB'
    return f'invalid size {size}'


def align_up(value: int, align: int = 32) -> int:
    """Align value up to specified bytes"""
    return (value + (align - 1)) & ~(align - 1)


@dataclass
class Params:
    """Main object to handle the parameters"""
    input: Union[Path, str, List[Path]] = Path('')
    output: Union[Path, str] = Path('build')
    name: str = 'network'
    target: str = 'stm32n6'
    no_secure: bool = False
    no_dbg_info: bool = False
    ecblob_in_params: bool = False
    split: Optional[bool] = None
    secure: bool = True
    address: str = '0x71000000,0x71800000'
    board: str = 'stm32n6570-dk'
    mode: str = ''
    parse_only: bool = False
    cont: bool = False
    llvm: bool = False
    st_clang: bool = False
    compatible_mode: bool = False
    log: Optional[str] = 'no-log'
    json: Optional[str] = 'no-json'
    report: Optional[str] = 'no-report'
    verbosity: int = 0
    debug: bool = False
    no_color: bool = False
    color: bool = True
    no_clean: bool = False
    clean: bool = True
    gen_c_file: bool = False
    pack_dir: Union[Path, str] = ''
    cube_ide_dir: Union[Path, str] = ''
    cross_compile: Union[Path, str] = ''
    dev_mode: Optional[str] = 'no-file'
    custom: Optional[str] = 'no-file'

    def __init__(self, args):
        """Constructor"""
        self.from_args(args)

    def from_args(self, args):
        """Import arguments from args object"""

        if hasattr(args, 'input'):
            if isinstance(args.input, list):
                self.input = [Path(i) for i in args.input]
            else:
                self.input = Path(args.input)
        else:
            raise ToolsError('\'input\' argument is mandatory')

        if hasattr(args, 'pack_dir'):
            self.pack_dir = args.pack_dir

        if hasattr(args, 'cube_ide_dir'):
            self.cube_ide_dir = args.cube_ide_dir

        if hasattr(args, 'cross_compile'):
            self.cross_compile = args.cross_compile

        if hasattr(args, 'output'):
            self.output = Path(args.output)
        else:
            self.output = Path('build')

        if hasattr(args, 'target'):
            self.target = args.target

        if hasattr(args, 'llvm'):
            self.llvm = args.llvm

        if hasattr(args, 'st_clang'):
            self.st_clang = args.st_clang

        if hasattr(args, 'compatible_mode'):
            self.compatible_mode = args.compatible_mode

        if hasattr(args, 'custom'):
            self.custom = args.custom

        if hasattr(args, 'report'):
            self.report = args.report

        if hasattr(args, 'mode'):
            self.mode = args.mode

        if hasattr(args, 'board'):
            self.board = args.board

        if hasattr(args, 'address'):
            self.address = args.address

        if hasattr(args, 'name'):
            self.name = args.name
        else:
            self.name = 'network'

        if hasattr(args, 'no_secure'):
            self.no_secure = args.no_secure
            self.secure = not self.no_secure
        else:
            self.no_secure = False
            self.secure = True

        if hasattr(args, 'no_dbg_info'):
            self.no_dbg_info = args.no_dbg_info

        if hasattr(args, 'ecblob_in_params'):
            self.ecblob_in_params = args.ecblob_in_params

        if hasattr(args, 'split'):
            self.split = args.split
        else:
            self.split = None

        if hasattr(args, 'no_clean'):
            self.no_clean = args.no_clean
            self.clean = not self.no_clean
        else:
            self.no_clean = False
            self.clean = True

        if hasattr(args, 'parse_only'):
            self.parse_only = args.parse_only

        if hasattr(args, 'gen_c_file'):
            self.gen_c_file = args.gen_c_file

        if hasattr(args, 'cont'):
            self.cont = args.cont

        if hasattr(args, 'log'):
            self.log = args.log

        if hasattr(args, 'json'):
            self.json = args.json

        if hasattr(args, 'verbosity'):
            self.verbosity = args.verbosity

        if hasattr(args, 'debug'):
            self.debug = args.debug

        if hasattr(args, 'no_color'):
            self.no_color = args.no_color
            self.color = not self.no_color
        else:
            self.no_color = False
            self.color = True

        if hasattr(args, 'dev_mode'):
            self.dev_mode = args.dev_mode


def create_logger(params: Params, default_log: Union[Path, str] = '') -> logging.Logger:
    """Create logger"""

    lvl = logging.WARNING
    if params.verbosity > 0:
        lvl = logging.INFO
    if params.debug:
        lvl = logging.DEBUG

    if params.log is None:
        if default_log:
            params.log = str(default_log) + '.log'
        else:
            params.log = Path(__file__).stem + '.log'
    elif isinstance(params.log, str) and params.log == 'no-log':
        params.log = None

    return get_logger(level=lvl, color=not params.no_color,
                      filename=params.log)
