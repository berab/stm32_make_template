###################################################################################
#   Copyright (c) 2025 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Utility functions to manage the STM32 tools
"""

import sys
import re
import platform
import os
import shutil
import time
import json
import subprocess
from typing import Tuple, Union, List, Optional, Any, Callable, Dict
from pathlib import Path
import logging
from enum import Enum
from dataclasses import dataclass


from exceptions import ExecutableNotFoundError, ExecutableExecError
from exceptions import ExecutableBadParameter, ToolsError
from misc import Params
from target import DevicePropertyDesc


_ENV_MAKE_EXE = 'MAKE_EXE'
_ENV_MAKE_EXE_NAME = 'make'
_ENV_STEDGEAI_CORE_EXE = 'STEDGEAI_CORE_EXE'
_ENV_STEDGEAI_CORE_DIR = 'STEDGEAI_CORE_DIR'
_STEDGEAI_CORE_EXE_NAME = 'stedgeai'
_ENV_STM32_CUBE_IDE_DIR = 'STM32_CUBE_IDE_DIR'
_ENV_STM32_CUBE_IDE_EXE_NAME = 'stm32cubeidec'


if platform.system() == 'Windows':
    windows_drives = [chr(x) + ":" for x in range(65, 91) if os.path.exists(chr(x) + ":")]
else:
    windows_drives = []


def fix_path(path: str):
    """."""
    if platform.system() == 'Windows' and path:
        path_ = str(os.path.normcase(path))
        for drive_ in windows_drives:
            letter_ = drive_[0].lower()
            if path_.startswith(f'/{letter_}/'):
                path_ = path_.replace(f'/{letter_}/', f'{letter_}:/', 1)
                break
        return os.path.normcase(path_)
    return path


def escape_spaces(path: str) -> str:
    """Escape spaces"""
    return path.replace(' ', '\\ ')


def is_unix_path(path):
    """Check if the path starts with a forward slash"""
    if path.startswith('/'):
        return True
    return False


def run_shell_cmd(
        cmd_line: List[str],
        env: Optional[dict] = None,
        cwd: Optional[str] = None,
        parser=None,
        detached: bool = False,
        verbosity: bool = False,
        assert_on_error: bool = True) -> Tuple[int, List[str], Optional[subprocess.Popen]]:
    """Execute a command in a shell and return the output"""

    logger = logging.getLogger()

    log_debug = logger.info if verbosity else logger.debug

    startupinfo = None
    if sys.platform in ('win32', 'cygwin', 'msys'):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.SW_HIDE | subprocess.HIGH_PRIORITY_CLASS

    if isinstance(cmd_line, list):
        str_args = ' '.join([str(x) for x in cmd_line])
        run_args = cmd_line
    else:
        raise ExecutableBadParameter(f'run_shell_cmd: cmd_line type {type(cmd_line)} is not valid')

    msg_ = f'-> executing the command - (cwd={cwd} os={os.name}, detached={detached})'
    log_debug(msg_)
    msg_ = f'                           env={env})'
    log_debug(msg_)
    log_debug('$ %s', str_args)

    lines = []
    process = None
    elapsed_time = 0.0
    stdout_pipe = subprocess.PIPE  # subprocess.DEVNULL if detached else subprocess.PIPE
    stderr_pipe = subprocess.STDOUT  # subprocess.DEVNULL if detached else subprocess.STDOUT
    try:
        t = time.perf_counter()  # system-wide timing
        process = subprocess.Popen(run_args,
                                   env=env, cwd=cwd,
                                   stdout=stdout_pipe,
                                   stderr=stderr_pipe,  # subprocess.PIPE,
                                   text=True,
                                   startupinfo=startupinfo,
                                   shell=detached,
                                   close_fds=True)

        while not detached:
            line = process.stdout.readline() if process.stdout is not None else ''
            if line == '' and process.poll() is not None:
                break
            if line:
                line = line.rstrip()
                log_debug(' %s', line)
                if parser:
                    parser(line)
                lines.append(line)

        return_code = process.returncode

        if process.stdout is not None:
            process.stdout.close()

        elapsed_time = time.perf_counter() - t
        msg = f"<- {elapsed_time:.03}s - {'SUCCESS' if not return_code else 'FAILED'}({return_code})"
        log_debug(msg)

        if detached:
            return 0, lines, process

        if return_code and assert_on_error:
            if not verbosity:
                for line in lines:
                    logger.error(line)
            raise ExecutableExecError(f'returned code = {return_code} command = {str_args}')

        return return_code, lines, None

    except (OSError, ValueError, FileNotFoundError, RuntimeError) as excep_:
        if process:
            process.kill()
        if isinstance(excep_, RuntimeError) and assert_on_error:
            raise excep_
        return -1, lines, None


def _get_app(exec_name: Union[str, Path],
             env_var: str = '') -> Tuple[str, Path, str]:
    """Return name, path and src type of the executable"""

    # If available, the ENV variable is used in priority to discover the executable
    app_env = os.environ.get(env_var, '')
    if env_var and app_env:  # check if valid
        app_ = Path(app_env)
        file_app_ = shutil.which(app_.stem, path=str(app_.parent))
        if file_app_ is not None:
            return app_.stem, app_.parent, f'env:{env_var}'
        raise ExecutableNotFoundError(f'Unable to find the executable: {env_var}={app_env}')

    # full-path has been provided with exec_name
    exec_name = Path(fix_path(str(exec_name)))
    app_exec = Path(exec_name)
    if app_exec.parent.is_dir():
        file_app_ = shutil.which(app_exec.stem, path=str(app_exec.parent))
        if file_app_ is not None:
            return app_exec.stem, app_exec.parent, 'fullpath'
        if str(app_exec.parent) != '.':
            raise ExecutableNotFoundError(f'Unable to find the executable: path={exec_name}')

    # Check if available in the system PATH
    file_app_ = shutil.which(str(exec_name))
    if file_app_ is not None:
        app_path = Path(file_app_)
        return app_path.stem, app_path.parent, 'path'

    return '', Path(), ''


class ToolVersion:
    """Object to manage the tools version"""

    def __init__(self, version: Any = None, extra: str = ''):
        """Set the version"""
        if not version:
            version = '0.0.0'  # undefined value
        if isinstance(version, ToolVersion):
            version = version.todict()  # copy mode
        if isinstance(version, str):
            vers = version.split(' ')[0].split('.')
            self.major = int(vers[0])
            self.minor = int(vers[1]) if len(vers) > 1 else 0
            self.micro = int(vers[2]) if len(vers) > 2 else 0
            self.extra = extra
        elif isinstance(version, dict):
            self.major = version.get('major', 0)
            self.minor = version.get('minor', 0)
            self.micro = version.get('micro', 0)
            self.extra = version.get('extra', '')
        else:
            raise ValueError(f'Invalid Tool version: {version}')

    def __eq__(self, other):
        if not isinstance(other, ToolVersion):
            other = ToolVersion(other)
        return self.toint() == other.toint()

    def __ge__(self, other):
        if not isinstance(other, ToolVersion):
            other = ToolVersion(other)
        return self.toint() >= other.toint()

    def __gt__(self, other):
        if not isinstance(other, ToolVersion):
            other = ToolVersion(other)
        return self.toint() > other.toint()

    def __le__(self, other):
        if not isinstance(other, ToolVersion):
            other = ToolVersion(other)
        return self.toint() <= other.toint()

    def __lt__(self, other):
        if not isinstance(other, ToolVersion):
            other = ToolVersion(other)
        return self.toint() < other.toint()

    def is_valid(self):
        """Indicate if the version is valid"""
        return self.major != 0 or self.minor != 0

    def todict(self):
        """Return a dict"""
        return {
            'major': self.major, 'minor': self.minor, 'micro': self.micro,
            'extra': self.extra
        }

    def toint(self, to_compare=False):
        """Return integer representation"""
        if to_compare:
            return self.major << 24 | self.minor << 16
        return self.major << 24 | self.minor << 16 | self.micro << 8

    def __str__(self):
        """Return a string human-readable representation"""
        if self.extra:
            return "{major}.{minor}.{micro}-{extra}".format(**self.todict())
        return "{major}.{minor}.{micro}".format(**self.todict())

    def __repr__(self):
        """Return a string representation"""
        return f'(major={self.major}, minor={self.minor}, micro={self.micro}, extra={self.extra})'


class CExecutable():
    """Base class to handle an executable"""

    def __init__(self, exec_name: Union[str, Path], env_var: str = '',
                 parser: Optional[Callable] = None,
                 org_type: str = '',
                 arg_version: Union[str, List[str]] = '--version'):
        """Create handle to manage an executable"""

        self._org_name: Union[str, Path] = exec_name
        self.env: str = env_var
        self._exec_name, self._exec_loc, self._org_type = _get_app(exec_name, env_var)
        if org_type:
            self._org_type = org_type
        self._version: ToolVersion = ToolVersion()
        self._error: int = -1
        self._pack_dir: Union[Path, str] = ''
        self._process: Optional[subprocess.Popen] = None

        def _cb_parser(mess: str):
            if parser is None:
                return
            pres_ = parser(mess)
            if pres_ and not self._version.is_valid():
                self._version = ToolVersion(pres_[0], extra=pres_[1])

        if self.is_valid() and parser and arg_version:
            if isinstance(arg_version, str):
                options_ = [arg_version]
            else:
                options_ = arg_version
            self.run(options_, parser=_cb_parser)

    def __call__(self) -> Path:
        """Return file-path of the executable"""
        return self.file_path

    def is_valid(self) -> bool:
        """Indicate if the executable is valid"""
        return bool(self._exec_name)

    def run(self, params: List[str],
            parser: Optional[Callable] = None,
            env: Optional[dict] = None,
            cwd: Optional[str] = None,
            verbosity: bool = False,
            assert_on_error: bool = True) -> List[str]:
        """Execute the command with the arguments"""
        if not self.is_valid():
            raise ExecutableNotFoundError(f'{self}')
        params = [str(self())] + params
        self._error, st_out, _ = run_shell_cmd(params, verbosity=verbosity,
                                               cwd=cwd, env=env, parser=parser,
                                               assert_on_error=assert_on_error)
        return st_out

    def run_detached(self, params: List[str],
                     parser: Optional[Callable] = None,
                     env: Optional[dict] = None,
                     cwd: Optional[str] = None,
                     verbosity: bool = False,
                     assert_on_error: bool = True) -> Optional[subprocess.Popen]:
        """Execute the command with the arguments"""
        if not self.is_valid():
            raise ExecutableNotFoundError(f'{self}')
        params = [str(self())] + params
        self._error, _, self._process = run_shell_cmd(params, verbosity=verbosity,
                                                      detached=True,
                                                      cwd=cwd, env=env, parser=parser,
                                                      assert_on_error=assert_on_error)
        return self._process

    def kill(self):
        """Kill the on-going sub-process"""
        if self._process is not None:
            self._process.kill()
            self._process = None

    @property
    def org_type(self) -> str:
        """Return origin type"""
        return self._org_type

    def set_org_type(self, org_type: str, forced: bool = False):
        """Set origin type"""
        if self.is_valid() or forced:
            self._org_type = org_type

    @property
    def file_path(self) -> Path:
        """Return the file-path of the executable"""
        if self._exec_name:
            return Path.joinpath(self._exec_loc, self._exec_name)
        return Path(self._org_name)

    @property
    def error(self) -> int:
        """Return the last run error"""
        if self.is_valid():
            return self._error
        return -1

    @property
    def name(self) -> Union[str, Path]:
        """Return the name of the executable"""
        if self._exec_name:
            return self._exec_name
        return self._org_name

    @property
    def location(self) -> Path:
        """Return parent folder of the executable"""
        if self._exec_name:
            f_loc = Path(self._exec_loc).resolve()
            return f_loc
        return Path('')

    @property
    def parent(self):
        """Return parent folder of the executable"""
        return self.location

    def set_pack_dir(self, pack_dir: Union[str, Path]) -> None:
        """Set the pack root location"""
        if self._exec_name:
            self._pack_dir = Path(pack_dir)

    @property
    def pack_dir(self) -> Union[Path, str]:
        """Return the pack root location"""
        return self._pack_dir

    @property
    def version(self) -> ToolVersion:
        """Return the version"""
        return self._version

    def __str__(self):
        """Short description"""
        header_ = f'[CExecutable] name=\'{self.name}\''
        if not self.is_valid():
            return f'{header_} env=\'{self.env}\' <executable not found>'
        else:
            header_ += f' {self._version}' if self._version.is_valid() else ''
        loc_ = str(self.location)
        if len(loc_) > 70:
            loc_ = f'{loc_[0:30]}..{loc_[-30:]}'
        if self.org_type == 'env':
            return f'{header_} location={loc_} (org={self.org_type}:{self.env})'
        else:
            return f'{header_} location={loc_} (org={self.org_type})'


def _cb_parse_stedgeai_version(mess):
    """Parser to retreive the version of ST Edge AI Core utility"""

    pattern = r'v\d+\.\d+\.\d+\b-\d+'
    if 'ST Edge AI Core' in mess:
        match = re.search(pattern, mess)
        if match:
            version = match.group(0).split('-')
            if len(version) > 1:
                return [version[0][1:], version[1]]
            else:
                return [version[0][1:], '']
    return ''


def _cb_parse_make_version(mess: str) -> Union[str, List[str]]:
    """Parser to retreive the version of GNU Make utility"""

    if 'GNU Make' in mess:
        mess = mess.split()[-1]
        mess_list = mess.split('_')
        return [mess_list[0], ''.join(mess_list[1:])]

    return ''


def _cb_parse_version_cube_prog(mess: str) -> Union[str, List[str]]:
    """Parser to retreive the version of STM32 Progammer CLI utility"""

    if 'STM32CubeProgrammer version:' in mess:
        mess = mess.split(':')[-1].strip()
        mess_list = mess.split('-')
        if len(mess_list) > 1:
            return [mess_list[0], mess_list[1]]
        else:
            return [mess_list[0], '']
    return ''


def _cb_parse_version_st_link_server(mess: str) -> Union[str, List[str]]:
    """Parser to retreive the version of ST-LINK_gdbserver utility"""

    if ' version:' in mess:
        mess = mess.split(':')[-1].strip()
        return [mess, '']
    return ''


def _cb_parse_arm_gcc_version(mess: str) -> Union[str, List[str]]:
    """Parser to retreive the version of arm-none-eabi-gcc compiler"""

    pattern = r'\b\d+\.\d+\.\d+\b\s\d+'
    if 'arm-none-eabi-gcc' in mess.lower():
        match = re.search(pattern, mess)
        if match:
            version = match.group(0).split()
            if len(version) > 1:
                return [version[0], version[1]]
            else:
                return [version[0], '']
    return ''


def _cb_parse_gnu_gdb_version(mess: str) -> Union[str, List[str]]:
    """Parser to retreive the version of arm-none-eabi-gcc compiler"""

    if 'gnu gdb' in mess.lower():
        mess = mess.split()[-1].strip()
        mess_list = mess.split('.')
        if len(mess_list) > 3:
            return ['.'.join(mess_list[:3]), mess_list[-1]]
        else:
            return ['.'.join(mess_list[:3]), '']
    return ''


_REGISTERED_TOOLS_: Dict = {
    'undefined': CExecutable('')
}


_HOST_DIR_MAPPING_: Dict = {  # Output of sys.platform
    "win32": "windows",
    "msys": "windows",
    "cygwin": "windows",
    "linux": "linux",
    "linux2": "linux",
    "darwin": "mac"
}


def _get_platform_folder_name() -> str:
    """Return root-name of the folder"""
    plat_ = _HOST_DIR_MAPPING_.get(sys.platform, '')
    if plat_ == 'mac' and platform.machine().lower() == 'arm64':
        plat_ = 'macarm'
    return plat_


_CB_PARSE_VERSION_ = {
    'make': (_cb_parse_make_version, '--version'),
    'mingw32-make': (_cb_parse_make_version, '--version'),
    'stedgeai': (_cb_parse_stedgeai_version, '--version'),
    'arm-none-eabi-gcc': (_cb_parse_arm_gcc_version, '--version'),
    'STM32_Programmer_CLI': (_cb_parse_version_cube_prog, '--version'),
    'ST-LINK_gdbserver': (_cb_parse_version_st_link_server, '--version'),
    'arm-none-eabi-gdb': (_cb_parse_gnu_gdb_version, '--version')
}


def _register_exec(exec_name: Union[str, Path], tag: str, env_var: str = '',
                   parser: Optional[Callable] = None,
                   arg_version: str = '',
                   reset_cache: bool = False) -> CExecutable:
    """Entry point to register/create CExecutable object"""

    if not tag:
        raise ToolsError('Valid tag parameter is requested')

    if reset_cache and tag in _REGISTERED_TOOLS_:
        _REGISTERED_TOOLS_.pop(tag)

    logger = logging.getLogger()
    logger.debug('-> registering the executable \'%s\' (tag=\'%s\', env=\'%s\')..',
                 exec_name, tag, env_var)

    reg_ = _REGISTERED_TOOLS_.get(tag, None)
    if reg_ is not None:
        logger.debug('tag=\'%s\' is already registered', tag)
        logger.debug('<- done - %s', reg_)
        return reg_

    def_parser_, def_opt_ = _CB_PARSE_VERSION_.get(tag, (None, ''))
    parser = parser if parser is not None else def_parser_
    arg_version = arg_version if arg_version else def_opt_
    exec_tool_ = CExecutable(exec_name, env_var, parser=parser,
                             arg_version=arg_version)
    if exec_tool_.is_valid():
        _REGISTERED_TOOLS_[tag] = exec_tool_

    logger.debug('<- done - %s', exec_tool_)
    return exec_tool_


def MakeUtility(exec_name: str = '', env_var: str = '', tag: str = '') -> CExecutable:
    """Make utility handler"""

    tag_ = tag if tag else _ENV_MAKE_EXE_NAME
    env_ = env_var if env_var else _ENV_MAKE_EXE
    exec_name_ = exec_name if exec_name else _ENV_MAKE_EXE_NAME

    res_ = _register_exec(exec_name_, tag_, env_var=env_)
    res_ = _register_exec('mingw32-make', tag_, env_var=env_)

    if not res_.is_valid():
        env_ = env_ if os.environ.get(env_, '') else f'!{env_}'
        return CExecutable(tag_, env_)

    res_.set_pack_dir(Path(res_.file_path.parents[0]))

    return res_


def STEdgeAICore(exec_name: str = '', env_var: str = '', tag: str = '',
                 pack_dir: Union[Path, str] = '') -> CExecutable:
    """ST EdgeAI Core CLI executable handler"""

    tag_ = tag if tag else 'stedgeai'
    env_ = env_var if env_var else _ENV_STEDGEAI_CORE_EXE
    exec_name_ = exec_name if exec_name else _STEDGEAI_CORE_EXE_NAME
    plat_ = _get_platform_folder_name()

    res_: Optional[CExecutable] = None

    if pack_dir:
        if not Path(pack_dir).is_dir():
            msg_err_ = f'STEdgeAICore: pack_dir=\'{pack_dir}\' is not a valid directory.'
            raise ToolsError(msg_err_)
        else:
            app_ = str(Path(pack_dir) / 'Utilities' / plat_ / exec_name_)
            res_ = _register_exec(app_, tag_)
            if not res_.is_valid():
                msg_err_ = f'STEdgeAICore: pack_dir=\'{pack_dir}\' is not a STEdgeAI Core root directory.'
                raise ToolsError(msg_err_)
            res_.set_pack_dir(Path(pack_dir))
            return res_

    # Use the System env. definition: _ENV_STEDGEAI_CORE_EXE or user
    res_ = _register_exec(exec_name_, tag_, env_)
    if res_.is_valid():
        parts_ = res_.file_path.parts
        if len(parts_) > 3 and parts_[-3].lower() == 'utilities' and parts_[-2] == plat_:
            res_.set_pack_dir(Path(res_.file_path.parents[2]))
        return res_

    # Use the System env. definition: _ENV_STEDGEAI_CORE_DIR
    env_pack_dir = os.environ.get(_ENV_STEDGEAI_CORE_DIR, '')
    if env_pack_dir:
        if not Path(env_pack_dir).is_dir():
            msg_err_ = f'STEdgeAICore: {_ENV_STEDGEAI_CORE_DIR}=\'{env_pack_dir}\' is not a valid directory.'
            raise ToolsError(msg_err_)
        else:
            # full path-file is created
            app_ = str(Path(env_pack_dir) / 'Utilities' / plat_ / exec_name_)
            res_ = _register_exec(app_, tag_)
            if not res_.is_valid():
                msg_err_ = f'STEdgeAICore: {_ENV_STEDGEAI_CORE_DIR}=\'{env_pack_dir}\' '
                msg_err_ += 'is not a valid STEdgeAI Core root directory.'
                raise ToolsError(msg_err_)
            else:  # Set the real origin
                res_.set_org_type('env', forced=True)
                res_.env = _ENV_STEDGEAI_CORE_DIR
                res_.set_pack_dir(Path(env_pack_dir))

    if not res_.is_valid():
        res_.env = f'{_ENV_STEDGEAI_CORE_EXE} or {_ENV_STEDGEAI_CORE_DIR}'

    return res_


def ArmGcc():
    """Arm-none-eabi-gcc compiler executable handler"""

    tag_ = 'arm-none-eabi-gcc'
    env_ = 'ARM_GCC_COMPILER_EXE'

    res_ = _register_exec(tag_, tag_, env_)

    if not res_.is_valid():
        env_ = env_ if os.environ.get(env_, '') else f'!{env_}'
        return CExecutable(tag_, env_)

    res_.set_pack_dir(Path(res_.file_path.parents[0]))

    return res_


def STM32CubeIDEDriver(env_var: str = '',
                       cube_ide_dir: Union[Path, str] = '') -> CExecutable:
    """STM32 Cube IDE driver"""

    tag_ = _ENV_STM32_CUBE_IDE_EXE_NAME
    env_ = env_var if env_var else _ENV_STM32_CUBE_IDE_DIR

    res_: Optional[CExecutable] = None

    if cube_ide_dir:
        if not Path(cube_ide_dir).is_dir():
            msg_err_ = f'STM32CubeIDE: cube_ide_dir=\'{cube_ide_dir}\' is not a valid directory.'
            raise ToolsError(msg_err_)
        else:
            app_ = str(Path(cube_ide_dir) / _ENV_STM32_CUBE_IDE_EXE_NAME)
            res_ = _register_exec(app_, tag_, reset_cache=True)
            if not res_.is_valid():
                msg_err_ = f'STM32CubeIDE: root_dir=\'{cube_ide_dir}\' is not a STM32CubeIDE root directory.'
                raise ToolsError(msg_err_)
            res_.set_pack_dir(Path(cube_ide_dir))
            return res_

    # Use the System env. definition (ex. _ENV_STM32_CUBE_IDE_DIR)
    env_pack_dir = os.environ.get(env_, '')
    if not env_pack_dir:
        msg_err_ = f'STM32CubeIDE: \'{env_}\' is not defined.'
        raise ToolsError(msg_err_)
    elif not Path(env_pack_dir).is_dir():
        msg_err_ = f'STM32CubeIDE: {_ENV_STM32_CUBE_IDE_DIR}=\'{env_pack_dir}\' is not a valid directory.'
        raise ToolsError(msg_err_)
    else:
        # full path-file is created
        app_ = str(Path(env_pack_dir) / _ENV_STM32_CUBE_IDE_EXE_NAME)
        res_ = _register_exec(app_, tag_, reset_cache=True)
        if not res_.is_valid():
            msg_err_ = f'STM32CubeIDE: {_ENV_STM32_CUBE_IDE_DIR}=\'{env_pack_dir}\' '
            msg_err_ += 'is not a valid STM32CubeIDE root directory.'
            raise ToolsError(msg_err_)
        else:  # Set the real definition
            res_.set_org_type('env', forced=True)
            res_.env = env_
            res_.set_pack_dir(Path(env_pack_dir))

    return res_


class STM32CubeIDEResources:
    """Root class to handle the STM32CubeIDE resources"""

    def __init__(self, cube_ide_dir: Union[Path, str] = ''):
        """Constructor"""

        self._logger = logging.getLogger()
        self._cubeide_drv = STM32CubeIDEDriver(cube_ide_dir=cube_ide_dir)

        if not self._cubeide_drv.is_valid():
            msg_err_ = f'STM32CubeIDE executable not found - \'{_ENV_STM32_CUBE_IDE_DIR}\' should be set.'
            raise ExecutableNotFoundError(msg_err_)

        self._gdb = self._from_cube_ide('arm-none-eabi-gdb',
                                        pattern='com.st.stm32cube.ide.mcu.externaltools.gnu-tools*')

        self._objcopy = self._from_cube_ide('arm-none-eabi-objcopy',
                                            pattern='com.st.stm32cube.ide.mcu.externaltools.gnu-tools*')

        self._make = self._from_cube_ide('make',
                                         pattern='com.st.stm32cube.ide.mcu.externaltools.make2*')

        self._cube_prg = self._from_cube_ide('STM32_Programmer_CLI',
                                             pattern='com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer*')

        self._gdb_server = self._from_cube_ide('ST-LINK_gdbserver',
                                               pattern='com.st.stm32cube.ide.mcu.externaltools.stlink-gdb-server*')

    def _from_cube_ide(self, exec_name: str, pattern: str) -> CExecutable:
        """Retrieve the executable from the STM32 Cube IDE installation"""

        cube_ide_root = self._cubeide_drv.pack_dir
        cdts = sorted(Path(os.path.join(cube_ide_root, 'plugins')).glob(pattern), reverse=True)
        cdts = [cdt for cdt in cdts if cdt.is_dir()]
        if cdts:
            exec_path = cdts[0] / 'tools' / 'bin'
            exec_ = _register_exec(exec_path / exec_name, tag=exec_name)
            exec_.set_org_type('cube-ide')
            return exec_

        return CExecutable(exec_name)

    @property
    def gdb_server(self) -> CExecutable:
        """."""
        return self._gdb_server

    @property
    def gdb_client(self) -> CExecutable:
        """."""
        return self._gdb

    @property
    def objcopy(self) -> CExecutable:
        """."""
        return self._objcopy

    @property
    def cube_programmer(self) -> CExecutable:
        """."""
        return self._cube_prg

    def __str__(self):
        """."""
        return str(self._cubeide_drv)


class EmbeddedToolChain(Enum):
    """Embedded Arm tool-chain type"""
    NONE = 0x0  # Unknown
    ARM_GCC = 0x8  # Embedded ARM GCC
    ARM_CLANG = 0x9  # Embedded ARM CLANG / LLVM
    ST_ARM_CLANG = 0xA  # Embedded ST ARM CLANG

    def __str__(self):
        """."""
        return EmbeddedToolChain.desc(self.value)

    def is_clang(self) -> bool:
        """."""
        return self.value in [EmbeddedToolChain.ARM_CLANG.value, EmbeddedToolChain.ST_ARM_CLANG.value]

    def is_gcc(self) -> bool:
        """."""
        return self.value == EmbeddedToolChain.ARM_GCC.value

    def is_llvm(self) -> bool:
        """."""
        return self.value == EmbeddedToolChain.ARM_CLANG.value

    def is_st_clang(self) -> bool:
        """."""
        return self.value == EmbeddedToolChain.ST_ARM_CLANG.value

    @property
    def selectors(self) -> Tuple[str, str]:
        """Return tool-chain selector"""
        if self.value == EmbeddedToolChain.ARM_GCC.value:
            return 'GCC', 'armgcc'
        if self.value == EmbeddedToolChain.ST_ARM_CLANG.value:
            return 'ST_CLANG', 'starmclang'
        if self.value == EmbeddedToolChain.ARM_CLANG.value:
            return 'LLVM', 'llvmclang'
        return 'NONE', 'NONE'

    @staticmethod
    def from_value(value: int):
        """."""
        try:
            obj = EmbeddedToolChain(value)
        except ValueError:
            obj = EmbeddedToolChain(0)
        return obj

    @staticmethod
    def desc(value: int) -> str:
        """."""
        if value == EmbeddedToolChain.ARM_GCC.value:
            return 'Embedded ARM GCC'
        if value == EmbeddedToolChain.ARM_CLANG.value:
            return 'Embedded ARM CLANG'
        if value == EmbeddedToolChain.ST_ARM_CLANG.value:
            return 'Embedded ST ARM CLANG'
        return f'<unknown tool-chain id=0x{value:x}>'


@dataclass
class DevParams():
    """Custom development parameters"""
    rt_lib_path: Optional[Path] = None
    rt_lib_inc_dir: Optional[Path] = None
    rt_aton_root_dir: Optional[Path] = None
    enabled: bool = False

    def get(self, attr, default: Any = None) -> Any:
        if self.enabled:
            val_ = getattr(self, attr, None)
            if val_ is not None:
                return val_
        return default


class STEdgeAICustomResources:
    """Root class to handle the custom parameters"""

    def __init__(self, params: Params):
        """Constructor"""

        self._data: Dict = {}
        self._dev_params = DevParams(enabled=params.dev_mode != 'no-file')
        logger = logging.getLogger()

        # dev mode config
        # internal dev mode parameters
        if params.dev_mode is None:
            # dev_mode option w/o argument
            params.dev_mode = 'dev_mode.json'
        if params.dev_mode != 'no-file':
            if not Path(params.dev_mode).is_file():
                if params.dev_mode != 'dev_mode.json':
                    msg_ = f'\'{params.dev_mode}\' is not a regular file'
                    raise ToolsError(msg_)
                else:
                    msg_ = f'\'{params.dev_mode}\' file is expected'
                    logger.warning(msg_)
            else:
                with open(params.dev_mode, 'r', encoding='utf-8') as file:
                    dev_mode_data = json.load(file)
                    for key_, val_ in dev_mode_data.items():
                        if key_.startswith('dev.'):
                            key_ = key_[4:]  # remove 'dev.' prefix
                            self._dev_params.__setattr__(key_, Path(val_))

        # custom parameters
        if params.custom is None:
            # custom option w/o argument
            params.custom = 'custom.json'
        if params.custom != 'no-file':
            if not Path(params.custom).is_file():
                if params.custom != 'custom.json':
                    msg_ = f'\'{params.custom}\' is not a regular file'
                    raise ToolsError(msg_)
            else:
                with open(params.custom, 'r', encoding='utf-8') as file:
                    self._data = json.load(file)

        if params.st_clang:
            self._toolchain = EmbeddedToolChain.ST_ARM_CLANG
        elif params.llvm:
            self._toolchain = EmbeddedToolChain.ARM_CLANG
        else:
            self._toolchain = EmbeddedToolChain.ARM_GCC

    def _get_data(self, key: str, default: Any = ''):
        """."""
        if not self._data:
            return default
        cdt_ = self._data.get(key, default)
        return cdt_

    @property
    def dev(self) -> DevParams:
        """Return dev parameters"""
        return self._dev_params

    @property
    def toolchain(self) -> EmbeddedToolChain:
        """Return toolchain type"""
        return self._toolchain

    @property
    def extra_system_path(self) -> Optional[Path]:
        """."""
        cdt_ = self._get_data('extra_system_path')
        if cdt_:
            return Path(cdt_)
        return None
    
    @property
    def network_runtime_lib(self) -> Optional[Path]:
        """."""
        cdt_ = self._get_data('runtime_network_lib')
        if cdt_:
            return Path(cdt_)
        return None

    @property
    def stedgeai_install_path(self) -> Optional[Path]:
        """Return stedgeai install path"""
        pth = self._get_data('stedgeai_install_path')
        if pth:
            return Path(pth).expanduser().resolve()
        return None

    @property
    def llvm_install_path(self) -> Optional[Path]:
        """Return llvm bin path"""
        pth = self._get_data('llvm_install_path')
        if pth:
            return Path(pth).expanduser().resolve()
        return None

    @property
    def target_triplet(self) -> Optional[str]:
        """Return target triplet of the json, or None if not defined"""
        tt = self._get_data('target_triplet', None)
        return tt

    @property
    def llvm_sysroot(self) -> Optional[Path]:
        """Return target triplet of the json, or None if not defined"""
        pth = self._get_data('llvm_sysroot')
        if pth:
            return Path(pth).expanduser().resolve()
        return None

    @property
    def makefile(self) -> str:
        """Return makefile name"""
        selector_, _ = self.toolchain.selectors
        return f'makefile_{selector_.lower()}'

    @property
    def resources(self) -> Path:
        """Return root resources folder"""
        def_ = Path(os.path.dirname(os.path.realpath(__file__))) / 'resources'
        cdt_ = self._get_data('resources_dir', def_)
        if '{RESOURCES_DIR}' in cdt_:
            cdt_ = Path(cdt_.replace('{RESOURCES_DIR}', str(def_)))
        return cdt_


class STEdgeAICoreNpuResources:
    """Root class to manage the requested NPU resources"""

    def __init__(self, params: Params):
        """Constructor"""

        self._cust = STEdgeAICustomResources(params)

        logger = logging.getLogger()
        self._target = params.target
        self._logger = logger

        device_prop = DevicePropertyDesc(self._target)

        # Force the STedgeAI install path from the JSON if it exist
        if self._cust.stedgeai_install_path is not None:
            params.pack_dir = self._cust.stedgeai_install_path

        self._stedgeai = STEdgeAICore(pack_dir=params.pack_dir)
        if not self._stedgeai.is_valid() and not self._cust.dev.enabled:
            # Try to find it automatically
            cur_file_dir = Path(os.path.dirname(os.path.realpath(__file__)))
            root_cdt = cur_file_dir.parents[1]
            logger.debug('try to use the directory \'%s\'..', root_cdt)
            self._stedgeai = STEdgeAICore(pack_dir=root_cdt)
            if not self._stedgeai.is_valid():
                msg_err_ = f'STEdgeAI executable not found - \'{self._stedgeai.env}\' should be set.'
                raise ExecutableNotFoundError(msg_err_)

        self._pack_dir = self._stedgeai.pack_dir
        self._resources = Path(os.path.dirname(os.path.realpath(__file__))) / 'resources'

        # root of the middlewares
        if self._cust.dev.enabled:
            middlewares_ = self._resources / '..' / '..' / '..' / 'Middlewares' / 'ST' / 'AI'
            middlewares_ = middlewares_.resolve()
        else:
            middlewares_ = Path(self._pack_dir) / 'Middlewares' / 'ST' / 'AI'

        if self._cust.dev.rt_aton_root_dir:
            self._ll_aton_dir = self._cust.dev.rt_aton_root_dir
        else:
            self._ll_aton_dir = middlewares_ / 'Npu'
        
        if self._cust.dev.rt_lib_inc_dir:
            self._rt_lib_inc = self._cust.dev.rt_lib_inc_dir
        else:
            self._rt_lib_inc = middlewares_ / 'Inc'

        if self._cust.dev.rt_lib_path:
            self._rt_lib_path = self._cust.dev.rt_lib_path
        else:
            if self._cust.network_runtime_lib:
                self._rt_lib_path = self._cust.network_runtime_lib
            else:
                self._rt_lib_path = middlewares_ / 'Lib' / self._cust.toolchain.selectors[0]
                root_lib_dir_ = self._rt_lib_path /  device_prop.core_lib_selector
                cdts_ = list(root_lib_dir_.glob('NetworkRuntime*_PIC.a'))
                if not cdts_:
                    msg_err_ = f'Unable to find a valid lib in {root_lib_dir_}'
                    raise ExecutableNotFoundError(msg_err_)
                self._rt_lib_path = cdts_[0]

        self._plt_lib = self._resources / 'platform' / device_prop.family

        if not self.is_valid():
            msg_err_ = 'STEdgeAICoreNpuResources is invalid.'
            raise ExecutableNotFoundError(msg_err_)

    def is_valid(self) -> bool:
        """Test that the directories are valid"""
        errors_: List[str] = []
        if not self._ll_aton_dir.is_dir():
            errors_.append(f'LL_ATON DIR: \'{self._ll_aton_dir}\' is not a valid directory')
        if not self._rt_lib_inc.is_dir():
            errors_.append(f'RUNTIME INC DIR: \'{self._rt_lib_inc}\' is not a valid directory')
        if not self._rt_lib_path.is_file():
            errors_.append(f'RUNTIME LIB: \'{self._rt_lib_path}\' is not a valid file')
        if not self._plt_lib.is_dir():
            errors_.append(f'PLT INC DIR: \'{self._plt_lib}\' is not a valid directory')
        for error_ in errors_:
            self._logger.error(error_)
        return bool(len(errors_) == 0)

    def get_makefile_defines_from_custom(self) -> list[str]:
        """Return a list of custom variables to be added when calling make, depending on the current toolchain"""
        defines = []
        if self._cust.toolchain == EmbeddedToolChain.ARM_CLANG:
            # Add the custom variables for the LLVM toolchain
            opts = {"LLVM_COMPILER_PATH": self._cust.llvm_install_path,
                    "LLVM_SYSROOT": self._cust.llvm_sysroot,
                    "TARGET_TRIPLET": self._cust.target_triplet}
            for k, v in opts.items():
                if v:
                    if isinstance(v, Path):
                        defines.append(f'{k}={escape_spaces(v.as_posix())}')
                    else:
                        defines.append(f'{k}={escape_spaces(v)}')
                # For empty customization, do not add any makefile variable (use defaults of the makefile)
        return defines

    @property
    def stedgeai(self) -> CExecutable:
        """Return STEdgeAI executable handler"""
        return self._stedgeai

    @property
    def pack(self) -> Path:
        """Return root of the pack directory"""
        return Path(self._pack_dir)

    @property
    def target(self) -> str:
        """Return target name"""
        return self._target

    @property
    def makefile(self) -> str:
        """Return makefile name"""
        return self._cust.makefile

    @property
    def resources(self) -> Path:
        """Return path of the platform files"""
        return self._resources
    
    @property
    def env(self) -> Optional[Dict[str, str]]:
        """Return custom environment parameters"""
        if self._cust.extra_system_path is not None:
            return {**os.environ, 'PATH': f"{self._cust.extra_system_path}{os.pathsep}{os.environ['PATH']}"}
        return None

    @property
    def platform(self) -> Path:
        """Return path of the platform files"""
        return self._plt_lib

    @property
    def ll_aton(self) -> Path:
        """Return path of the LL ATON files"""
        return self._ll_aton_dir

    @property
    def rt_lib_inc(self) -> Path:
        """Return path of the header files for the network runtime lib"""
        return self._rt_lib_inc

    @property
    def rt_lib_path(self) -> Path:
        """Return full path of the network runtime lib"""
        return self._rt_lib_path
