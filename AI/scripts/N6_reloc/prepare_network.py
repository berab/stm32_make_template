###################################################################################
#   Copyright (c) 2024 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
NPU Utility functions - prepare the network.c for relocatable mode
"""

import logging
import argparse
import os
from random import sample
import sys
import glob
import zlib
import re
from textwrap import dedent, indent
from datetime import datetime
from string import Template
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from c_network_parser import CNpuNetworkDesc
from reloc_misc import MPoolCDesc, MPoolCType, align_up
from exceptions import BaseExceptionError, RelocPrepareError
from misc import size_int_to_str
from misc import Params, create_logger
from target import DevicePropertyDesc


#
# History
#   v0.0 - initial version (based on stai core implementation)
#   v0.1 - add generation of C-descriptors
#   v0.2 - fix case where 0-initializer is not provided
#   v1.0 - add support for clang tool-chain
#   v1.1 - add support to place the ecblob with param
#

__title__ = 'NPU Utility - Preparing/checking the generated C-files for relocatable mode'
__version__ = '1.1'
__author__ = 'STMicroelectronics'


_DEFAULT_INPUT = './st_ai_output'
_DEFAULT_BUILD_DIR = 'build'
_FAKE_SIZE = 32


def _patch_npu_mcu_caches(lines: List[str], c_labels: List[str]) -> int:
    """Patch the call of NPU/MCU cache operations related to c-labels"""

    logger = logging.getLogger()
    nb_patches = 0

    if not c_labels:
        logger.info('  no patch related to LL_ATON_Cache.')
        return 0

    for idx, line in enumerate(lines):
        if 'LL_ATON_Cache_' not in line:
            continue
        for c_label in c_labels:
            if c_label in line:
                nb_patches += 1
                lines[idx] = line.replace('LL_ATON_Cache_',
                                          'RELOC_LL_ATON_Cache_', 1)
    logger.info('  %s \'LL_ATON_Cache\' occurences patched.', nb_patches)

    if nb_patches:  # include macro definitions
        ins_idx = 0
        for idx, line in enumerate(lines):
            if line.strip().startswith('#include '):
                ins_idx = idx
            if ins_idx and not line.strip():
                lines.insert(ins_idx + 1, '#include "ll_reloc_cache_wrapper.h"\n')
                break

    return nb_patches


def _patch_ecblob_to_params(lines: List[str], c_name: str) -> int:
    """Patch - create indirection for const ecblobs"""

    logger = logging.getLogger()

    if not lines:
        logger.info('  no patch related to Epoch Controller (ECBLOB to PARAMS).')
        return 0

    # Retreive the const ec_blobs (and prepare the next steps)
    ec_blob_entries_: List[Tuple[str, str]] = []
    ec_blob_ptr_entries_: List[str] = []
    offset_ = 3
    # ex line: "static const uint64_t _ec_blob_network_1[11608] ="
    #          "static uint64_t _ec_blob_network_1_ptr[3592];"
    pattern = r"static\s+const\s+(\w+)\s+_ec_blob_(\w+)_(\d+)\[(\d+)\]\s*="
    pattern_ptr = r"static\s+(\w+)\s+_ec_blob_(\w+)_(\d+)_ptr\[(\d+)\];"
    for idx_, line in enumerate(lines):
        if not line.strip().startswith('ECBLOB_CONST_SECTION') and not line.strip().startswith('ECBLOB_RUNTIME_SECTION'):
            continue
        c_line = lines[idx_ + offset_].strip()
        match = re.match(pattern, c_line)
        match_ptr = re.match(pattern_ptr, c_line)
        if match:
            c_type_ = match.group(1)
            c_name_ = match.group(2)
            c_id_ = match.group(3)
            c_size_ = match.group(4)
            if not c_name_.endswith(f'{c_name}'):
                logger.error('  unexpected ec_blob name: %s', c_name_)
                raise RelocPrepareError('Unexpected ec_blob name')
            if c_type_ != 'uint64_t':
                logger.error('  unexpected ec_blob type: %s', c_type_)
                raise RelocPrepareError('Unexpected ec_blob type')
            if not c_size_.isnumeric() or int(c_size_) == 0:
                logger.error('  unexpected ec_blob size: %s', c_size_)
                raise RelocPrepareError('Unexpected ec_blob size')
        elif match_ptr:
            c_type_ = match_ptr.group(1)
            c_name_ = match_ptr.group(2)
            c_id_ = match_ptr.group(3)
            c_size_ = match_ptr.group(4)
        else:
            msg_ = 'unexpected ec_blob definition:\n'
            msg_ += f'    line {idx_ + offset_ + 1}: "{lines[idx_ + offset_]}"'
            raise RelocPrepareError(msg_)

        if match:
            ec_blob_org_ = lines[idx_ + offset_].strip().split()[-2]
            ec_blob_org_ = f'_ec_blob_{c_name}_{c_id_}'
            # print("*** ", ec_blob_org_)
            # ec_blob_org_ = ec_blob_org_.replace('[]', '')
            ec_blob_new_ = ec_blob_org_.replace(f'_ec_blob_{c_name}', f'_ec_blob_PARAM_{c_name}')
            ec_blob_entries_.append((ec_blob_org_, ec_blob_new_))
            lines[idx_ + offset_] = f'const uint64_t {ec_blob_new_}[{c_size_}] =\n'
            # print("*** ", ec_blob_entries_[-1])
        elif match_ptr:
            ec_blob_ptr_entries_.append(f'_ec_blob_{c_name}_{c_id_}')
            # print("*** ", ec_blob_ptr_entries_[-1], '_ptr')

    logger.info('  %s \'const ecblob\' found.', len(ec_blob_entries_))

    if ec_blob_entries_:
        class InsertLinesMgr():
            """Helper class to insert lines"""

            def __init__(self, lines: List[str], cpos: int):
                """Constructor"""
                self._lines = lines
                self._cpos = cpos

            def insert(self, line: str = ''):
                """Insert line + add LF"""
                self._lines.insert(self._cpos, line + '\n')
                self._cpos += 1

        for idx, line in enumerate(lines):
            if line.strip().startswith('ECBLOB_CONST_SECTION'):
                lines_mgr = InsertLinesMgr(lines, idx)
                lines_mgr.insert()
                lines_mgr.insert('/* BEGIN - PATCH - EC BLOB IN PARAMS */')
                lines_mgr.insert()
                for ec_blob_entry in ec_blob_entries_:
                    ext_line_ = f'extern const uint64_t {ec_blob_entry[1]}[]; /* {ec_blob_entry[0]} */'
                    lines_mgr.insert(f'{ext_line_}')
                lines_mgr.insert()
                lines_mgr.insert('const uint64_t* _ec_blob_table[] = {')
                for ec_blob_entry in ec_blob_entries_:
                    ext_line_ = f' &{ec_blob_entry[1]}[0],'
                    lines_mgr.insert(f'{ext_line_}')
                lines_mgr.insert('};')
                lines_mgr.insert()
                for inc_, ec_blob_entry in enumerate(ec_blob_entries_):
                    # if not ec_blob_entry[0].split('_')[-1].isnumeric():
                    if ec_blob_entry[0] in ec_blob_ptr_entries_:
                        ext_line_ = f'#define {ec_blob_entry[0]} _ec_blob_table[{inc_}]'
                    else:
                        ext_line_ = f'#define {ec_blob_entry[0]} {ec_blob_entry[1]}'
                    lines_mgr.insert(f'{ext_line_}')
                lines_mgr.insert()
                lines_mgr.insert('/* END - PATCH - EC BLOB IN PARAMS */')
                lines_mgr.insert()
                break

    return len(ec_blob_entries_)


def _patch_epoch_mgr(lines: List[str], c_labels: List[str]) -> int:
    """Patch the call of ec_reloc related to c-labels"""

    logger = logging.getLogger()
    nb_refs = 0

    if not c_labels or not lines:
        logger.info('  no patch related to Epoch Controller (RELOC ECBLOB).')
        return 0

    defines_: List[str] = []
    for line in lines:
        for c_label_ in c_labels:
            if not line.strip().startswith('#define '):
                continue
            if c_label_ in line:
                defines_.append(line.strip().split(' ')[1])
                nb_refs += 1

    logger.info('  %s \'ec_reloc\' occurences patched.', nb_refs)

    patches_: List[Tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if line.strip().startswith('#define '):
            continue
        for define_ in defines_:
            if define_ in line and 'ec_reloc(' in line:
                n_line = line.replace('if (!ec_reloc', 'EC_RELOC', 1)
                n_line = n_line.replace('))', ');', 1)
                patches_.append((idx, n_line))
    inc_ = 0
    for patch_ in patches_:
        logger.debug('  %s ', patch_)
        lines.insert(patch_[0] + inc_, patch_[1])
        c_idx_ = patch_[0] + inc_
        cont = 1
        while cont:
            lines[c_idx_ + cont] = '// ' + lines[c_idx_ + cont]
            cont += 1
            if lines[c_idx_ + cont - 1].strip().endswith('}'):
                cont = 0
        inc_ += 1

    EC_RELOC_code = dedent("""
        /* BEGIN - EC_RELOC wrapper - clang fix */

        struct ec_reloc_param {
            const ECFileEntry *reloc_table_ptr;
            ECInstr *program;
            unsigned int idx;
            ECAddr base;
            ECAddr *prev_base;
        };

        [[clang::optnone]]
        bool _ec_reloc(struct ec_reloc_param *params) {
            return ec_reloc(params->reloc_table_ptr, params->program,
                            params->idx, params->base, params->prev_base);
        }

        #define EC_RELOC(rtable_, prog_, idx_, base_, pbase_) \\
        { \\
            static struct ec_reloc_param param = {.base = (base_)}; \\
            param.reloc_table_ptr = (rtable_); param.program = (prog_); \\
            param.idx = (idx_); param.prev_base = (pbase_); \\
            if (!_ec_reloc(&param)) \\
                return false; \\
        }
        /* END - EC_RELOC wrapper */

        """)

    if patches_:  # include macro definitions
        for idx, line in enumerate(lines):
            if line.strip().startswith('ECBLOB_CONST_SECTION'):
                for inc, c_line in enumerate(EC_RELOC_code.splitlines()):
                    lines.insert(idx + inc, c_line + '\n')
                break

    return len(patches_)


def prepare_c_network_file(args: Params, results: Optional[Dict[str, Any]] = None,
                           no_banner: bool = False):
    """Entry point to prepare the c-files"""

    logger = logging.getLogger()

    clang_mode = bool(args.st_clang) or bool(args.llvm)

    if not no_banner:
        logger.info('%s (version %s)', __title__, __version__)
        logger.info('Creating date : %s', datetime.now().ctime())
        logger.info('')

    logger.info('Entry point : \'%s\' (name=\'%s\')', args.input, args.name)
    logger.info('clang mode  : %s', clang_mode)

    # check info from generated file
    c_npu_network = CNpuNetworkDesc(args.input, logger,
                                    f_name=args.name,
                                    target=args.target,
                                    mem_only=not args.parse_only)
    args.input = c_npu_network.filepath
    f_name_ = c_npu_network.f_name
    c_name_ = c_npu_network.c_name
    c_npu_network.summary(full=args.verbosity > 1)

    if results is not None:
        results['versions'].update({ 'prepare_c_file': __version__})
        results.update(c_npu_network.to_dict())

    mempools = c_npu_network.mpools
    c_lines = c_npu_network.lines

    # retrieve initializer files (*.<postfix>.raw files)
    head, tail = os.path.split(args.input)
    logger.info('')
    logger.info('Preparing the C-descriptors for mempools..')
    logger.info(' checking the memory initializers from \'%s\' folder..', head)
    logger.info('')

    dev_desc_: DevicePropertyDesc = DevicePropertyDesc(args.target)
    raw_files = glob.glob(os.path.join(head, f'{c_name_}*.raw'))
    if c_name_ == 'Default' and not raw_files:
        raw_files = glob.glob(os.path.join(head, 'network*.raw'))

    # complete the list with the used mempool w/o raw initializers
    raw_0_files = []
    used_postfixs_ = [mp_.postfix for mp_ in mempools if mp_.used_size]
    for postfix in used_postfixs_:
        found_file_: bool = False
        for file in raw_files:
            _, tail = os.path.split(file)
            if tail.endswith(f'{postfix}.raw'):
                found_file_ = True
                break
        if not found_file_:
            raw_0_files.append(f'ZERO_MPOOL.{postfix}.raw')
    raw_files += raw_0_files

    _id_relative_ext_ro_rw = [
        MPoolCDesc.BASE_PARAM_RELOC_ID,
        MPoolCDesc.BASE_PARAM_RELOC_ID + 1
    ]
    _id_relative_mempool: List[Optional[MPoolCDesc]] = [None, None]
    _offset = 0
    mpool_cdesc: List[MPoolCDesc] = []
    for mempool in mempools:
        found_mp_file: Optional[MPoolCDesc] = None
        # retreive the associated raw file
        if mempool.vpool:
            continue
        for file in raw_files:
            _, tail = os.path.split(file)
            if not mempool.postfix:
                logger.info(" no POSTFIX : %s", mempool)
            if tail.endswith(f'{mempool.postfix}.raw'):
                mp_desc = MPoolCDesc(mempool.postfix, mempool.c_label[0])
                mp_desc.set_flags(mempool.used(),
                                  mempool.is_relative,
                                  mempool.with_params,
                                  mempool.is_param_only,
                                  mempool.is_rw,
                                  mempool.is_cacheable)

                # set the RELOC ID
                if mempool.is_relative and not mempool.is_rw:
                    if _id_relative_mempool[0] is None:
                        mp_desc.set_id(_id_relative_ext_ro_rw[0])
                        _id_relative_mempool[0] = mp_desc
                    else:
                        msg_err = f'RO RELOC ID for \'{mempool.postfix}\' mempool already'
                        msg_err += f' assigned to: \n \'{_id_relative_mempool[0]}\'.'
                        raise RelocPrepareError(msg_err)
                elif mempool.is_relative and mempool.is_rw:
                    if _id_relative_mempool[1] is None:
                        mp_desc.set_id(_id_relative_ext_ro_rw[1])
                        _id_relative_mempool[1] = mp_desc
                    else:
                        msg_err = f'RW RELOC ID for \'{mempool.postfix}\' mempool already'
                        msg_err += f' assigned to: \n \'{_id_relative_mempool[1]}\'.'
                        raise RelocPrepareError(msg_err)

                mp_desc.set_dst_addr(mempool.offset)

                if file.startswith('ZERO_MPOOL'):
                    file_length_in_bytes = 0
                else:
                    file_length_in_bytes = os.path.getsize(file)
                logger.info(' found \'%s\' file for %s (fsize=%s, expected=%s)', tail,
                            mempool.postfix, file_length_in_bytes, mempool.used())

                if not file.startswith('ZERO_MPOOL'):
                    _offset = mp_desc.set_raw_file(file, _offset)
                logger.debug(' %s', str(mp_desc))
                found_mp_file = mp_desc
                break  # one RAW has been found

        # check that all mempool descriptors are covered (vpool is not considered)
        if found_mp_file is None:
            continue
        mpool_cdesc.append(found_mp_file)
        if mpool_cdesc[-1].name != mempool.postfix:
            logger.warning(' no raw file found for \'%s\' mempool', mempool.postfix)
            if mempool.size:
                logger.error('Memory file initializer (raw file) is requested')
                logger.error(' for %s', str(mempool))
                msg_err = f'NO memory file initilalizer for \'{mempool.postfix}\''
                if not args.cont:
                    raise RelocPrepareError(msg_err)

    logger.info('')
    reloc_issues_: List[str] = []
    c_labels: List[str] = []
    for mp_desc in mpool_cdesc:
        if not mp_desc.is_supported:
            logger.error('%s', mp_desc.err)
            msg_err = f'UNSUPPORTED mempool {mp_desc.name}'
            if not args.cont:
                raise RelocPrepareError(msg_err)
        logger.info(' %s', str(mp_desc))
        if mp_desc.c_label:
            c_labels.append(mp_desc.c_label)
            if mp_desc.dst and mp_desc.dst < dev_desc_.ext_base_address and mp_desc.size:
                reloc_issues_.append(f'USEMODE_RELATIVE property can be not used for \'{mp_desc.name}\' memory-pool')
        if mp_desc.c_label and mp_desc.get_type != MPoolCType.RELOC and mp_desc.size:
            reloc_issues_.append(f'USEMODE_RELATIVE property is requested for \'{mp_desc.name}\' memory-pool')

    if reloc_issues_:
        logger.info('')
        for msg_ in reloc_issues_:
            logger.error(msg_)
        raise RelocPrepareError('Invalid memory pool for external memory.')

    ext_ram_sz = 0
    if _id_relative_mempool[1] and _id_relative_mempool[1].size:
        mpool_ = _id_relative_mempool[1]
        ext_ram_sz = mpool_.size
        msg_ = f'Note: the external r/w memory region "{mpool_.name}" should be relocated (size={mpool_.size:,})'
        logger.info('')
        logger.info(msg_)

    if args.parse_only:
        return 0

    os.makedirs(args.output, exist_ok=True)

    if args.name == 'no-name':
        args.name = f_name_

    file_name = os.path.join(args.output, args.name)
    file_name_net = f'{file_name}_reloc' + '.c'
    file_name_mpools = f'{file_name}_reloc_mempools' + '.c'
    file_name_raw = f'{file_name}_reloc_mempools' + '.raw'
    file_name_conf = f'{file_name}_reloc_conf' + '.h'
    file_name_ecblobs = f'{file_name}_reloc_ecblobs' + '.h'
    ecblobs_lines: List[str] = []

    logger.info('')
    logger.info('Generating relocatable C-files..')

    if c_npu_network.compiler.epoch_ctrl:
        src_ecblobs_ = os.path.join(args.input.parent, f_name_ + '_ecblobs.h')
        if not os.path.isfile(src_ecblobs_):
            msg_err_ = f'\'{src_ecblobs_}\' is not a regular files'
            raise RelocPrepareError(msg_err_)
        with open(src_ecblobs_, encoding="utf-8") as fh_:
            ecblobs_lines = fh_.readlines()
            fh_.close()

    if args.ecblob_in_params:
        _patch_ecblob_to_params(ecblobs_lines, c_name_)

    if clang_mode:
        logger.info(' applying patches for clang..')
        _patch_npu_mcu_caches(c_lines, c_labels)
        _patch_epoch_mgr(ecblobs_lines, c_labels)

    if ecblobs_lines:
        logger.info(' creating %s', file_name_ecblobs)
        with open(file_name_ecblobs, mode="w", encoding="utf-8") as fh_:
            fh_.writelines(ecblobs_lines)
            fh_.close()
        # patch the network c-file
        for idx, line_ in enumerate(c_lines):
            if f'{f_name_}_ecblobs.h' in line_:
                c_lines[idx] = f'#include \"{args.name}_reloc_ecblobs.h\"\n'
                break

    tools_version_ = f'/* {__title__} v{__version__} */\n'
    tools_version_ += f'/* Created date - {datetime.now().ctime()} */\n\n'
    tools_version_ += f'/* File: {args.input} */\n\n'

    network_reloc_footer = dedent("""

        #if defined(BUILD_AI_NETWORK_RELOC)

        #include "ll_aton_reloc_network.h"

        AI_RELOC_NETWORK();

        #endif  /* BUILD_AI_NETWORK_RELOC */
        """)

    logger.info(' creating %s', file_name_net)

    with open(file_name_net, mode="w", encoding="utf-8") as fh_:
        fh_.writelines(c_lines)
        fh_.writelines(network_reloc_footer)
        fh_.close()

    network_reloc_mem_header = dedent(
        """\
        /* AUTOGENERATED DO NOT MODIFY */

        #include <stdint.h>

        #if defined(BUILD_AI_NETWORK_RELOC)
        #undef BUILD_AI_NETWORK_RELOC
        #endif

        #include <ll_aton_reloc_network.h>

        /*
            mem_pool_desc.flags definition - (32b)
                b31..b24 (8b) - type of memory pool - 1:RELOC, 2:COPY, 3:RESET
                b23..b16 (8b) - type of data - 1:PARAMS 2:ACTIV 3:MIXED
                b15..b8  (8b) - attr of data - 1:READ 2:WRITE 5:RCACHED 6:WCACHED
                b7..b0   (8b) - idx for param section (RELOC type)
        */
        """)

    tpl_mpool_array = dedent(
        """\
        const unsigned char __attribute__((used, section (".params_$idx"), )) $c_label[$size]; /* real size = $r_size */
        """)

    tpl_mpool_desc = indent(dedent(
        """\
        /* $desc */
        { .name=\"$name\", .flags=$flags, .foff=$foff, .dst=$dst, .size=$size },\
        """), '  ')

    logger.info(' creating %s', file_name_mpools)

    raw_data = bytearray(0)
    nb_fake_mregion_ = 0
    with open(file_name_mpools, "w") as fh_:
        fh_.writelines(network_reloc_mem_header)
        fh_.write('\n\n')
        fh_.write('/* Fake C-array for relocatable memory regions */\n\n')
        for mp_desc in mpool_cdesc:
            raw_data += mp_desc.raw_data
            if mp_desc.is_used and mp_desc.c_label:
                item_dict = {
                    'idx': str(mp_desc.get_id),
                    'c_label': mp_desc.c_label,
                    'size': str(_FAKE_SIZE),
                    'r_size': str(mp_desc.size)
                }
                code_ = Template(tpl_mpool_array).safe_substitute(item_dict)
                nb_fake_mregion_ += 1
                fh_.write(code_)
                fh_.write('\n')
        if nb_fake_mregion_ == 0:  # unreferenced region (PAD)
            item_dict = {
                'idx': '0',
                'c_label': '_unreferenced_buffer',
                'size': str(_FAKE_SIZE),
                'r_size': str(_FAKE_SIZE)
            }
            code_ = Template(tpl_mpool_array).safe_substitute(item_dict)
            fh_.write(code_)
            fh_.write('\n')
        fh_.write('\n')
        fh_.write('/* Mempool descriptors */\n\n')
        w_line_ = 'static ll_aton_reloc_mem_pool_desc __attribute__((used, section (".params_desc"), )) '
        w_line_ += '_params_desc[] = {\n'
        fh_.write(w_line_)
        for mp_desc in mpool_cdesc:
            if mp_desc.is_used:
                item_dict = {
                    'desc': str(mp_desc),
                    'name': mp_desc.name,
                    'flags': f'0x{mp_desc.flags:08x}UL',
                    'foff': str(mp_desc.foff),
                    'dst': f'0x{mp_desc.dst:08x}UL',
                    'size': str(mp_desc.size)
                }
                code_ = Template(tpl_mpool_desc).safe_substitute(item_dict)
                fh_.write(code_)
                fh_.write('\n')

        fh_.write('  /* NULL */\n')
        fh_.write('  { 0 },\n };\n')
        fh_.write('\n')
        fh_.close()

    logger.info(' creating %s', file_name_conf)
    mems_ = c_npu_network.memories()
    rt_version_ = c_npu_network.compiler.version
    rt_version_str_ = f'({rt_version_[0]} & 0xFF) << 24 | ({rt_version_[1]} & 0xFF) << 16'
    rt_version_str_ += f' | ({rt_version_[2]} & 0xFF) << 8'
    with open(file_name_conf, "w") as fh_:
        fh_.write('/* AUTOGENERATED DO NOT MODIFY */\n\n')
        fh_.write(tools_version_)
        if args.st_clang:
            fh_.write(f'#define RUNTIME_DESC        "{c_npu_network.compiler.desc} (RELOC.ST_CLANG)"\n')
        elif args.llvm:
            fh_.write(f'#define RUNTIME_DESC        "{c_npu_network.compiler.desc} (RELOC.CLANG)"\n')
        else:
            fh_.write(f'#define RUNTIME_DESC        "{c_npu_network.compiler.desc} (RELOC.GCC)"\n')
        fh_.write(f'#define RUNTIME_VERSION     ({rt_version_str_}) ')
        fh_.write(f' /* {c_npu_network.compiler.version[:-1]} */\n')
        fh_.write(f'#define RUNTIME_VERSION_DEV ({c_npu_network.compiler.version[3]}UL)\n\n')
        fh_.write(f'#define C_NAME              "{args.name.lower()}"\n')
        fh_.write(f'#define C_FCT_SUFFIX        {c_name_}\n')
        fh_.write(f'#define ACTS_SZ             ({mems_[0] + mems_[2]}UL) ')
        fh_.write(f' /* internal={size_int_to_str(mems_[0])}, externel={size_int_to_str(mems_[2])} */\n')
        fh_.write(f'#define PARAMS_SZ           ({mems_[1] + mems_[3]}UL) ')
        fh_.write(f' /* internal={size_int_to_str(mems_[1])}, external={size_int_to_str(mems_[3])} */\n')
        fh_.write(f'#define EXT_RAM_SZ          ({ext_ram_sz}UL)\n')
        fh_.write('\n')
        fh_.write(f'#define PARAMS_BIN_SZ       ({len(raw_data)}UL) ')
        fh_.write(f' /* {size_int_to_str(len(raw_data))} */\n')
        fh_.write(f'#define PARAMS_BIN_CRC32    ({zlib.crc32(raw_data) & 0xFFFFFFFF}UL)\n')

    if len(raw_data) == 0:
        logger.warning('No param initializers are defined.')
        return -1

    if len(raw_data) != align_up(len(raw_data), align=8):
        logger.warning('Size of the param initializers are not aligned on 8 bytes')

    logger.info(' creating %s (size=%s)', file_name_raw, f'{len(raw_data):,}')

    with open(file_name_raw, "wb") as fh_:
        fh_.write(raw_data)
        fh_.close()

    return 0


def main():
    """Script entry point."""

    parser = argparse.ArgumentParser(description='{} v{}'.format(__title__, __version__))

    parser.add_argument('--input', '-i', metavar='STR', type=str,
                        help='location of the generated c-files (or network.c file path)',
                        default=_DEFAULT_INPUT)

    parser.add_argument('--output', '-o', metavar='STR', type=str,
                        help='output directory',
                        default=_DEFAULT_BUILD_DIR)

    parser.add_argument('--name', '-n', metavar='STR', type=str,
                        help='basename of the generated c-files (default=<network-file-name>)',
                        default='no-name')

    parser.add_argument('--llvm', action='store_const', const=1,
                        help='use LLVM compiler and libraries (default: GCC compiler is used)')

    parser.add_argument('--st-clang', action='store_const', const=1,
                        help='use ST CLANG compiler and libraries (default: GCC compiler is used)')

    parser.add_argument('--parse-only', action='store_true',
                        help='Parsing only the generated c-files')

    parser.add_argument('--cont', action='store_true',
                        help='Continue on error')

    parser.add_argument('--log', metavar='STR', type=str, nargs='?',
                        default='no-log',
                        help='log file')

    parser.add_argument('--verbosity', '-v',
                        nargs='?', const=1, type=int, choices=range(0, 3),
                        default=1, help="set verbosity level")

    parser.add_argument('--debug', action='store_true',
                        help='Enable internal log (DEBUG PURPOSE)')

    parser.add_argument('--no-color', action='store_true',
                        help='Disable log color support')

    params: Params = Params(parser.parse_args())

    logger = create_logger(params, Path(__file__).stem)

    try:
        res = prepare_c_network_file(params)
    except BaseExceptionError as e:
        logger.exception(e, stack_info=False, exc_info=params.debug)
        return -1

    return res


if __name__ == '__main__':
    sys.exit(main())
