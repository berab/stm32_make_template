###################################################################################
#   Copyright (c) 2024 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Utility functions - post-process elf file for relocatable model
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

#
# History
#
#   v0.0 - initial version
#   v0.1 - clean/reworked code
#   v1.0 - add support for clang/llvm
#

__title__ = 'NPU Utility - Post-process script to generate the binary files for relocatable mode'
__version__ = '1.0'
__author__ = 'STMicroelectronics'


from exceptions import BaseExceptionError
from binary_mgr import ElfPostProcess, RelocBinaryImage
from misc import Params, create_logger


_DEFAULT_INPUT = 'build/network.elf'
_DEFAULT_OUTPUT_NAME = 'network'
_DEFAULT_BUILD_DIR = 'build'


def post_process_elf(params: Params,  results: Optional[Dict[str, Any]] = None,
                     no_banner: bool = False):
    """Post-Process the elf file"""

    logger = logging.getLogger()

    c_name = params.name
    elf_file_path = Path(params.input)

    clang_mode = bool(params.st_clang) or bool(params.llvm)

    if not no_banner:
        logger.info('%s (version %s)', __title__, __version__)
        logger.info('Creating date : %s', datetime.now().ctime())
        logger.info('')

    logger.info('Entry point   : \'%s\' (name=\'%s\')', elf_file_path, params.name)
    logger.info('output        : \'%s\'', params.output)

    if os.path.isdir(elf_file_path):
        elf_file_path = Path(elf_file_path) / f'{c_name}.elf'
        logger.info('used elf-file : \'%s\'', elf_file_path)

    # if os.path.isdir(params.output):
    #    params.output = params.output / 'network_rel.bin'


    raw_params_path: Union[Path, str] = elf_file_path.parents[0]
    raw_params_path = Path(raw_params_path) / f'{c_name}_reloc_mempools.raw'
    if not raw_params_path.is_file():
        raw_params_path = ''

    epp_ = ElfPostProcess(elf_file_path,
                          paramspath=raw_params_path,
                          clang_mode=clang_mode,
                          logger=logger)

    if params.verbosity > 1:
        epp_.summary(full=True)

    logger.info('')
    logger.info('Building the binary image (with \"%s\" file, split=%s)...',
                raw_params_path, bool(params.split))
    epp_.build(bool(params.split))

    logger.info('')
    logger.info('Saving the binary file...')
    bin_files_ = epp_.save(params.output)

    c_files_ = []
    if params.gen_c_file:
        c_files_ = epp_.to_c(params.output)

    logger.info('')
    logger.info('Loading and checking the binary file...')
    reloc_bin_ = RelocBinaryImage(bin_files_[0], logger=logger)
    reloc_bin_.check()
    logger.info('')
    reloc_bin_.summary(logger.info)

    if results is not None:
        res_ = reloc_bin_.to_dict()
        res_['gen_files'] = [{'size': os.stat(f).st_size, 'path': str(Path(f).absolute())} for f in bin_files_]
        if bool(params.split):
            res_['params_size'] = os.stat(bin_files_[-1]).st_size
        for c_file in c_files_:
            res_['gen_files'].append({'size': os.stat(c_file).st_size,
                                     'path': str(Path(c_file).absolute())})
        results['versions'].update({ 'post-process': __version__})
        results['reloc_binary_image'] = res_

    epp_.log_ec_blobs()

    logger.info('')
    logger.info('Generating files...')
    for file_ in bin_files_:
        file_stats = os.stat(file_)
        size = file_stats.st_size
        logger.info(' creating \"%s\" (size=%s)', file_, f'{size:,}')
    for file_ in c_files_:
        logger.info(' \"%s\"', file_)


def main():
    """Main function to parse the arguments"""  # noqa: DAR101,DAR201,DAR401

    parser = argparse.ArgumentParser(description=f'{__title__} v{__version__}')

    parser.add_argument('--input','-i', metavar='STR', type=str, help='elf file',
                        default=_DEFAULT_INPUT)

    parser.add_argument('--output', '-o', metavar='STR', type=str,
                        help='output directory',
                        default=_DEFAULT_BUILD_DIR)

    parser.add_argument('--name', '-n', metavar='STR', type=str,
                        help='basename of the generated c-files',
                        default=_DEFAULT_OUTPUT_NAME)

    parser.add_argument('--clang', action='store_const', const=1,
                        help='use CLANG compiler and libraries')

    parser.add_argument('--gen-c-file', action='store_const', const=1,
                        help='Generate c-file image (DEBUG PURPOSE)')

    parser.add_argument('--log', metavar='STR', type=str, nargs='?',
                        default='no-log',
                        help='log file')

    parser.add_argument('--verbosity', '-v',
                        nargs='?', const=1, type=int, choices=range(0, 3),
                        default=1, help="set verbosity level")

    parser.add_argument('--debug', action='store_const', const=1,
                        help='Enable internal log (DEBUG PURPOSE)')

    parser.add_argument('--no-color', action='store_const', const=1,
                        help='Disable log color support')

    params: Params = Params(parser.parse_args())

    logger = create_logger(params, Path(__file__).stem)

    try:
        post_process_elf(params)
    except BaseExceptionError as e:
        logger.exception(e, stack_info=False, exc_info=params.debug)
        return -1

    return 0


if __name__ == '__main__':
    sys.exit(main())
