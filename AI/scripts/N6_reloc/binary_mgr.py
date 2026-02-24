###################################################################################
#   Copyright (c) 2024, 2025 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Utility functions to manipulate the binay objects
"""

import logging
import os
import sys
import struct
import argparse
from typing import Union, Dict, List, Optional, Any, Callable
from pathlib import Path
from textwrap import dedent
from datetime import datetime


from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from elftools.elf.relocation import RelocationSection
from elftools.elf.descriptions import describe_reloc_type, describe_sh_type, describe_symbol_type


from reloc_misc import MSegmentID, align_up
from reloc_misc import MPoolCDesc, MPoolCType
from logging_utilities import print_table, get_print_fcts
from exceptions import RelocElfProcessError, RelocPostProcessError, RelocBinaryHeaderError
from misc import Params, create_logger
from tools import EmbeddedToolChain
from prepare_network import _FAKE_SIZE


#
# History
#
#   v0.0 - initial version
#   v1.0 - RC version
#   v1.1 - add rt ctx dump
#          complete/fix debug info in gen c/h files
#   v1.2 - add ecblob in params support
#   v1.3 - add json result output support
#

__title__ = 'NPU Utility - Elf/Binary parser'
__version__ = '1.3'
__author__ = 'STMicroelectronics'


_DEFAULT_INPUT = 'build/network_rel.bin'


_MAGIC = 0x4E49424E
_VSEG_ID_MASK = 0xF0000000
_VSEG_OFFSET_MASK = 0x0FFFFFFF
_VSEG_ID_OFF = 28


def _get_id(addr: int):
    """Return ID of the provided address"""
    return (addr & _VSEG_ID_MASK) >> _VSEG_ID_OFF


def _get_offset(addr: int):
    """Return OFFSET of the provided address"""
    return addr & _VSEG_OFFSET_MASK


def _get_base(addr: Union[MSegmentID, int]):
    """Return BASE of the provided address"""
    if isinstance(addr, int):
        return addr & _VSEG_ID_MASK
    else:
        return (0x1 << _VSEG_ID_OFF) * addr.value


# Virtual segment definitions
_VSEG_DESCRIPTOR = {
    MSegmentID.UNUSED:
    {
        'addr': 0x0, 'sname': MSegmentID.UNUSED.name, 'sec_names': []
    },
    MSegmentID.FLASH:
    {
        'addr': _get_base(MSegmentID.FLASH), 'sname': MSegmentID.FLASH.name, 'sec_names': ['.flash', '.relocs']
    },
    MSegmentID.RAM:
    {
        'addr': _get_base(MSegmentID.RAM), 'sname': MSegmentID.RAM.name, 'sec_names': ['.data', '.bss']
    },
    MSegmentID.PARAM_0:
    {
        'addr': _get_base(MSegmentID.PARAM_0), 'sname': MSegmentID.PARAM_0.name, 'sec_names': ['.params_0']
    },
    MSegmentID.PARAM_1:
    {
        'addr': _get_base(MSegmentID.PARAM_1), 'sname': MSegmentID.PARAM_1.name, 'sec_names': ['.params_1']
    },
    MSegmentID.PARAM_2:
    {
        'addr': _get_base(MSegmentID.PARAM_2), 'sname': MSegmentID.PARAM_2.name, 'sec_names': ['.params_2']
    },
}


def _get_vseg_desc(addr: int) -> Dict:
    """Return the associated vseg descriptor"""
    id_ = _get_id(addr)
    try:
        eid_ = MSegmentID(id_)
        return _VSEG_DESCRIPTOR[eid_]
    except ValueError:
        return _VSEG_DESCRIPTOR[MSegmentID.UNUSED]


def _get_vseg(addr: int) -> MSegmentID:
    """."""
    id_ = _get_id(addr)
    try:
        return MSegmentID(id_)
    except ValueError:
        return MSegmentID.UNUSED


_REQUESTED_ELF_SECTIONS = [
    '.flash', '.rel.flash', '.data', '.rel.data', '.relocs', '.bss'
]


_SUPPORTED_REL_TYPE = [
    'R_ARM_ABS32', 'R_ARM_GOT_BREL', 'R_ARM_THM_CALL', 'R_ARM_THM_JUMP24', 'R_ARM_REL32', 'R_ARM_GOT_PREL'
]


_SUPPORTED_CLANG_REL_TYPE = [
    'R_ARM_THM_MOVW_BREL_NC', 'R_ARM_THM_MOVT_BREL', 'R_ARM_THM_MOVW_PREL_NC', 'R_ARM_THM_MOVT_PREL'
]


_REQUESTED_SYMBOLS = [
    '_network_entries', '_network_rt_ctx', '_params_desc'
]


def get_sections_from_elf(obj):
    """Helper function to retreive the sections"""  # noqa: DAR101, DAR201

    sections = {}
    with open(obj, "rb") as _f:
        elf = ELFFile(_f)
        for i, section in enumerate(elf.iter_sections()):
            sect = {}
            sect["idx"] = i
            sect['type'] = describe_sh_type(section['sh_type'])
            sect["name"] = section.name
            sect["addr"] = int(section['sh_addr'])
            sect["offset"] = int(section['sh_offset'])
            sect["size"] = int(section.data_size)
            sect["align"] = int(section.data_alignment)
            sect["data"] = section.data()
            sections[section.name] = sect
        _f.close()
    return sections


def get_symbols_from_elf(obj):
    """Helper function to retreive the symbols"""  # noqa: DAR101, DAR201
    sym_dict = {}
    with open(obj, "rb") as _f:
        elf = ELFFile(_f)
        for section in elf.iter_sections():
            if not isinstance(section, SymbolTableSection):
                continue
            for symbol in section.iter_symbols():
                item = {}
                item["name"] = str(symbol.name)
                item["type"] = describe_symbol_type(symbol['st_info']['type'])
                item["bind"] = symbol['st_info']['bind']
                item["size"] = symbol['st_size']
                item["visibility"] = symbol['st_other']['visibility']
                item["section"] = symbol['st_shndx']
                try:
                    item["section"] = int(item["section"])
                except ValueError:
                    pass
                item["value"] = int(symbol['st_value'])
                sym_dict[str(symbol.name)] = item
        _f.close()
    return sym_dict


def get_relocations_from_elf(obj):
    """Helper function to return the list of relocated objects"""  # noqa: DAR101, DAR201
    rel_list = []
    with open(obj, "rb") as _f:
        elf = ELFFile(_f)
        for section in elf.iter_sections():
            if not isinstance(section, RelocationSection):
                continue
            # print("***** ", section['sh_link'], section.name, section['sh_name'], section['sh_type'])
            symtable = elf.get_section(section['sh_link'])
            for rel in section.iter_relocations():
                # rel -> r_offset:int, r_info: int, r_info_sym: idx,int, r_info_type: int
                if rel['r_info_sym'] == 0:
                    continue
                item = {}
                item["offset"] = int(rel['r_offset'])
                item["info"] = rel['r_info']
                item["type"] = describe_reloc_type(rel['r_info_type'], elf)
                symbol = symtable.get_symbol(rel['r_info_sym'])
                item["sym_type"] = describe_symbol_type(symbol['st_info']['type'])
                # print(f"* symbol r_info_sym={rel['r_info_sym']} name=\"{symbol.name}\" : ", symbol.entry)
                if symbol['st_name'] == 0:
                    # section name is used as name
                    symsec = elf.get_section(symbol['st_shndx'])
                    item["name"] = str(symsec.name)
                else:
                    item["name"] = str(symbol.name)
                item["value"] = symbol["st_value"]
                vseg_org = _get_vseg_desc(item["offset"])
                vseg_val = _get_vseg_desc(item["value"])
                item["vseg"] = f'{vseg_org["sname"]}:{vseg_val["sname"]}'
                item['status'] = ''
                item['extra'] = ''
                rel_list.append(item)
        _f.close()
    return rel_list


class RelocBinaryImage():
    """."""

    _ITEM_SIZE = 4  # word size (4bytes)
    _HEADER = {  # name, offset (word value - multiple of 4bytes)
        'magic': 0,
        'flags': 1,
        'data_start': 2,
        'data_end': 3,
        'data_data': 4,
        'bss_start': 5,
        'bss_end': 6,
        'got_start': 7,
        'got_end': 8,
        'rel_start': 9,
        'rel_end': 10,
        'params_start': 11,
        'params_offset': 12,

        'ne.ec_init': 13,
        'ne.ec_inference': 14,
        'ne.input_set': 15,
        'ne.input_get': 16,
        'ne.output_set': 17,
        'ne.output_get': 18,

        'ne.epochs': 19,
        'ne.output_buffers': 20,
        'ne.input_buffers': 21,
        'ne.weight_encryption_info': 22,
        'ne.blob_encryption_info': 23,
        'ne.internal_buffers': 24,
        'ne.ctx': 25,
    }

    _RT_CTX = {
        # ctx structure
        # name: (offset, type) word value - multiple of 4bytes
        # see "struct ai_reloc_rt_ctx" in ll_aton_reloc_network.h file
        'state': (0, None),
        'file_addr': (1, None),
        'ram_addr': (2, None),
        'rom_addr': (3, None),
        'cbs_addr': (4, None),
        'c_name': (5, str),
        'acts_sz': (6, int),
        'params_sz': (7, int),
        'ext_ram_sz': (8, int),
        'rt_version_desc': (9, str),
        'rt_version': (10, int),
        'rt_version_extra': (11, int),
        'params_bin_sz': (12, int),
        'params_bin_crc32': (13, int),
        'rt_c_struct_sizes': (14, int),
        'reserved1': (15, None),
        'reserved2': (16, None),
    }

    _ITEM_SYM_MIN = 13
    _ITEM_SYM_MAX = 23

    def __init__(self, data: Union[bytearray, str, Path],
                 logger: Optional[Union[str, logging.Logger]] = None):
        """."""

        if isinstance(data, (bytearray, bytes)):
            self._data = bytearray(data)
        else:
            fpath_ = Path(data)
            if not os.path.isfile(fpath_):
                msg_ = f'\'{fpath_}\' is not a regular file'
                raise RelocElfProcessError(msg_)
            with open(fpath_, mode='rb') as read_file:
                self._data = bytearray(read_file.read())
                read_file.close()

        if isinstance(logger, str) or logger is None:
            logger = logging.getLogger()
        self._logger = logger

        self._logger.debug('creating RelocBinaryImage object')

        self._status = 'INIT'

        # check magic value
        magic_ = self['magic']
        if magic_ != _MAGIC:
            msg_ = f'Invalid magic value - {magic_:08x} instead {_MAGIC:08x}'
            raise RelocBinaryHeaderError(msg_)
        # check reported base@
        base_addr_ = self['data_start']
        vseg_ = _VSEG_DESCRIPTOR[MSegmentID.RAM]
        expected_addr_ = vseg_['addr']
        if base_addr_ != expected_addr_:
            msg_ = f'Invalid addr for {vseg_["sname"]} segment - {base_addr_:08x} instead {expected_addr_:08x}'
            raise RelocBinaryHeaderError(msg_)
        base_addr_ = _get_base(self['data_data'])
        vseg_ = _VSEG_DESCRIPTOR[MSegmentID.FLASH]
        expected_addr_ = vseg_['addr']
        if base_addr_ != expected_addr_:
            msg_ = f'Invalid addr for {vseg_["sname"]} segment - {base_addr_:08x} instead {expected_addr_:08x}'
            raise RelocBinaryHeaderError(msg_)

        self._with_data = len(self._data) > _get_offset(self['data_data'])

        self._logger.debug(' %s', str(self))

    def header_size(self):
        """Return size in bytes of the header"""
        return len(RelocBinaryImage._HEADER) * RelocBinaryImage._ITEM_SIZE

    def data(self):
        """."""
        return self._data

    def decode_flags(self):
        """Decode the flags field"""
        flags_ = self['flags']
        desc_ = {}
        desc_['vers_major'] = (flags_ >> 28) & 0xF
        desc_['vers_minor'] = (flags_ >> 24) & 0xF
        desc_['secure'] = bool((flags_ >> 20) & 0x1)
        desc_['dbg_info'] = bool((flags_ >> 21) & 0x1)
        desc_['async_mode'] = bool((flags_ >> 22) & 0x1)
        desc_['toolchain'] = self.toolchain
        desc_['float-abi'] = (flags_ >> 13) & 0x3
        desc_['fpu'] = bool((flags_ >> 12) & 0x1)
        desc_['cpuid'] = f'{flags_ & 0xFFF:03X}'
        str_desc_ = f'v{desc_["vers_major"]}.{desc_["vers_minor"]}'
        str_desc_ += f' dbg={desc_["dbg_info"]}'
        str_desc_ += f' async={desc_["async_mode"]}'
        str_desc_ += f' sec={desc_["secure"]}'
        str_desc_ += f' \'{desc_["toolchain"]}\''
        str_desc_ += f' cpuid={desc_["cpuid"]}'
        str_desc_ += f' fpu={desc_["fpu"]}'
        str_desc_ += f' float-abi={desc_["float-abi"]}'
        desc_['description'] = str_desc_
        return desc_

    def __getitem__(self, key):
        """."""
        return struct.unpack_from("<I", self._data,
                                  RelocBinaryImage._HEADER[key] * RelocBinaryImage._ITEM_SIZE)[0]

    def __setitem__(self, key, value):
        """."""
        self._status = 'UPDATED'
        struct.pack_into("<I", self._data,
                         RelocBinaryImage._HEADER[key] * RelocBinaryImage._ITEM_SIZE, value)

    @property
    def toolchain(self) -> EmbeddedToolChain:
        """."""
        flags_ = self['flags']
        return EmbeddedToolChain.from_value((flags_ >> 16) & 0xF)

    def flags(self) -> dict:
        """."""
        return self.decode_flags()

    def IMG_size(self) -> int:
        """."""
        return len(self.data())

    def RO_size(self) -> int:
        """."""
        return _get_offset(self['data_data'])

    def RW_size(self) -> int:
        """."""
        return _get_offset(self['bss_end'])

    def PARAMS_offset(self) -> int:
        """."""
        return _get_offset(self['params_offset'])

    def PARAMS_size(self) -> int:
        """."""
        if self.PARAMS_offset() == 0:
            return 0
        return self.IMG_size() - self.PARAMS_offset()

    def XIP_size(self) -> int:
        """."""
        return align_up(self.RW_size())

    def COPY_size(self) -> int:
        """."""
        return align_up(self.XIP_size() + self.RO_size())

    def check(self):
        """Check the contents of the REL/GOT sections"""
        bss_start_ = _get_offset(self['bss_start'])
        bss_end_ = _get_offset(self['bss_end'])
        data_end_ = _get_offset(self['data_end'])
        max_flash_off_ = _get_offset(self['data_data'])
        flash_base_ = 0
        data_base_ = _get_offset(self['data_data'])
        n_err_ = 0

        def __check_valid_offset(val_):
            """."""
            _vseg_ = _get_vseg_desc(val_)
            _mseg_ = _get_vseg(val_)
            _off_ = _get_offset(val_)
            if _mseg_ == MSegmentID.RAM:
                if (data_end_ < _off_ < bss_start_) or _off_ > bss_end_:
                    msg_ = f'Invalid offset, not in RAM segment - {_vseg_["sname"]} + {_off_}'
                    self._logger.error(msg_)
                    return 1, _vseg_
            elif _mseg_ == MSegmentID.FLASH:
                if _get_offset(val_) > max_flash_off_:
                    msg_ = f'Invalid offset, not in FLASH segment - {_vseg_["sname"]} + {_off_}'
                    self._logger.error(msg_)
                    return 1, _vseg_
            elif _mseg_ in (MSegmentID.PARAM_0, MSegmentID.PARAM_1):
                return 0, _vseg_
            else:
                msg_ = f'Invalid segment - {_vseg_["sname"]} + {_off_}'
                self._logger.error(msg_)
                return 1, _vseg_
            return 0, _vseg_

        self._logger.debug('-> checking the REL/GOT sections..')

        # check REL section
        rel_start_ = _get_offset(self['rel_start'])
        rel_end_ = _get_offset(self['rel_end'])
        nb_rel_ = int((rel_end_ - rel_start_) / 4)
        for idx in range(nb_rel_):
            off_ = flash_base_ + rel_start_ + idx * RelocBinaryImage._ITEM_SIZE
            val_ = struct.unpack_from("<I", self._data, off_)[0]
            if val_ < 0x40000000:
                v_off_ = _get_offset(val_)
            else:
                v_off_ = data_base_ + _get_offset(val_)
            r_val_ = struct.unpack_from("<I", self._data, v_off_)[0]
            err_, vseg_ = __check_valid_offset(r_val_)
            n_err_ += err_
            msg_ = f'REL/{idx:<3d} - {val_:08x} -> {r_val_:08x} -> {vseg_["sname"]} + {_get_offset(r_val_)}'
            if err_:
                self._logger.error(msg_)
            else:
                self._logger.debug(msg_)

        # check GOT section
        got_start_ = _get_offset(self['got_start'])
        got_end_ = _get_offset(self['got_end'])
        nb_rel_ = int((got_end_ - got_start_) / 4)
        for idx in range(nb_rel_ - 3):
            off_ = data_base_ + got_start_ + idx * RelocBinaryImage._ITEM_SIZE
            val_ = struct.unpack_from("<I", self._data, off_)[0]
            err_, vseg_ = __check_valid_offset(val_)
            n_err_ += err_
            msg_ = f'GOT/{idx:<3d} - {off_ - data_base_:08x} {val_:08x} -> {vseg_["sname"]} + {_get_offset(val_)}'
            if err_:
                self._logger.error(msg_)
            else:
                self._logger.debug(msg_)

        if n_err_:
            msg_ = f' {n_err_} objects can be not relocated'
            raise RelocPostProcessError(msg_)

        self._logger.debug('<- done - %s error(s)', n_err_)

    def _decode_const_str(self, off) -> str:
        """Return decoded const str"""
        if off == 0:
            return '<undefined>'
        bname_ = bytes()
        max_ = 60
        while self._data[off] != 0 and max_:
            bname_ += struct.unpack_from("c", self._data, off)[0]
            off += 1
            max_ -= 1
        bname_ += bytes(0)
        return bname_.decode(encoding="utf-8")

    def unpack_rt_context(self, data: Optional[bytearray] = None) -> Dict:
        """Decode RT context"""

        res = {}
        cd_off_ = _get_offset(self['ne.ctx'])
        if data is None:
            data = self._data
            cd_off_ += _get_offset(self['data_data'])

        for attr_, item_ in RelocBinaryImage._RT_CTX.items():
            attr_type_ = item_[1]
            offset_ = cd_off_ + item_[0] * RelocBinaryImage._ITEM_SIZE
            val_ = struct.unpack_from("<I", data, offset_)[0]
            if attr_type_ == str:
                res[attr_] = self._decode_const_str(_get_offset(val_))
            elif attr_type_ == int:
                res[attr_] = val_

        # decode specific fields
        res['rt_c_struct_sizes'] = {
            'll_buffer_info': (res.get('rt_c_struct_sizes', 0) >> 8) & 0xFF,
            'epochblock_item': res.get('rt_c_struct_sizes', 0) & 0xFF
        }
        res['params_bin_crc32'] = f'0x{res.get("params_bin_crc32", 0):08x}'

        return res

    def unpack_mempool_c_descriptors(self, data: Optional[bytearray] = None) -> List:
        """Return list with mempool c descriptors"""

        def _decode_entry(off_: int, data_: bytearray):
            addr_name_ = struct.unpack_from("<I", data_, off_)[0]
            name_ = self._decode_const_str(_get_offset(addr_name_))
            flags_ = struct.unpack_from("<I", data_, off_ + 4)[0]
            foff_ = struct.unpack_from("<I", data_, off_ + 8)[0]
            dst_ = struct.unpack_from("<I", data_, off_ + 12)[0]
            size_ = struct.unpack_from("<I", data_, off_ + 16)[0]
            mpd_ = MPoolCDesc('')
            mpd_.set_raw_flags(flags_)
            item_ = {
                'name': f'{name_}',
                'addr': f'0x{addr_name_:08x}',
                'flags_raw': f'0x{flags_:08x}',
                'flags_desc': mpd_.flags_to_str(),
                'foff': foff_,
                'dst': f'0x{dst_:08x}',
                'size': size_
            }
            return item_

        items_ = []
        cd_off_ = _get_offset(self['params_start'])
        if data is None:
            data = self._data
            cd_off_ += _get_offset(self['data_data'])
        cont = True
        nb_entries = 0
        while cont:
            items_.append(_decode_entry(cd_off_, data))
            val_ = struct.unpack_from("<I", data, cd_off_)[0]
            cd_off_ += (4 * 5)
            nb_entries += 1
            if val_ == 0 or nb_entries > 10:
                cont = False

        return items_

    def to_dict(self, data: Optional[bytearray] = None) -> Dict:
        """Return dictionary representing the binary image"""

        def _section_size(sec):
            """."""
            return _get_offset(self[f'{sec}_end']) - _get_offset(self[f'{sec}_start'])

        res_ = {}
        decode_ = self.decode_flags()
        toolchain_ = decode_['toolchain']
        decode_['toolchain'] = decode_['toolchain'].name
        res_['flags'] = decode_
        res_['img_size'] = self.IMG_size()
        res_['params_offset'] = self.PARAMS_offset()
        res_['params_size'] = self.PARAMS_size()
        res_['xip_size'] = self.XIP_size()
        res_['copy_size'] = self.COPY_size()
        res_['ro_size'] = self.RO_size()
        res_['rw_size'] = self.RW_size()
        res_['sections'] = {
            'header': self.header_size(),
            'data': _section_size('data'),
            'bss': _section_size('bss'),
            'got': _section_size('got'),
            'rel': _section_size('rel')
        }
        items_ = self.unpack_mempool_c_descriptors(data)
        res_['mempool_c_descriptors'] = items_[:-1]
        rt_ctx = self.unpack_rt_context(data)
        res_['rt_context'] = rt_ctx
        res_['img_params_size'] = rt_ctx.get('params_bin_sz', 0)
        res_['acts_size'] = rt_ctx.get('acts_sz', 0)

        notes: List[str] = []
        if toolchain_.is_clang():
            notes.append('[INFO] Only COPY mode is supported. The binary image has been built with a Clang toolchain.')
        for item_ in items_:
            mpd_ = MPoolCDesc(item_["name"], flags=int(item_["flags_raw"], 16))
            if mpd_.get_type.is_writable() and mpd_.get_data_attr.is_readonly():
                mp_ = f'{mpd_.name}:0x{item_["foff"]:08x}/{item_["size"]:,d}'
                msg_ = f'[WARNING] A WRITEABLE memory pool \'{mp_}\' with READONLY data attribute is defined.'
                notes.append(msg_)
        res_['notes'] = notes
        return res_

    def _log_mempool_c_descriptors(self, print_fn, data: Optional[bytearray] = None):
        """Display/log mempool c-descriptors"""

        items_ = self.unpack_mempool_c_descriptors(data)

        rows_ = []
        for item_ in items_:
            row_ = [f'{item_["name"]} ({item_["addr"]})', f'{item_["flags_raw"]} {item_["flags_desc"]}']
            row_ += [f'{item_["foff"]:<10d}', f'{item_["dst"]}', f'{item_["size"]:d}']
            rows_.append(row_)

        header_ = ['name (addr)', 'flags', 'foff', 'dst', 'size']
        colalign_ = ('left', 'left', 'left', 'left', 'left')
        title_ = f'mempool c-descriptors (off={self["params_start"]:08x}'\
                 f', {len(rows_)} entries, from {_get_vseg(self["params_start"]).name})'
        print_table(header_, rows_, print_fn, colalign_, title=title_)

    def summary(self, pr_fn: Optional[Callable] = None,
                decode: Optional[Callable[[int], str]] = None,
                data: Optional[bytearray] = None,
                short_desc: bool = False):
        """Prints a string summary of the network binary image"""

        pr_fn = pr_fn if pr_fn is not None else self._logger.info

        res_ = self.to_dict(data)

        def _section_size(sec):
            """."""
            return res_['sections'][sec]

        rows_ = []
        for idx, k in enumerate(RelocBinaryImage._HEADER.keys()):
            value = self[k]
            comment_ = ''
            if idx == 1:
                comment_ = f'{res_["flags"]["description"]}'
            elif idx == 2:
                comment_ = f'data size = {_section_size("data")}'
            elif idx == 4:
                comment_ = f'- RO size = {self.RO_size()}'
            elif idx == 5:
                comment_ = f'bss size = {_section_size("bss")}'
            elif idx == 6:
                comment_ = f'- RW size = {self.RW_size()}'
            elif idx == 7:
                s_ = _section_size("got")
                comment_ = f'got size = {s_} - {int(s_ / RelocBinaryImage._ITEM_SIZE)} items'
            elif idx == 9:
                s_ = _section_size("rel")
                comment_ = f'rel size = {s_} - {int(s_ / RelocBinaryImage._ITEM_SIZE)} items'
            elif (idx == 11 or RelocBinaryImage._ITEM_SYM_MIN <= idx <= RelocBinaryImage._ITEM_SYM_MAX) and decode:
                comment_ = decode(value)

            rows_.append([f'{idx}', f'{k:s}', f'{value:08x}', comment_])

        header_ = ['idx', 'key', 'value', 'description']
        colalign_ = ('left', 'left', 'left', 'left')
        title_ = f'{self}'
        if not short_desc:
            print_table(header_, rows_, pr_fn, colalign_, title=title_)

        def _print_field_(field_, value_):
            msg_ = f'{field_:20s} = {value_}'
            pr_fn(msg_)

        pr_fn('')
        if short_desc:
            pr_fn(res_["flags"]["description"])
            pr_fn('')
        extra_ = f' data({_section_size("data")})+got({_section_size("got")})+bss({_section_size("bss")}) sections'
        val_ = f'{self.XIP_size():<10,}{extra_}'
        _print_field_('XIP size', val_)

        extra_ = f' +ro({self.RO_size()}) sections'
        val_ = f'{self.COPY_size():<10,}{extra_}'
        _print_field_('COPY size', val_)

        extra_ram_ = _section_size("got")
        extra_ro_ = _section_size("header") + _section_size("rel")
        extra_sec_ = f' got:{extra_ram_}({extra_ram_ * 100 / self.RW_size():.1f}%)'
        extra_sec_ += f' header+rel:{extra_ro_}({extra_ro_ * 100 / self.RO_size():.1f}%)'
        msg_ = f'{extra_ram_ + extra_ro_ :<10,}{extra_sec_}'
        _print_field_('extra sections', msg_)

        params_bin_sz = 0
        msg_ = f'{res_["rt_context"]["params_sz"]:<10,}'
        if self.PARAMS_offset() == 0:
            params_bin_sz = res_["rt_context"]["params_bin_sz"]
            msg_ += ' not included in the binary file'
        _print_field_('params size', msg_)

        _print_field_('acts size', f'{res_["rt_context"]["acts_sz"]:<10,}')
        _print_field_('binary file size', f'{res_["img_size"]:<10,}')
        _print_field_('params file size', f'{params_bin_sz:<10,}')

        if _get_vseg(self['params_start']) == MSegmentID.RAM and (self._with_data or data is not None):
            pr_fn('')
            self._log_mempool_c_descriptors(pr_fn, data=data)
        else:
            pr_fn('no data available for mempool c-descriptors')

        rt_ctx = res_['rt_context']
        pr_fn('')
        msg_ = f'rt_ctx: c_name=\"{rt_ctx["c_name"]}\", acts_sz={rt_ctx["acts_sz"]:,}'
        msg_ += f', params_sz={rt_ctx["params_sz"]:,}, ext_ram_sz={rt_ctx["ext_ram_sz"]:,}'
        pr_fn(msg_)
        msg_ = f'rt_ctx: rt_version_desc=\"{rt_ctx["rt_version_desc"]}\"'
        pr_fn(msg_)

        if res_['notes']:
            pr_fn('')
            pr_fn('Notes:')
        for note_ in res_['notes']:
            pr_fn(f' - {note_}')

        pr_fn('')

    def __repr__(self) -> str:
        """."""
        desc_ = self.decode_flags()
        msg_ = f'RelocBinaryImage - v{desc_["vers_major"]}.{desc_["vers_minor"]} / '
        msg_ += f'{self._status} - {self.header_size()}B - {len(self._data):,}'
        msg_ += f' ({"code+params" if self.PARAMS_offset() else "code only"})'
        return msg_


class ElfPostProcess():
    """Class to manage the ELF file and to generate the binary file"""

    def __init__(self, filepath: Union[Path, str],
                 paramspath: Union[str, Path] = '',
                 clang_mode: bool = False,
                 logger: Optional[Union[str, logging.Logger]] = None):
        """Constructor"""

        self._sections: Dict = {}
        self._symbols: Dict = {}
        self._reloc: List = []
        self._sec_flash: Dict
        self._sec_data: Dict
        self._sec_param0: Dict
        self._skipped_addrs: List[int] = []
        self._ec_blobs: Dict = {}
        self._paramspath: Union[str, Path] = paramspath
        self._split: bool = False
        self._clang_mode: bool = clang_mode
        self._ecblob_in_params: bool = False

        self._rel_sect: bytearray = bytearray()

        if isinstance(logger, str) or logger is None:
            logger = logging.getLogger()
        self._logger = logger

        self._filepath = Path(filepath)
        self._image: bytearray = bytearray()

        if not os.path.isfile(self._filepath):
            msg_ = f'\'{self._filepath}\' is not a regular file'
            raise RelocElfProcessError(msg_)

        logger.debug('')
        logger.debug('-> ElfPostProcess (v%s): processing the \"%s\" file',
                     __version__, self._filepath)
        logger.debug(' clang_mode = %s', str(self._clang_mode))

        # Extract main info from the elf file
        logger.debug('Extracting sections..')
        self._sections = get_sections_from_elf(self._filepath)
        self._symbols = get_symbols_from_elf(self._filepath)
        self._reloc = get_relocations_from_elf(self._filepath)

        logger.debug('')
        self._log_sections(self._logger.debug)

        # sanity check
        logger.debug('')
        logger.debug('Sanity check..')
        self._sanity_check()
        logger.debug(' OK')

        # set the main objects
        self._sec_flash = self._sections['.flash']
        self._sec_data = self._sections['.data']
        self._sec_param0 = self._sections['.params_0']
        self._bin_header = RelocBinaryImage(self._sec_flash['data'])

        # remove fake data
        self._sec_param0['data'] = bytearray(self._sec_param0['data'][:-_FAKE_SIZE])
        self._sec_param0['size'] = len(self._sec_param0['data'])
        self._ecblob_in_params = bool(self._sec_param0['size'] != 0)

        if self._clang_mode:  # check that got section is empty
            if self._bin_header['got_start'] != self._bin_header['got_end']:
                msg_ = 'SANITY CHECK: clang mode - Invalid binary - GOT section is not empty'
                raise ValueError(msg_)

        # compute the list of the skipped @
        self._build_skipped_addresses()

        # compute the size of the blobs
        logger.debug('Searching the blob objects..')

        for key, value in self._symbols.items():
            if key.startswith('_ec_blob_') and value["type"] == 'OBJECT':
                msg_ = f' found \'{key}\' symbol, size={value["size"]}'
                logger.debug(msg_)
                key_s_ = key.split('_')
                if key_s_[-2].isnumeric():  # relocate blob
                    name_ = '_'.join(key_s_[:len(key_s_) - 1])
                    ext_ = key_s_[-1]
                else:
                    name_ = key
                    ext_ = ''
                item_ = self._ec_blobs.get(name_, [0, MSegmentID.UNUSED, 0, MSegmentID.UNUSED, ext_])
                if not item_[4] and ext_:
                    item_[4] = ext_
                vseg_ = _get_vseg(value["value"])
                if vseg_ == MSegmentID.RAM:
                    item_[0] += value["size"]
                    item_[1] = vseg_
                else:
                    item_[2] += value["size"]
                    item_[3] = vseg_
                self._ec_blobs[name_] = item_

        msg_ = f' there is {len(self._ec_blobs)} entries.'
        logger.debug(msg_)
        msg_ = f' ecblobs in params: {self._ecblob_in_params} (size={self._sec_param0["size"]:,})'
        logger.debug(msg_)
        if self._ecblob_in_params:
            self._update_mempool_offsets()

        def decode_sym_(addr: int) -> str:
            """."""
            sym_desc_ = self._get_symbol(addr)
            if sym_desc_ is not None:
                return sym_desc_['name']
            else:
                return '<symbol not found>'
            # return self._get_symbol(addr)['name']

        logger.debug('')
        logger.debug('Initial binary header')
        self._bin_header.summary(self._logger.debug, decode_sym_,
                                 data=self._sec_data['data'])

        logger.debug('')
        logger.debug('Building the RELOC section.. (S=\'s\')')
        nb_err, self._nb_got_entries = self._build_rel_section()
        logger.debug('')
        if nb_err:
            self._log_reloc_objects(logger.debug)
            logger.debug('')
            self._log_reloc_objects(logger.error, True)
            logger.debug('<- KO')
            msg_ = f'Unsupported RELOC objects ({nb_err})'
            raise RelocElfProcessError(msg_)
        else:
            self._log_reloc_objects(logger.debug)

        logger.debug('')
        logger.debug('<- done - %s', str(self))

    def _update_mempool_offsets(self) -> None:
        """Update the offset in mempool descriptors"""

        self._logger.debug(' updating mempool desc offsets..')
        self._sec_data['data'] = bytearray(self._sec_data['data'])
        val_ = self._symbols['_params_desc']['value']
        cd_off_ = _get_offset(val_)
        addr_name_ = struct.unpack_from("<I", self._sec_data['data'], cd_off_)[0]
        while addr_name_ != 0:
            cd_off_ += 4
            flags_ = struct.unpack_from("<I", self._sec_data['data'], cd_off_)[0]
            cd_off_ += 4
            foff_ = struct.unpack_from("<I", self._sec_data['data'], cd_off_)[0]
            mpd_ = MPoolCDesc('')
            mpd_.set_raw_flags(flags_)
            if mpd_.get_type == MPoolCType.COPY:
                struct.pack_into("<I", self._sec_data['data'],
                                 cd_off_, foff_ + self._sec_param0['size'])
            cd_off_ += 8  # dst_, size_
            cd_off_ += 4  # next entry
            addr_name_ = struct.unpack_from("<I", self._sec_data['data'], cd_off_)[0]

    def build(self, split: bool = False):
        """Build the binary image"""

        params_ = bytearray()
        align_ = 8  # 8-bytes

        self._logger.debug('')
        self._logger.debug('-> Building the binary image..')
        self._logger.debug('used alignment: %s bytes', align_)
        msg_ = f'size of flash/p0/data/p1/rel/p2 sections: {len(self._sec_flash["data"])}/'\
               f'{len(self._sec_data["data"])}/-/{len(self._rel_sect)}/-'
        self._logger.debug(msg_)
        size_ = len(self._sec_flash["data"])
        msg_ = f'flash section is aligned: {align_up(size_, align_) == size_}'
        self._logger.debug(msg_)
        size_ = len(self._sec_data["data"])
        msg_ = f'data section is aligned: {align_up(size_, align_) == size_}'
        self._logger.debug(msg_)

        self._split = bool(split)
        if self._paramspath and not split:
            with open(self._paramspath, mode='rb') as read_file:
                params_ = bytearray(read_file.read())
                read_file.close()
            msg_ = f'raw params file: \'{self._paramspath}\' (s={len(params_)})'
            self._logger.debug(msg_)
        else:
            self._logger.debug('no raw params file (split=%s)', split)

        data_data = _get_offset(self._bin_header['data_data'])
        diff_ = data_data - len(self._sec_flash["data"])
        msg_ = f'data_data = {data_data}, {len(self._sec_flash["data"])} -> {diff_}'
        if diff_:
            self._logger.warning(msg_)

        if diff_ < 0:
            msg_ = f'Alignment issue - data_data off and len(flash) diff={diff_}'
            raise RelocPostProcessError(msg_)

        pad_f = bytearray(diff_)
        self._logger.debug('p0: %s', len(pad_f))

        bin_init_size = len(self._sec_flash['data']) + len(self._sec_data['data']) + diff_

        pad_0 = bytearray(align_up(bin_init_size, align_) - bin_init_size)
        self._logger.debug('p1: %s', len(pad_0))

        off_rel_start_n = bin_init_size + len(pad_0)
        if align_up(off_rel_start_n, align_) != off_rel_start_n:
            msg_ = f'Alignment issue - bin flash+data+pad {off_rel_start_n}'
            raise RelocPostProcessError(msg_)

        pad_1 = bytearray(align_up(len(self._rel_sect), align_) - len(self._rel_sect))
        self._logger.debug('p2: %s', len(pad_1))

        img_ = self._sec_flash['data'] + pad_f + self._sec_data['data'] + pad_0 + self._rel_sect + pad_1
        params_off_ = len(img_) if len(params_) else 0
        if not split:
            img_ += self._sec_param0['data']
            img_ += params_

        msg_ = f'params offset: {params_off_} (total binary size={len(img_)})'
        self._logger.debug(msg_)

        dec_ = off_rel_start_n - _get_offset(self._bin_header['rel_start'])

        self._logger.debug('updating the RelocBinaryImage object')
        self._image = img_
        self._bin_header = RelocBinaryImage(self._image)

        msg_ = f'updating \'rel_start\' entry: +{dec_}'
        self._logger.debug(msg_)
        msg_ = f'updating \'params_offset\' entry: {params_off_:08x} ({params_off_})'
        self._logger.debug(msg_)

        self._bin_header['rel_start'] = self._bin_header['rel_start'] + dec_
        self._bin_header['rel_end'] = self._bin_header['rel_start'] + len(self._rel_sect)
        self._bin_header['params_offset'] = params_off_

        def decode_sym_(addr: int) -> str:
            """."""
            sym_desc_ = self._get_symbol(addr)
            if sym_desc_ is not None:
                return sym_desc_['name']
            else:
                return '<symbol not found>'
            # return self._get_symbol(addr)['name']

        self._bin_header.summary(self._logger.debug, decode_sym_)
        self._logger.debug('<- done')
        self._logger.debug('')

    def save(self, binary_path: Optional[Union[str, Path]] = None) -> List[Path]:
        """Save the binary image"""

        c_name = self._filepath.stem
        if binary_path is None:
            binary_path = self._filepath.parents[0].joinpath(f'{c_name}_rel.bin')
        elif os.path.isdir(binary_path):
            binary_path = Path(binary_path).joinpath(f'{c_name}_rel.bin')
        # out_dir = self._filepath.parents[0]

        binary_path = Path(binary_path)
        stem_ = binary_path.stem
        suff_ = binary_path.suffixes
        parent_ = binary_path.parent
        binary_params_path = parent_.joinpath(f"{stem_}_params{''.join(suff_)}")

        self._logger.debug('')
        self._logger.debug('-> Creating \'%s\'', binary_path)

        with open(binary_path, "wb") as _f:
            _f.write(self._bin_header.data())
            _f.close()

        file_stats = os.stat(binary_path)
        msg_ = f'File size in Bytes is {file_stats.st_size}'
        self._logger.debug(msg_)

        self._logger.debug('<- done')
        self._logger.debug('')

        if self._split and self._paramspath:
            if self._sec_param0['data']:
                with open(self._paramspath, mode='rb') as read_file:
                    params_ = bytearray(read_file.read())
                    read_file.close()
                full_params = self._sec_param0['data'] + params_
                binary_params_path.write_bytes(full_params)
            else:
                binary_params_path.write_bytes(Path(self._paramspath).read_bytes())
            return [Path(binary_path), Path(binary_params_path)]

        return [Path(binary_path)]

    def to_c(self, dst_path: Optional[Union[str, Path]] = None) -> List[Path]:
        """Create the c-files"""

        c_name = self._filepath.stem
        f_ext = 'AA'
        if dst_path is None:
            c_path = self._filepath.parents[0].joinpath(f'{c_name}_rel.c')
            h_path = self._filepath.parents[0].joinpath(f'{c_name}_rel.h')
        elif os.path.isdir(dst_path):
            c_path = Path(dst_path).joinpath(f'{c_name}_rel.c')
            h_path = Path(dst_path).joinpath(f'{c_name}_rel.h')
        else:
            f_name = Path(dst_path).stem
            f_ext = Path(dst_path).suffix
            if f_ext != '.c':
                raise RelocElfProcessError(f'Invalid suffix: \'{dst_path}\', expected \'.c\'')
            c_path = Path(dst_path)
            h_path = Path(dst_path).parents[0].joinpath(f'{f_name}.h')

        self._logger.debug('')
        self._logger.debug('-> Creating \'%s\', \'%s\'', c_path, h_path)

        xip_size_ = align_up(self._bin_header.RW_size())
        copy_size_ = align_up(xip_size_ + self._bin_header.RO_size())

        mempc_descs_ = self._bin_header.unpack_mempool_c_descriptors()
        rt_context_ = self._bin_header.unpack_rt_context()

        # generate header file
        with open(h_path, 'w') as _f:
            _f.write('/* Generated file - SHOULD-BE NOT MODIFIED */\n\n')
            _f.write('#ifndef __{}_RELOC_H__\n'.format(c_name.upper()))
            _f.write('#define __{}_RELOC_H__\n\n'.format(c_name.upper()))
            _f.write('#include <stdint.h>\n\n')
            _f.write('#define AI_{}_RELOC_C_NAME            "{}"\n'.format(c_name.upper(), rt_context_['c_name']))
            _f.write('#define AI_{}_RELOC_RT_DESC           "{}"\n\n'.format(c_name.upper(),
                                                                             rt_context_['rt_version_desc']))
            _f.write('#define AI_{}_RELOC_RAM_SIZE_XIP      ({})\n'.format(c_name.upper(), xip_size_))
            _f.write('#define AI_{}_RELOC_RAM_SIZE_COPY     ({})\n\n'.format(c_name.upper(), copy_size_))
            _f.write('#define AI_{}_RELOC_IMAGE_SIZE        ({})\n\n'.format(c_name.upper(),
                                                                             self._bin_header.IMG_size()))
            _f.write('#define AI_{}_RELOC_ACTIVATIONS_SIZE  ({})\n'.format(c_name.upper(), rt_context_['acts_sz']))
            _f.write('#define AI_{}_RELOC_WEIGHTS_SIZE      ({})\n'.format(c_name.upper(), rt_context_['params_sz']))
            _f.write('#define AI_{}_RELOC_EXT_RAM_SIZE      ({})\n\n'.format(c_name.upper(), rt_context_['ext_ram_sz']))

            for idx, mempc_desc_ in enumerate(mempc_descs_):
                flags_val_ = mempc_desc_["flags_raw"]
                flags_desc_ = mempc_desc_["flags_desc"]
                if flags_val_:
                    _f.write('#define AI_{}_RELOC_MPOOL_DESC_{}_NAME   "{}"\n'.format(c_name.upper(),
                                                                                      idx, mempc_desc_["name"]))
                    _f.write('#define AI_{}_RELOC_MPOOL_DESC_{}_FLAGS  ({}) /* {} */\n'.format(c_name.upper(),
                                                                                               idx, flags_val_,
                                                                                               flags_desc_))
                    _f.write('#define AI_{}_RELOC_MPOOL_DESC_{}_FOFF   ({})\n'.format(c_name.upper(),
                                                                                      idx, mempc_desc_["foff"]))
                    _f.write('#define AI_{}_RELOC_MPOOL_DESC_{}_DST    ({})\n'.format(c_name.upper(),
                                                                                      idx, mempc_desc_["dst"]))
                    _f.write('#define AI_{}_RELOC_MPOOL_DESC_{}_SIZE   ({})\n\n'.format(c_name.upper(),
                                                                                        idx, mempc_desc_["size"]))

            _f.write('uintptr_t ai_{}_reloc_img_get(void);\n\n'.format(c_name))
            _f.write('#endif /* __{}_RELOC_H__ */\n'.format(c_name.upper()))
            _f.close()

        # generate C file
        align_def = dedent("""

            #if defined(__ICCARM__) || defined (__IAR_SYSTEMS_ICC__)
                #define _ALIGNED(x)         __ALIGNED_X(x)
                #define __ALIGNED_XY(x, y)  x ## y
                #define __ALIGNED_X(x)      __ALIGNED_XY(__ALIGNED_,x)
                #define __ALIGNED_1         _Pragma("data_alignment = 1")
                #define __ALIGNED_2         _Pragma("data_alignment = 2")
                #define __ALIGNED_4         _Pragma("data_alignment = 4")
                #define __ALIGNED_8         _Pragma("data_alignment = 8")
            #elif defined(__CC_ARM)
                #define _ALIGNED(x)         __attribute__((aligned (x)))
            #elif defined(__GNUC__)
                #define _ALIGNED(x)         __attribute__((aligned(x)))
            #endif

            """)

        nb_w = self._bin_header.IMG_size()
        img = self._bin_header.data()
        indent = 4
        C_BYTE_BY_LINE = 16
        pos = 0
        with open(c_path, 'w') as _f:
            _f.write('/* Generated file - SHOULD-BE NOT MODIFIED */\n\n')
            _f.write('#include <stdint.h>\n')
            _f.writelines(align_def)
            _f.write('uintptr_t ai_{}_reloc_img_get(void)\n{}\n'.format(c_name, '{'))
            _f.write(' _ALIGNED(8)\n')
            _f.write(' static const uint8_t s_{}_reloc_img[{}] = {}\n'.format(c_name, len(img), '{'))
            while nb_w:
                c_nb_w = min(C_BYTE_BY_LINE, nb_w)
                arr_w = img[pos:pos + c_nb_w]
                nb_w -= c_nb_w
                pos += C_BYTE_BY_LINE

                l_val = ['0x{:02x}'.format(b) for b in arr_w]
                l_str = ' ' * indent + ', '.join(l_val)
                if nb_w:
                    l_str += ','
                l_str += '\n'
                _f.write(l_str)
            _f.write(' {}\n\n'.format('};'))
            _f.write('  return (uintptr_t)(s_{}_reloc_img);\n\n'.format(c_name))
            _f.write('{}\n'.format('};'))
            _f.close()

        self._logger.debug('<- done')
        self._logger.debug('')

        return [c_path, h_path]

    def check(self):
        """Check the binary file"""

        self._logger.debug('')
        self._logger.debug('-> Checking binary image')

        self._bin_header.check()
        self._bin_header.summary(self._logger.debug)

        self._logger.debug('<- done')
        self._logger.debug('')

    def _build_skipped_addresses(self):
        """."""
        self._logger.debug('')
        self._logger.debug('Computing the skipped addresses..')

        val_ = self._symbols['_network_entries']['value']
        nb_entries = int(self._symbols['_network_entries']['size'] / 4)
        msg_ = f' from \'_network_entries\' structure - base@={val_:08x} ({nb_entries} items)'
        self._logger.debug(msg_)
        for v in range(nb_entries):
            self._skipped_addrs.append(val_)
            val_ += 4
        val_ = self._symbols['_params_desc']['value']
        nb_entries = int(self._symbols['_params_desc']['size'] / 4)
        for v in range(nb_entries):
            # self._skipped_addrs.append(val_)
            val_ += 4

        msg_ = ' ' + str([f'{v:08x}' for v in self._skipped_addrs])
        self._logger.debug(msg_)

    def _get_symbol(self, sym: Union[str, int]):
        """Return the associated symbol desc. based on the name or the @"""
        sym_desc_ = None
        if isinstance(sym, int):
            for sym_ in self._symbols.values():
                if sym_["value"] == sym:
                    sym_desc_ = sym_
        else:
            sym_desc_ = self._symbols.get(sym, None)
        return sym_desc_

    def _dump_symbol(self, sym: Union[str, int]):
        """Display/log info from a given symbol"""

        sym_desc_ = self._get_symbol(sym)
        if sym_desc_ is None and isinstance(sym, int):
            desc_ = f'{sym:8x}'
        if sym_desc_:
            sec_name_ = ''
            if isinstance(sym_desc_['section'], int):
                sec_ = [f for f in self._sections.values() if f["idx"] == sym_desc_['section']]
                sec_name_ = sec_[0]['name']
            desc_ = f'{sym_desc_["value"]:08x} {sym_desc_["size"]:3d} {sym_desc_["type"]:8s} {sec_name_:10s}'
            desc_ += f' {sym_desc_["name"]:50s}'
        else:
            desc_ += ' NOT FOUND'
        self._logger.info(desc_)

    def _in_section(self, addr, sec):
        """."""
        if sec not in self._sections.values():
            msg_ = f'Provided section is not registered {sec["name"]}'
            raise ValueError(msg_)
        return addr >= sec['addr'] and (addr + 4) <= (sec['addr'] + sec['size'])

    def _build_rel_section(self):
        """."""
        self._rel_sect = bytearray()
        nb_err_ = 0
        got_offsets_ = []
        allow_ro_write = False
        supported_rel_type = _SUPPORTED_REL_TYPE
        if self._clang_mode:
            supported_rel_type += _SUPPORTED_CLANG_REL_TYPE
            allow_ro_write = True
        for reloc in self._reloc:
            if reloc['name'].startswith('.debug_'):
                reloc['status'] = 'D'
                continue
            err_msg_ = f'{reloc["offset"]:08x}/{reloc["type"]}:'
            if reloc['type'] not in supported_rel_type:
                reloc['status'] = 'E'
                reloc['extra'] = f'{err_msg_} Unsupported RELOC type'
                nb_err_ += 1
                continue
            if reloc['value'] == 0:
                reloc['status'] = 'E'
                reloc['extra'] = f'{err_msg_} Unresolved SYMBOL'
                nb_err_ += 1
                continue
            if reloc["offset"] in self._skipped_addrs:
                val_ = self.get_u32_value(reloc["offset"])
                reloc['status'] = 's'
                reloc['value'] = val_
            elif reloc['type'] == 'R_ARM_GOT_BREL' or reloc['type'] == 'R_ARM_GOT32':
                offset_ = self.get_u32_value(reloc["offset"])
                reloc['status'] = 'g'
                reloc['extra'] = f'/ off={offset_:08x}'
                if offset_ not in got_offsets_:
                    got_offsets_.append(offset_)
            elif self._clang_mode and reloc['type'] in _SUPPORTED_CLANG_REL_TYPE:
                offset_ = self.get_u32_value(reloc["offset"])
                reloc['status'] = 'g'
                if 'PREL' in reloc['type']:
                    reloc['extra'] = ' CLANG - PC-relatif'
                else:
                    reloc['extra'] = ' CLANG - R9-based '
            elif reloc['type'] == 'R_ARM_ABS32':
                if allow_ro_write or self._in_section(reloc["offset"], self._sec_data):
                    val_ = self.get_u32_value(reloc["offset"])
                    reloc['status'] = 'r'
                    reloc['value'] = val_
                    self._rel_sect += struct.pack("<I", reloc["offset"])
                else:
                    reloc['status'] = 'E'
                    reloc['extra'] = f'{err_msg_} Invalid offset (not from RAM)'
                    nb_err_ += 1
            else:
                reloc['status'] = '-'
        return nb_err_, len(got_offsets_)

    def _sanity_check(self):
        """Check the contents of the elf file"""

        # requested elf sections: name, type and mapping
        sec_no_found = []
        for req_sec in _REQUESTED_ELF_SECTIONS:
            if req_sec not in self._sections.keys():
                sec_no_found.append(req_sec)
        if sec_no_found:
            msg_ = f'Invalid elf file - {sec_no_found} section(s) not found'
            raise ValueError(msg_)

        for _, sec in self._sections.items():
            if sec['name'].startswith('.rel.') or sec['name'] == '.relocs':
                if sec['type'] != 'REL' and sec['size'] != 0:
                    msg_ = f'SANITY CHECK: "{sec["name"]}", Invalid section type - {sec["type"]} instead REL'
                    raise ValueError(msg_)
            if not sec['addr']:
                continue
            seg_ = _get_vseg_desc(sec['addr'])
            if sec['name'] not in seg_['sec_names']:
                msg_ = f'SANITY CHECK: "{sec["name"]}", Invalid section def.'
                msg_ += f' - {seg_["sec_names"]} {sec["name"]}/{sec["addr"]:08x}'
                raise ValueError(msg_)

        # requested symbols
        sym_no_found = []
        for req_sym in _REQUESTED_SYMBOLS:
            if req_sym not in self._symbols:
                sym_no_found.append(req_sym)
        if sym_no_found:
            msg_ = f'Invalid elf file - {sym_no_found} symbol(s) not found'
            raise ValueError(msg_)

    def get_u32_value(self, offset: int) -> int:
        """Return the contents of the data"""

        for _, sec_ in self._sections.items():
            if offset >= sec_['addr'] and (offset + 4) <= (sec_['addr'] + sec_['size']):
                offset = offset - sec_['addr']
                return struct.unpack_from("<I", sec_['data'], offset)[0]

        msg_ = f'Invalid offset - {offset:08x}'
        raise ValueError(msg_)

    def _log_sections(self, print_fn):
        """Display/log the sections"""

        rows_ = []
        for sect in self._sections.values():
            row_ = [f'{sect["idx"]:d}', f'{sect["name"]:s}', f'{sect["addr"]:08x}']
            row_ += [f'{sect["offset"]:8d}', f'{sect["size"]:8d}', f'{sect["align"]:4d}', f'{sect["type"]:14s}']
            rows_.append(row_)

        header_ = ['Idx', 'Name', 'Addr', 'Off', 'Size', 'Al', 'Type']
        nb_sym_ = f'number of symbol/reloc : {len(self._symbols)} / {len(self._reloc)}'
        title_ = f'Elf sections ({len(self._sections)}) - {nb_sym_}'
        print_table(header_, rows_, print_fn, title=title_)

    def _log_reloc_objects(self, print_fn, err_only: bool = False):
        """Display/log the relocatable objects"""

        rows_ = []
        nb_reloc = 0
        nb_reloc_debug = 0
        for reloc in self._reloc:
            if reloc["status"] == 'D':
                nb_reloc_debug += 1
                continue
            if err_only and reloc["status"] != 'E':
                continue
            if reloc["status"] == 'r':
                nb_reloc += 1
            row_ = [f'{reloc["offset"]:08x}', f'{reloc["info"]:08x}', f'{reloc["type"]:16s}', f'{reloc["status"]:1s}']
            row_ += [f'{reloc["value"]:8x}', f'{reloc["sym_type"]:8s}', f'{reloc["vseg"]:14s}', f'{reloc["name"]}']
            row_ += [f' {reloc["extra"]}']
            rows_.append(row_)

        header_ = ['Offset', 'Info', 'Type', 'S', 'Value', 'SymType', 'VirtSeg', 'Name', '']
        title_ = f'Reloc objects - {nb_reloc} reloc objects / {nb_reloc * 4} bytes {nb_reloc_debug}'
        print_table(header_, rows_, print_fn, title=title_, tablefmt='simple')

    def log_ec_blobs(self):
        """Report size of the ec blob"""

        if not self._ec_blobs:
            return

        rows_ = []
        bss_, ro_data_ = 0, 0
        for key, value in self._ec_blobs.items():
            bss_ += value[0]
            ro_data_ += value[2]
            reloc_ = f'r:{value[4]}' if value[4] else ''
            row_ = [key, f'{value[0]:,}' if value[0] else '', f'{value[2]:,}', reloc_]
            rows_.append(row_)

        rows_.append([])
        rows_.append(['total', f'{bss_:,}', f'{ro_data_:,}', ''])

        self._logger.info('')
        header_ = ['Name', 'bss', 'ro data', 'reloc']
        title_ = f'EC blob objects ({len(self._ec_blobs)})'
        print_table(header_, rows_, self._logger.info, title=title_)

    def summary(self, logger: Optional[Union[str, logging.Logger, Any]] = None, full: bool = False):
        """."""

        def decode_sym_(addr: int) -> str:
            """."""
            return self._get_symbol(addr)['name']

        pr_fn, pr_debug_fn = get_print_fcts(self._logger, logger, full)

        if pr_debug_fn:
            pr_debug_fn('')
            self._log_sections(pr_debug_fn)
        pr_fn('')
        self._bin_header.summary(pr_fn, decode_sym_,
                                 data=self._sec_data['data'])

    def __str__(self):
        """."""
        nb_rel = f'{int(len(self._rel_sect) / 4)} ({len(self._rel_sect)} bytes)'
        nb_got = f'{int(self._nb_got_entries)} ({self._nb_got_entries * 4} bytes)'

        msg_ = f'ElfPostProcess: rel:{nb_rel}, got:{nb_got}'
        return msg_


def read_binary_file(params: Params, no_banner: bool = False) -> int:
    """Entry to read and check the binary file (runtime loadable model)"""

    logger = logging.getLogger()

    if not no_banner:
        logger.info('%s (version %s)', __title__, __version__)
        logger.info('Creating date : %s', datetime.now().ctime())
        logger.info('')

    logger.info('Input file     : %s', params.input)

    reloc_bin_ = RelocBinaryImage(params.input, logger=logger)  # type: ignore
    reloc_bin_.check()
    logger.info('')

    if params.report != 'no-report':
        logger.info('Generating report file: %s', params.report)
        with open(params.report, 'w', encoding='utf-8') as report_file:
            def pr_fn_(msg: str) -> None:
                """."""
                report_file.write(' ' + msg + '\n')
            pr_fn_('')
            reloc_bin_.summary(pr_fn=pr_fn_, short_desc=True)
        logger.info('')

    reloc_bin_.summary(pr_fn=logger.info)

    return 0


def main():
    """Main function to parse the arguments"""  # noqa: DAR101,DAR201,DAR401

    parser = argparse.ArgumentParser(description=f'{__title__} v{__version__}')

    parser.add_argument('--input', '-i', metavar='STR', type=str,
                        help='location of the relocatable binary model (.bin file)',
                        default=_DEFAULT_INPUT)

    parser.add_argument('--report', '-r', type=str, nargs='?',
                        const='report.txt',
                        help=argparse.SUPPRESS,
                        default='no-report')

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
        read_binary_file(params)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(e, stack_info=False, exc_info=params.debug)
        return -1

    return 0


if __name__ == '__main__':
    sys.exit(main())
