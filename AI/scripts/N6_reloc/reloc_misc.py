###################################################################################
#   Copyright (c) 2024, 2025 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Misc functions/classes for the relocatable binay object
"""

import os
from enum import Enum
from pathlib import Path
from typing import Union


class MSegmentID(Enum):
    """ID of the memory segment"""
    UNUSED = 0
    FLASH = 2
    RAM = 4
    # PARAM_START = 8
    PARAM_0 = 8
    PARAM_1 = 9
    PARAM_2 = 10

    def __str__(self):
        return self.name


class MPoolCType(Enum):
    """Type of memory pool"""
    UNUSED = 0
    RELOC = 1
    COPY = 2
    RESET = 3
    UNSUPPORTED = 0xFF

    def is_writable(self) -> bool:
        """Indicate if the pool is writable"""
        return self in (MPoolCType.COPY, MPoolCType.RESET)


_SUPPORTED_TYPES = (MPoolCType.UNUSED, MPoolCType.RELOC, MPoolCType.COPY, MPoolCType.RESET)


class MPoolCDataType(Enum):
    """Data type of memory pool"""
    UNDEF = 0
    PARAM = 1  # POOL with only the parameters/constants
    ACTIV = 2  # POOL with only the activations
    MIXED = 3  # POOL with both parameters and activations

    def is_param_only(self) -> bool:
        """Indicate if the pool contains only parameters"""
        return self == MPoolCDataType.PARAM

    def is_activ_only(self) -> bool:
        """Indicate if the pool contains only activations"""
        return self == MPoolCDataType.ACTIV

    def is_mixed(self) -> bool:
        """Indicate if the pool contains both parameters and activations"""
        return self == MPoolCDataType.MIXED


class MPoolCDataAttr(Enum):
    """Data attr of memory pool"""
    UNDEF = 0
    READ = 1  # READ ONLY
    WRITE = 2  # WRITE ONLY
    CACHED = 4  # CACHED
    RCACHED = 5  # READ ONLY and CACHED
    WCACHED = 6  # R/W and CACHED

    def is_readonly(self) -> bool:
        """Indicate if the pool is read-only"""
        return self in (MPoolCDataAttr.READ, MPoolCDataAttr.RCACHED)


_TYPE_SHIFT = 24
_TYPE_MASK = 0xFF

_DATA_SHIFT = 16
_DATA_MASK = 0xFF

_ID_SHIFT = 0
_ID_MASK = 0xFF

_ATTR_SHIFT = 8
_ATTR_MASK = 0xFF


def align_up(size, align=8):
    """Return aligned up value"""  # noqa: DAR101, DAR201
    return (size + align - 1) & (~(align - 1))


class MPoolCDesc():
    """Class to handle the poll C descriptor"""

    BASE_PARAM_RELOC_ID = 0

    def __init__(self, name: str, c_label: str = '', flags: int = 0):
        """."""
        self._name: str = name
        self._c_label: str = c_label
        self._flags: int = flags
        self._foffset: int = 0
        self._dst: int = 0
        self._size: int = 0
        self._raw_data: bytearray = bytearray(0)
        self._err_msg: str = ''

    @property
    def name(self) -> str:
        """Return the name"""
        return self._name

    @property
    def raw_data(self) -> bytearray:
        """Return the associated data"""
        return self._raw_data

    @property
    def c_label(self) -> str:
        """Return the c_label"""
        return self._c_label

    @property
    def size(self) -> int:
        """Return the size"""
        return self._size

    @property
    def flags(self) -> int:
        """Return the flags"""
        return self._flags

    @property
    def foff(self) -> int:
        """Return the foff"""
        return self._foffset

    @property
    def dst(self) -> int:
        """Return the dst"""
        return self._dst

    @property
    def err(self) -> str:
        """Return the err msg"""
        return self._err_msg

    def set_raw_flags(self, flags):
        """Set the flags"""
        self._flags = flags

    def set_flags(self, size: int, relative: bool, with_params: bool,
                  params_only: bool, rw_mode: bool, cacheable: bool):
        """Build the flags field for mpool C-descriptor"""

        # Supported memory pool configuration for relocatable model
        #
        #   relative & params_only & ro     -> RELOC.PARAM.X
        #          params are stored in external flash (part of the binary model), the code is
        #          updated with the @ location (bin_add + offset) at runtime.
        #   relative & !with_params & rw    -> RELOC.ACTIV.X
        #          for activations only placed in external ram (r/w region)
        #          the code is updated with @ provided by the user application at runtime.
        #          Optionally at runtime the memory region can be cleared.
        #   relative & with_params & rw     -> RELOC.MIXED.X
        #          for activations&params placed in external ram (r/w region)
        #          the code is updated with @ provided by the user application at runtime.
        #   absolute & with_params & rw     -> COPY
        #          params are stored in external flash (part of the binary model), thet are copied
        #          in the internal RAM at runtime. Dst@ is fixed at generation/compile time
        #   absolute & !with_params & rw    -> RESET
        #          for activations only at fixed @.
        #          Optionally at runtime, the memory region can be cleared.
        #
        # Other configuration, combination are not supported.
        #
        #   absolute & ro                   -> NOT SUPPORTED

        self._size = size
        self._err_msg = ''
        if size == 0:
            self._flags = MPoolCType.UNUSED.value << _TYPE_SHIFT
        elif relative and params_only and not rw_mode:
            self._flags = MPoolCType.RELOC.value << _TYPE_SHIFT | MPoolCDataType.PARAM.value << _DATA_SHIFT
        elif relative and not with_params and rw_mode:
            self._flags = MPoolCType.RELOC.value << _TYPE_SHIFT | MPoolCDataType.ACTIV.value << _DATA_SHIFT
        elif relative and with_params and rw_mode:
            self._flags = MPoolCType.RELOC.value << _TYPE_SHIFT | MPoolCDataType.MIXED.value << _DATA_SHIFT
        elif not relative and with_params and rw_mode:
            self._flags = MPoolCType.COPY.value << _TYPE_SHIFT | MPoolCDataType.MIXED.value << _DATA_SHIFT
        elif not relative and params_only and not rw_mode:
            self._flags = MPoolCType.COPY.value << _TYPE_SHIFT | MPoolCDataType.PARAM.value << _DATA_SHIFT
        elif not relative and rw_mode and not with_params:
            self._flags = MPoolCType.RESET.value << _TYPE_SHIFT | MPoolCDataType.ACTIV.value << _DATA_SHIFT
        else:
            self._err_msg = f'The mempool \'{self.name}\' is not supported, attrs={"rel" if relative else "abs"}'
            self._err_msg += f'/{"rw" if rw_mode else "ro"}'
            self._err_msg += f'/{"c" if cacheable else "-"}'
            self._err_msg += f'/{"param" if with_params else "activ"}'
            self._flags = MPoolCType.UNSUPPORTED.value << _TYPE_SHIFT
            return

        if cacheable:
            self._flags |= (MPoolCDataAttr.CACHED.value << _ATTR_SHIFT)
        if rw_mode:
            self._flags |= (MPoolCDataAttr.WRITE.value << _ATTR_SHIFT)
        else:
            self._flags |= (MPoolCDataAttr.READ.value << _ATTR_SHIFT)

    @property
    def get_type(self) -> MPoolCType:
        """Return the type"""
        type_value = (self._flags >> _TYPE_SHIFT) & _TYPE_MASK
        return MPoolCType(type_value)

    @property
    def get_data_type(self) -> MPoolCDataType:
        """Return the data type"""
        data_type_value = (self._flags >> _DATA_SHIFT) & _DATA_MASK
        return MPoolCDataType(data_type_value)

    @property
    def get_data_attr(self) -> MPoolCDataAttr:
        """Return the data attr"""
        data_attr_value = (self._flags >> _ATTR_SHIFT) & _ATTR_MASK
        return MPoolCDataAttr(data_attr_value)

    @property
    def get_id(self) -> int:
        """Return the id"""
        return (self._flags >> _ID_SHIFT) & _ID_MASK

    @property
    def is_supported(self) -> bool:
        """Indicate if the mpol is supported"""
        return self.get_type in _SUPPORTED_TYPES

    @property
    def is_used(self) -> bool:
        """Indicate if the mpol is used"""
        return self.get_type not in (MPoolCType.UNSUPPORTED, MPoolCType.UNUSED)

    def set_id(self, idx: int) -> int:
        """Set the reloc id"""
        if self.get_type == MPoolCType.RELOC:
            self._flags |= (idx & _ID_MASK) << _ID_SHIFT
            return idx + 1
        return idx

    def set_dst_addr(self, dst: int):
        """Set the offset and dst address"""
        if self.get_type in (MPoolCType.RESET, MPoolCType.COPY):
            self._dst = dst
        else:
            self._dst = 0

    def set_raw_file(self, file_path: Union[str, Path], foff: int = 0) -> int:
        """Set the associated generated RAW file"""
        file_length_in_bytes = os.path.getsize(file_path)

        if self.get_data_type not in (MPoolCDataType.PARAM, MPoolCDataType.MIXED):
            return foff

        # read the file
        with open(file_path, 'rb') as _f:
            self._raw_data = bytearray(_f.read())
            _f.close()

        # pad with zeros to be 8B-aligned
        if len(self._raw_data) < self._size:
            file_length_in_bytes = self._size
        pad_n = align_up(file_length_in_bytes) - len(self._raw_data)
        self._raw_data += bytearray(pad_n)

        self._foffset = foff
        return self._foffset + len(self._raw_data)

    def flags_to_str(self) -> str:
        """Return human description of the flags"""
        type_ = self.get_type
        data_type_ = self.get_data_type
        data_attr_ = self.get_data_attr

        if type_ == MPoolCType.UNSUPPORTED:
            return f'{type_.name:15s}'

        desc_ = type_.name
        if type_ != MPoolCType.UNUSED:
            desc_ += f'.{data_type_.name}'
        if type_ == MPoolCType.RELOC:
            desc_ += f'.{self.get_id}'
        if type_ != MPoolCType.UNUSED:
            desc_ += f'.{data_attr_.name}'
        return desc_

    def __str__(self):
        """."""
        str_ = f'{self._name:16s} : '
        str_ += f'{self.flags_to_str():22s}'
        str_ += f' foff={self._foffset:08x}'
        str_ += f' dst={self._dst:08x}'
        str_ += f' size={self._size}'
        str_ += f' raw_data={len(self._raw_data)}'
        if self._c_label:
            str_ += f' c_label={self._c_label}'
        return str_
