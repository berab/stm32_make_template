###################################################################################
#   Copyright (c) 2025 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Utility function to deploy a relocatable model
"""

import argparse
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import tempfile
import time
from typing import List, Union, Optional, Tuple
from dataclasses import dataclass


from misc import Params, create_logger, align_up
from tools import STM32CubeIDEResources, CExecutable
from tools import EmbeddedToolChain
from target import BoardPropertyDesc
from binary_mgr import RelocBinaryImage
from exceptions import ToolsError


#
# History
#
#   v1.0 - initial version
#   v1.1 - add llvm/(st-)clang support
#   v1.2 - add support for usbc test firmware
#   v1.3 - remove max-speed mode (usbc conf should be used)
#   v2.0 - add multiple input files support
#


__title__ = 'NPU Utility - ST Load and run (dev environment)'
__version__ = '2.0'
__author__ = 'STMicroelectronics'


_DEFAULT_INPUT = 'build/network_rel.bin'
_GDB_SERVER_PORTNO = 36789
_DEFAULT_BOARD = 'stm32n6570-dk'
_DEFAULT_DEST_ADDR = '0x71000000,0x71800000'
_HEADER_MAGIC = 0x4C45524D  # 'MREL' in little-endian


@dataclass
class InspectedBinaryFile:
    """Inspection result"""
    binary_file: Path
    params_file: Optional[Path]
    f_size: int
    f_params_size: int
    c_name: str
    etoolchain: EmbeddedToolChain
    xip_size: int
    copy_size: int
    acts_size: int
    params_size: int
    ext_ram_size: int
    split_mode: bool
    is_secure: bool
    cpuid: int
    ll_aton_ver: Tuple[int, int, int, int] = (0, 0, 0, 0)

    def __str__(self) -> str:
        """String representation"""
        return (f'{self.binary_file}: size={self.f_size:,d} cpuid=0x{self.cpuid:03x} '
                f'c_name=\'{self.c_name}\' \'{self.etoolchain}\' '
                f'll_aton={self.ll_aton_ver[0]}.{self.ll_aton_ver[1]}.{self.ll_aton_ver[2]}.{self.ll_aton_ver[3]} '
                f'acts/params={self.acts_size:,d}/{self.params_size:,d} '
                f'xip/copy={self.xip_size:,d}/{self.copy_size:,d} '
                f'ext_ram={self.ext_ram_size} split={self.split_mode} secure={self.is_secure}')


def _get_params_file(net_file) -> str:
    """."""
    pfile_ = Path(net_file)
    stem_ = pfile_.stem
    suffix_ = pfile_.suffix
    if stem_.endswith('_rel'):
        nstem_ = stem_ + '_params' + suffix_
        npfile_ = pfile_.parent / nstem_
        return str(npfile_)
    return ''


def _check_supported_mode(mode_params: List[str]):
    """Check if the mode is supported"""
    supported_modes = ['copy', 'xip', 'usbc', 'ext', 'no-overlay', 'no-flash', 'no-run', 'clear']

    for m in mode_params:
        if m not in supported_modes:
            available = ','.join(supported_modes)
            raise ToolsError(f'Unsupported mode: {m}, available modes are: {available}')


def _build_header(addrs: List[int], params_addrs: List[int],
                  xip: bool = False, ext: bool = False,
                  clear: bool = False, no_overlay: bool = False) -> bytearray:
    """Build header for the relocatable binary image"""
    header = bytearray()
    magic_ = _HEADER_MAGIC
    header += magic_.to_bytes(4, byteorder='little')
    nb_addr = len(addrs)
    header += nb_addr.to_bytes(4, byteorder='little')
    flags = 0
    if xip:
        flags |= 0x1
    if ext:
        flags |= 0x2
    if clear:
        flags |= 0x4
    if no_overlay:
        flags |= 0x8
    header += flags.to_bytes(4, byteorder='little')
    for a, p in zip(addrs, params_addrs):
        header += a.to_bytes(4, byteorder='little')
        header += p.to_bytes(4, byteorder='little')
    return header


def _inspect_input_files(input_files: Union[str, Path, List[Path]]) -> List[InspectedBinaryFile]:
    """Inspect the binary files"""
    results: List[InspectedBinaryFile] = []

    if isinstance(input_files, (str, Path)):
        input_files = [Path(input_files)]

    for f in input_files:
        bin_img = RelocBinaryImage(f)
        bin_img.check()
        bin_rt_ctx: dict = bin_img.unpack_rt_context()
        params_off: int = bin_img.PARAMS_offset()
        split_model: bool = False
        params_file: Optional[Path] = None
        f_size: int = 0
        f_params_size: int = 0
        ll_aton_ver: Tuple[int, int, int, int] = (0, 0, 0, 0)

        lver_ = bin_rt_ctx.get("rt_version", 0)
        lver_extra_ = bin_rt_ctx.get("rt_version_extra", 0)
        ll_aton_ver = ((lver_ >> 24) & 0xFF, (lver_ >> 16) & 0xFF, (lver_ >> 8) & 0xFF, lver_extra_)

        if params_off == 0:  # split model, params file is required
            params_file = _get_params_file(f)
            if params_file and Path(params_file).is_file():
                split_model = True
                params_file = Path(params_file)
                f_params_size = params_file.stat().st_size
            else:
                raise ToolsError(f'File \'{params_file}\' is requested.')
        f_size = f.stat().st_size

        result = InspectedBinaryFile(
            binary_file=f,
            params_file=params_file,
            f_size=f_size,
            f_params_size=f_params_size,
            c_name=bin_rt_ctx["c_name"],
            etoolchain=bin_img.flags().get('toolchain', EmbeddedToolChain.NONE),
            xip_size=bin_img.XIP_size(),
            copy_size=bin_img.COPY_size(),
            acts_size=bin_rt_ctx["acts_sz"],
            params_size=bin_rt_ctx["params_sz"],
            ext_ram_size=bin_rt_ctx["ext_ram_sz"],
            split_mode=split_model,
            is_secure=bin_img.flags().get('secure', False),
            cpuid=int(bin_img.flags().get('cpuid', 0), 16),
            ll_aton_ver=ll_aton_ver
        )
        results.append(result)
    return results


def _prepare_deploy_params(models: List[InspectedBinaryFile],
                           board: BoardPropertyDesc,
                           no_overlay: bool = False) -> dict:
    """Prepare deployment parameters from inspected models"""
    max_ext_ram: int = 0
    max_xip_sz: int = 0
    max_copy_sz: int = 0
    cumul_bin_sz: int = 0
    dst_offsets: List[int] = []
    dst_params_offsets: List[int] = []
    cur_offset: int = 0

    if len(models) > board.max_model_size:
        msg_ = f'Number of models ({len(models)}) exceeds the maximum supported '
        msg_ += f'({board.max_model_size})'
        raise ToolsError(msg_)

    for model in models:

        f_name = model.binary_file

        if model.ll_aton_ver[:-1] != board.ll_aton_rt_version[0]:
            msg_ = f'\'{f_name}\': runtime version is invalid, '
            msg_ += f'expected version : {board.ll_aton_rt_version[0]} but have {model.ll_aton_ver[:-1]}'
            raise ToolsError(msg_)

        if model.ext_ram_size > board.ram.acts_ext:
            msg_ = f'\'{f_name}\': requires more external RAM than available '
            msg_ += f'{model.ext_ram_size:,} > {board.ram.acts_ext:,}'
            raise ToolsError(msg_)

        params_offset = 0
        max_ext_ram = max(max_ext_ram, model.ext_ram_size)
        if no_overlay:
            max_xip_sz += align_up(model.xip_size)
            max_copy_sz += align_up(model.copy_size)
        else:
            max_xip_sz = max(max_xip_sz, align_up(model.xip_size))
            max_copy_sz = max(max_copy_sz, align_up(model.copy_size))
        bin_sz = align_up(model.f_size,
                          board.ext_flash.sector_size)
        if model.f_params_size > 0:
            params_sz = align_up(model.f_params_size,
                                 board.ext_flash.sector_size)
            params_offset = cur_offset + bin_sz
            bin_sz += params_sz
        dst_params_offsets.append(params_offset)
        cumul_bin_sz += bin_sz
        dst_offsets.append(cur_offset)
        cur_offset += bin_sz

    return {
        "ext_ram": max_ext_ram,
        "xip_sz": max_xip_sz,
        "copy_sz": max_copy_sz,
        "bin_sz": cumul_bin_sz,
        "dst_offsets": dst_offsets,
        "dst_params_offsets": dst_params_offsets
    }


def st_load_and_run(params: Params, no_banner: bool = False):
    """Post-Process the elf file"""

    logger = logging.getLogger()

    board = BoardPropertyDesc(params.board)
    bin_files: List[InspectedBinaryFile] = _inspect_input_files(params.input)

    mode_params = params.mode.split(',')
    _check_supported_mode(mode_params)
    install_mode = 'xip' if 'xip' in mode_params else 'copy'
    if 'ext' in mode_params:
        install_mode = f'{install_mode}-ext'
    no_flash = bool('no-flash' in mode_params)
    no_run = bool('no-run' in mode_params)
    acts_clear = bool('clear' in mode_params)
    no_overlay = bool('no-overlay' in mode_params)

    if 'usbc' in mode_params:
        install_mode = f'{install_mode}-usbc'

    if not no_banner:
        logger.info('%s (version %s)', __title__, __version__)
        logger.info('Creating date : %s', datetime.now().ctime())
        logger.info('')

    bin_is_llvm = []
    for bin_file in bin_files:
        model_info = str(bin_file).split(' ')
        logger.info('model info     : %s', ' '.join(model_info[:2]))
        logger.info('                 %s', ' '.join(model_info[2:]))

        if bin_file.etoolchain.is_llvm():
            bin_is_llvm.append(True)
        else:
            bin_is_llvm.append(False)

    if any(bin_is_llvm):
        install_mode += '-llvm'

    if any(bin_is_llvm) and not all(bin_is_llvm):
        msg_ = 'All binary files must use the same compiler and librairies'
        raise ToolsError(msg_)

    logger.info('board          : \'%s\'', params.board)
    logger.info('mode           : %s', mode_params)

    use_clang = any([bin_file.etoolchain.is_llvm() or bin_file.etoolchain.is_st_clang() for bin_file in bin_files])
    if 'xip' in mode_params and use_clang:
        logger.warning('XIP mode is not supported with CLANG toolchain, COPY mode is forced')
        install_mode = install_mode.replace('xip', 'copy')

    logger.info('')

    cube_ide = STM32CubeIDEResources(params.cube_ide_dir)

    baudrate = board.baudrate
    com_desc = f'serial:{baudrate}' if 'usbc' not in mode_params else 'serial'

    board_info = str(board).split(' ')
    logger.info('board info     : %s', ' '.join(board_info[:4]))
    logger.info('                 %s', ' '.join(board_info[4:]))
    logger.info('use clang      : %s', use_clang)

    req_mem_ = _prepare_deploy_params(bin_files, board=board, no_overlay=no_overlay)

    if req_mem_['ext_ram'] > board.ram.acts_ext:
        msg_ = 'Model requires more external RAM than available '
        msg_ += f'{req_mem_["ext_ram"]:,} > {board.ram.acts_ext:,}'
        raise ToolsError(msg_)

    if 'xip' in install_mode and board.ram.exec_int < req_mem_['xip_sz']:
        if 'ext' not in install_mode:
            logger.warning('Insufficient internal exec RAM, external RAM is used.')
            install_mode = install_mode.replace('xip', 'xip-ext')
    elif 'copy' in install_mode and board.ram.exec_int < req_mem_['copy_sz']:
        if 'ext' not in install_mode:
            logger.warning('Insufficient internal exec RAM, external RAM is used.')
            install_mode = install_mode.replace('copy', 'copy-ext')

    logger.info('install mode   : \'%s\'', install_mode)

    fw_name_, eflash_ = board.firmware_name(f'{install_mode}')
    dst_addrs_: List[int] = [off + eflash_.base_addr for off in req_mem_['dst_offsets']]
    dst_params_addrs_: List[int] = [off + eflash_.base_addr if off else 0 for off in req_mem_['dst_params_offsets']]

    if len(bin_files) == 1:
        dst_params_addrs_[0] = board.ext_flash.params_addr if dst_params_addrs_[0] else 0

    desc_ = 'non-overlay' if no_overlay else 'overlay'
    desc_ += f' bin={req_mem_["bin_sz"]:,}'
    if 'xip' in install_mode:
        desc_ += f' [xip={req_mem_["xip_sz"]:,}] copy={req_mem_["copy_sz"]:,}'
    else:
        desc_ += f' xip={req_mem_["xip_sz"]:,} [copy={req_mem_["copy_sz"]:,}]'
    desc_ += f' \'installed in {"ext" if "ext" in install_mode else "int"} exec_ram\''
    desc_ += f' ext_ram={req_mem_["ext_ram"]:,}'
    logger.info('total (%s)      : %s', len(bin_files), desc_)
    logger.info(' flash@        : %s', ','.join([f'0x{addr:08X}' for addr in dst_addrs_]))
    logger.info(' flash_params@ : %s', ','.join([f'0x{addr:08X}' for addr in dst_params_addrs_]))
    logger.info('')

    cube_prg: CExecutable = cube_ide.cube_programmer

    logger.info("Resetting the board.")
    cmds = ['-q', '-c', 'port=SWD', 'mode=powerdown', 'freq=2000', 'ap=1']
    cube_prg.run(cmds, assert_on_error=False)

    time.sleep(1)

    def _flash_binary_file(binary_file, dst_addr_, file_name: Optional[str] = None):
        """Flash binary file"""
        file_stats = os.stat(binary_file)
        size = file_stats.st_size
        f_name_ = file_name if file_name is not None else binary_file
        logger.info("Flashing \'%s\' at address %s (size=%s)..", f_name_, f'0x{dst_addr_:08X}', size)
        el = cube_prg.parent / "ExternalLoader" / board.ext_flash.loader_name
        cmds = ['-q', '-c', 'port=SWD', 'mode=hotplug', 'freq=2000', 'ap=1', '--extload',
                el, '--download', str(binary_file), str(dst_addr_)]
        cube_prg.run(cmds, assert_on_error=True, verbosity=params.verbosity > 1)

    header_ = _build_header(dst_addrs_, dst_params_addrs_,
                            xip=('xip' in install_mode),
                            ext=('ext' in install_mode),
                            no_overlay=no_overlay,
                            clear=acts_clear)

    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        temp_file_path = Path(temp_file.name + '.bin')
        with open(temp_file_path, 'wb') as temp_bin:
            temp_bin.write(header_)
        _flash_binary_file(temp_file_path, eflash_.header_addr,
                           f'header (nb_entries={len(dst_addrs_)})')

    if not no_flash:
        for bin_file, dst_addr_, dst_params_addr_ in zip(bin_files, dst_addrs_, dst_params_addrs_):
            _flash_binary_file(bin_file.binary_file, dst_addr_)
            if bin_file.split_mode and bin_file.params_file is not None:
                _flash_binary_file(bin_file.params_file, dst_params_addr_)
    else:
        logger.warning('Binary files are not flashed')

    logger.debug("Starting GDB server port=%s..", _GDB_SERVER_PORTNO)
    cmds = ["-d", "--frequency", "2000", "--apid", "1", "-v",
            "--port-number", str(_GDB_SERVER_PORTNO), "-cp",
            cube_prg.parent]
    cube_ide.gdb_server.run_detached(cmds, verbosity=params.verbosity > 1)

    time.sleep(1)

    logger.info("Loading & start the validation application \'%s\'..", fw_name_.stem)
    cmds = [
        "-ex", f"target remote :{_GDB_SERVER_PORTNO}",
        "-ex", "monitor reset",
        "-ex", "load",
        "-ex", "set $pc = Reset_Handler",
        "-ex", "detach",
        "-ex", "quit",
        str(fw_name_)]
    cube_ide.gdb_client.run(cmds, verbosity=params.verbosity > 1)
    cube_ide.gdb_server.kill()

    logger.info("Deployed model is started and ready to be used.")

    if no_run:
        logger.info('')
        return 0

    time.sleep(1)

    logger.info("Executing the deployed model (desc=%s)..", com_desc)
    logger.info('')

    try:
        from stm_ai_runner import AiRunner
    except ImportError:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ai_runner'))
        try:
            from stm_ai_runner import AiRunner
        except ImportError:
            logger.error('Update the \'PYTHONPATH\' to find the stm_ai_runner Python module.')
            return -1

    runner: AiRunner = AiRunner(debug=params.debug)
    runner.connect(desc=com_desc)
    if not runner.is_connected:
        logger.error(runner.get_error())
        return -1

    for name_ in runner.names:
        logger.info("Found model: c-name=\'%s\'", name_)
        runner.summary(name=name_, print_fn=logger.info)

        inputs = runner.generate_rnd_inputs(name=name_, batch_size=2)
        mode = AiRunner.Mode.PER_LAYER
        if params.debug:
            mode |= AiRunner.Mode.DEBUG
        outputs, profiler = runner.invoke(inputs,  # disable_pb=True,
                                          mode=mode, name=name_)
        runner.print_profiling(inputs, profiler, outputs,
                               print_fn=logger.info,
                               tensor_info=False)
        logger.info('')

    runner.disconnect()

    return 0


def main():
    """Script entry point."""

    parser = argparse.ArgumentParser(description=f'{__title__} v{__version__}')

    parser.add_argument('--input', '-i', metavar='STR', nargs="*",
                        help='location of the binary files (default: %(default)s)',
                        default=_DEFAULT_INPUT)

    parser.add_argument('--board', metavar='STR', type=str,
                        help='ST development board (default: %(default)s)',
                        default=_DEFAULT_BOARD)

    parser.add_argument('--address', metavar='STR', type=str,
                        help='destination address - model(,params) (default: %(default)s)',
                        default=_DEFAULT_DEST_ADDR)

    parser.add_argument('--mode', metavar='STR', type=str,
                        help='firmware variants & mode: copy,xip[no-flash,no-overlay,no-run,usbc,ext]',
                        default='copy')

    parser.add_argument('--cube-ide-dir', metavar='STR', type=str,
                        help='installation directory of STM32CubeIDE tools (ex. ~/ST/STM32CubeIDE_1.18.0/STM32CubeIDE)',
                        default='')

    parser.add_argument('--log', metavar='STR', type=str, nargs='?',
                        default='no-log',
                        help='log file')

    parser.add_argument('--verbosity', '-v',
                        nargs='?', const=1, type=int, choices=range(0, 3),
                        default=1, help="set verbosity level")

    parser.add_argument('--debug', action='store_const', const=1,
                        help='enable internal log (DEBUG PURPOSE)')

    parser.add_argument('--no-color', action='store_const', const=1,
                        help='disable log color support')

    params: Params = Params(parser.parse_args())

    logger = create_logger(params, Path(__file__).stem)

    try:
        res = st_load_and_run(params)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(e, stack_info=False, exc_info=params.debug)
        return -1

    return res


if __name__ == '__main__':
    sys.exit(main())
