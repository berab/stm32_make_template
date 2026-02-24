###################################################################################
#   Copyright (c) 2025 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Entry point to use the npu services
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
import time
from colorama import Fore, init
import json

from exceptions import BaseExceptionError, ExecutableNotFoundError
from exceptions import ExecutableExecError, RelocProcessError
from prepare_network import prepare_c_network_file
from relocatable_pp import post_process_elf
from misc import Params, create_logger
from tools import MakeUtility, STEdgeAICoreNpuResources, fix_path, escape_spaces


#
# History
#
#   v1.0 - initial version
#   v1.1 - add clang support
#   v1.2 - add custom/llvm cmd support
#          add st-clang building files
#   v1.3 - alignment with STEdgeAI Core 2.2
#          fix/complete name option
#          add option to place the const ecblob in param section
#   v1.4 - add results json file generation
#

__title__ = 'NPU Utility - Relocatable model generator'
__version__ = '1.4'
__author__ = 'STMicroelectronics'


_DEFAULT_INPUT = './st_ai_output'
_DEFAULT_BUILD_DIR = 'build'


def step(msg: str, logger: logging.Logger, params: Params, end=False) -> None:
    """."""
    typ_ = '<-' if end else '->'
    if params.color:
        init()  # work-around to avoid to lost the color (Windows-git-bash env)
        msg_ = f'{typ_} {Fore.GREEN}{msg}{Fore.RESET}'
    else:
        msg_ = f'{typ_} {msg}'

    logger.info('')
    logger.info(msg_)
    if not end:
        logger.info('')


def save_results(params: Params, results: dict) -> None:
    """Save results to a json file if requested."""
    if params.json == 'no-json':
        return
    if params.json is None or params.json == "":
        params.json = Path(params.output) / f'{params.name}_reloc_results.json'
    if params.json and params.json != 'no-json':
        with open(params.json, 'w', encoding='utf-8') as fp:
            json.dump(results, fp, indent=4)


def npu_driver(params: Params) -> int:
    """Main process"""

    logger = logging.getLogger()

    logger.info('%s (version %s)', __title__, __version__)
    logger.info('Creating date : %s', datetime.now().ctime())
    logger.info('')

    logger.debug(params)

    clang_mode = bool(params.st_clang) or bool(params.llvm)
    compatible_mode = bool(params.compatible_mode)

    logger.info('Input file         : %s', params.input)
    logger.info('Output/build dir   : %s', params.output)
    logger.info('clang mode         : %s', clang_mode)
    logger.info('compatible mode    : %s', compatible_mode)
    logger.info('custom             : %s', params.custom)

    rlib = STEdgeAICoreNpuResources(params)
    results = {
        'version': '1.0',  # version of this results file
        'created-date': datetime.now().ctime(),
        'versions': {'npu_driver': __version__}
        }

    logger.info('STEdge AI core     : %s (%s)', rlib.pack, rlib.stedgeai.version)

    if params.secure and clang_mode:
        logger.info('!SECURE mode is disabled, cmse is not compatible with ROPI/RWPI option')
        params.secure = False

    build_dir = Path(params.output)

    if not rlib.ll_aton.is_dir():
        msg_err_ = f'Unable to find the LL_ATON files in \'{rlib.ll_aton}\' directory.'
        raise RelocProcessError(msg_err_)

    if not params.parse_only:
        make = MakeUtility('make')
        if not make.is_valid():
            raise ExecutableNotFoundError('Make utility is requested.')
        logger.debug(make)

    # -----------------------------------------------------------
    # STEP 0
    # -----------------------------------------------------------

    step('[STEP.0] Preparing the generated c-files..', logger, params)

    start_time = time.perf_counter()
    try:
        prepare_c_network_file(params, results=results, no_banner=True)
    except BaseExceptionError as e:
        logger.exception(e, stack_info=False, exc_info=params.debug)
        return -1
    diff_time_0 = time.perf_counter() - start_time
    msg_ = f'done - Took {diff_time_0:.4f}s'
    step(msg_, logger, params, True)

    if params.parse_only:
        save_results(params, results)
        return 0

    # -----------------------------------------------------------
    # STEP 1
    # -----------------------------------------------------------

    step('[STEP.1] Building the intermediate executable..', logger, params)

    start_time = time.perf_counter()

    def log_parser(msg: str) -> None:
        """."""
        if params.verbosity > 1:
            logger.info(msg)

    build_dir_ = build_dir.resolve().as_posix()
    if params.clean:
        logger.info('Cleaning the generated intermediate files..')
        lines = make.run(['-f', rlib.makefile, 'clean', f'BUILD_DIR={build_dir_}'],
                         cwd=str(rlib.resources), parser=log_parser)
        if make.error:
            if params.verbosity < 2:
                for line in lines:
                    logger.error(line)
            raise ExecutableExecError()

    make_opts = ['-f']
    make_opts.append(rlib.makefile)
    if params.secure:
        make_opts.append('SECURE_MODE=y')
    if params.cross_compile:
        make_opts.append(f'CROSS_COMPILE="{escape_spaces(fix_path(str(params.cross_compile)))}"')
    if compatible_mode:
        make_opts.append('COMPATIBLE_MODE=y')
    make_opts.append(f'BUILD_DIR={escape_spaces(build_dir_)}')
    make_opts.append(f'TARGET={params.name}')

    make_opts.append(f'RESOURCES_DIR={escape_spaces(rlib.resources.as_posix())}')
    make_opts.append(f'RT_ATON_ROOT_DIR={escape_spaces(rlib.ll_aton.as_posix())}')
    make_opts.append(f'SW_LIB_PATH={escape_spaces(rlib.rt_lib_path.as_posix())}')
    make_opts.append(f'SW_LIB_INC_DIR={escape_spaces(rlib.rt_lib_inc.as_posix())}')
    make_opts.append(f'PLT_DIR={escape_spaces(rlib.platform.as_posix())}')

    make_opts.append(f'EB_DBG_INFO={"n" if params.no_dbg_info else "y"}')
    make_opts.append(f'ECBLOB_IN_PARAMS={"y" if params.ecblob_in_params else "n"}')

    # Add options specified in the json file:
    for opt in rlib.get_makefile_defines_from_custom():
        make_opts.append(opt)

    logger.info('Build..')
    logger.info(' CWD=%s', rlib.resources)
    for opt in make_opts:
        logger.info(' %s', opt)
    logger.info('')
    lines = make.run(make_opts, parser=log_parser, env=rlib.env, cwd=str(rlib.resources))
    if make.error:
        if params.verbosity < 2:
            for line in lines:
                logger.error(line)
        raise ExecutableExecError()

    diff_time_1 = time.perf_counter() - start_time
    msg_ = f'done - Took {diff_time_1:.4f}s'
    step(msg_, logger, params, True)

    # -----------------------------------------------------------
    # STEP 2
    # -----------------------------------------------------------

    step('[STEP.2] Creating the relocatable binary model..', logger, params)

    params.input = f'{params.output}'
    start_time = time.perf_counter()
    try:
        post_process_elf(params, results=results, no_banner=True)
    except BaseExceptionError as e:
        logger.exception(e, stack_info=False, exc_info=params.debug)
        save_results(params, results)
        return -1

    diff_time_2 = time.perf_counter() - start_time
    msg_ = f'done - Took {diff_time_2:.4f}s'
    step(msg_, logger, params, True)

    save_results(params, results)
    return 0


def main():
    """Script entry point."""

    parser = argparse.ArgumentParser(description=f'{__title__} v{__version__}')

    parser.add_argument('--input', '-i', metavar='STR', type=str,
                        help='location of the generated c-files (or network.c file path)',
                        default=_DEFAULT_INPUT)

    parser.add_argument('--output', '-o', metavar='STR', type=str,
                        help='output directory',
                        default=_DEFAULT_BUILD_DIR)

    parser.add_argument('--name', '-n', metavar='STR', type=str,
                        help='basename of the generated c-files (default=<network-file-name>)',
                        default='no-name')

    parser.add_argument('--no-secure', action='store_const', const=1,
                        help='generate binary model for non secure context')

    parser.add_argument('--no-dbg-info', action='store_const', const=1,
                        help='generate binary model without LL_ATON_EB_DBG_INFO')

    parser.add_argument('--ecblob-in-params', action='store_const', const=1,
                        help='place the EC blob in param section')

    parser.add_argument('--split', action='store_const', const=1,
                        help='generate a separate binary file for the params/weights')

    parser.add_argument('--llvm', action='store_const', const=1,
                        help='use LLVM compiler and libraries (default: GCC compiler is used)')

    parser.add_argument('--st-clang', action='store_const', const=1,
                        help='use ST CLANG compiler and libraries (default: GCC compiler is used)')

    parser.add_argument('--compatible-mode', action='store_const', const=1,
                        help='set the compible option (target dependent)')

    parser.add_argument('--custom', metavar='STR', type=str, nargs='?',
                        default='no-file',
                        help='config file for custom build (default: custom.json)')

    parser.add_argument('--cross-compile', metavar='STR', type=str,
                        help='prefix of the ARM tool-chain (CROSS_COMPILE env variable can be used)',
                        default='')

    parser.add_argument('--gen-c-file', action='store_const', const=1,
                        help='generate c-file image (DEBUG PURPOSE)')

    parser.add_argument('--parse-only', action='store_true',
                        help='parsing only the generated c-files')

    parser.add_argument('--no-clean', action='store_true',
                        help='Don\'t clean the intermediate files')

    parser.add_argument('--log', metavar='STR', type=str, nargs='?',
                        default='no-log',
                        help='log file')

    parser.add_argument('--json', metavar='STR', type=str, nargs='?',
                        default='no-json',
                        help='Generate result file (json format)')

    parser.add_argument('--verbosity', '-v',
                        nargs='?', const=1, type=int, choices=range(0, 3),
                        default=1, help="set verbosity level")

    parser.add_argument('--debug', action='store_const', const=1,
                        help='Enable internal log (DEBUG PURPOSE)')

    parser.add_argument('--no-color', action='store_const', const=1,
                        help='Disable log color support')

    # Enable development mode (INTERNAL DEV PURPOSE) - Hidden option
    parser.add_argument('--dev-mode', metavar='STR', type=str, nargs='?',
                        default='no-file',
                        help=argparse.SUPPRESS)

    params: Params = Params(parser.parse_args())

    logger = create_logger(params, Path(__file__).stem)

    try:
        res = npu_driver(params)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(e, stack_info=False, exc_info=params.debug)
        return -1

    return res


if __name__ == '__main__':
    sys.exit(main())
