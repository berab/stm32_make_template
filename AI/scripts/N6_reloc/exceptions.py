###################################################################################
#   Copyright (c) 2024 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Module including specific exceptions definition
"""


_ERROR_INDEX_RELOC_PP = 600  # Base index of the error number relative the RELOC process
_ERROR_INDEX_TOOLS = 700  # Base index of the error number relative the tools


class BaseExceptionError(Exception):
    """Base class for specific exceptions"""
    error = 0
    idx = 0

    def __init__(self, mess=None):
        self.mess = mess
        super(BaseExceptionError, self).__init__(mess)

    @property
    def code(self):  # pylint: disable=C0116
        return self.error + self.idx

    def __str__(self):
        _mess = ''
        if self.mess:
            _mess = '{}'.format(self.mess)
        else:
            _mess = '{}'.format(type(self).__doc__.split('\n')[0].strip())
        _msg = 'E{:03d}({}): {}'.format(self.code, type(self).__name__, _mess)
        return _msg


class RelocProcessError(BaseExceptionError):
    """Generic reloc error"""
    error = _ERROR_INDEX_RELOC_PP


class RelocPreProcessError(RelocProcessError):
    """Pre-Process error"""
    idx = 1


class RelocPostProcessError(RelocProcessError):
    """Reloc Post-Process error"""
    idx = 2


class RelocElfProcessError(RelocProcessError):
    """Elf PP error"""
    idx = 3


class RelocBinaryHeaderError(RelocProcessError):
    """Binary Header error"""
    idx = 4


class RelocPrepareError(RelocProcessError):
    """Prepare C-file error"""
    idx = 5


class RelocParserError(RelocProcessError):
    """Parser C-file error"""
    idx = 6


class ToolsError(BaseExceptionError):
    """Generic tools error"""
    error = _ERROR_INDEX_TOOLS


class ExecutableNotFoundError(ToolsError):
    """Executable not found"""
    idx = 1


class ExecutableExecError(ToolsError):
    """Execution fails"""
    idx = 2


class ExecutableBadParameter(ToolsError):
    """Invalid parameter"""
    idx = 3


class JsonParserError(ToolsError):
    """Json parsing error"""
    idx = 4


class CParserError(ToolsError):
    """C parsing error"""
    idx = 5


class FirmwareFileNotFoundError(ToolsError):
    """Firmware file not found"""
    idx = 6
