###################################################################################
#   Copyright (c) 2024 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
AiRunner Profiler utility (experimental)
"""
# from platform import node
import sys
import argparse
import logging
from enum import IntFlag
from typing import List, Union, Tuple, Optional, NamedTuple, Dict
from pathlib import Path
from datetime import datetime
import numpy as np

try:
    from stm_ai_runner import AiRunner, AiRunnerSession, get_logger
    from stm_ai_runner.neural_art.c_network_parser import CNpuNetworkDesc, EpochBlockDesc
    from stm_ai_runner.neural_art.c_network_parser import StreamEngineUnit, MemoryPool
    from stm_ai_runner.neural_art.exceptions import ErrorException
except ImportError:
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    try:
        from stm_ai_runner import AiRunner, AiRunnerSession, get_logger
        from stm_ai_runner.neural_art.c_network_parser import CNpuNetworkDesc, EpochBlockDesc
        from stm_ai_runner.neural_art.c_network_parser import StreamEngineUnit, MemoryPool
        from stm_ai_runner.neural_art.exceptions import ErrorException
    except ImportError as e:
        print('ModuleNotFoundError:', e,  # noqa: T201
              '- Update the \'PYTHONPATH\' to find the stm_ai_runner Python module.')
        sys.exit(1)


#
# History
#
#   v0.1 - initial version
#   v0.2 - add plot option
#   v0.3 - add EC support (merge compiler info associated to a given BLOB)
#        - add ai_runer summay
#   v0.4 - update plotted figures (two graphs: GOP & Time Inference per epoch)
#


__title__ = 'NPU Utility - AiRunner Profiler'
__version__ = '0.4'
__author__ = 'STMicroelectronics'


_DEFAULT = 'serial:921600'
_DEFAULT_NETWORK_FILE_PATH = 'st_ai_output'


_KB = 1000  # 1024 used to report the GB/s
_MB = _KB * _KB
_GB = _MB * _KB


class AiCounterType(IntFlag):
    """AiCounterType type"""
    EPOCH_LEN = 1 << 0
    STRG_ACTIVE = 1 << 1
    STRG_HENV = 1 << 2
    BUSIF_RW_DATA = 1 << 3
    NPU_CACHE = 1 << 4
    STRG_I_ACTIVE = 1 << 5
    STRG_O_ACTIVE = 1 << 6

    def __str__(self):
        """."""  # noqa: DAR201
        desc_ = []
        if self.value & AiCounterType.EPOCH_LEN:
            desc_.append('EPOCH_LEN')
        if self.value & AiCounterType.BUSIF_RW_DATA:
            desc_.append('PORT')
        if self.value & AiCounterType.STRG_ACTIVE:
            desc_.append('STRG_ACTIVE')
        if self.value & AiCounterType.STRG_I_ACTIVE:
            desc_.append('STRG_I_ACTIVE')
        if self.value & AiCounterType.STRG_O_ACTIVE:
            desc_.append('STRG_O_ACTIVE')
        if self.value & AiCounterType.STRG_HENV:
            desc_.append('STRG_HENV')
        if self.value & AiCounterType.NPU_CACHE:
            desc_.append('NPU_CACHE')
        return ' | '.join(desc_)

    __repr__ = __str__


def s_msg_get_values(cat: str, s_msgs: Union[List[str], str]):
    """Return a list of the values (str format)"""  # noqa: DAR101, DAR201
    if isinstance(s_msgs, str):
        s_msgs = [s_msgs]
    for s_msg in s_msgs:
        v_ = s_msg.split(':')
        idx_ = 2 if v_[0].startswith('s:') else 0
        n_idx_ = idx_ + 1
        if cat in v_[idx_] and len(v_) > n_idx_:
            return v_[n_idx_:] if len(v_) > n_idx_ else [v_[n_idx_]]
    return []


def to_ms(cycles: Union[int, List[int]], freq_hz: int) -> Union[float, List[float]]:
    """Return duration in ms"""  # noqa: DAR101, DAR201
    if isinstance(cycles, int):
        return cycles * 1000 / freq_hz
    return [v_ * 1000 / freq_hz for v_ in cycles]


def to_perc(values: Union[List[int], List[float]]) -> List[float]:
    """Return percentage"""  # noqa: DAR101, DAR201
    total_ = sum(values)
    return [round(v_ * 100 / total_, 2) for v_ in values]


def to_mbs(size_byte: int, duration_ms: float):
    """Return bandwidth MB/s"""  # noqa: DAR101, DAR201
    if duration_ms > 0.0:
        return size_byte / (duration_ms * 1000)
    return 0


def mbw_to_str(mbw: float):
    """Convert memory bandwidth value to readable string"""  # noqa: DAR101, DAR201
    if mbw > _GB:
        return f'{mbw / _GB:.2f} GB/s'
    if mbw > _MB:
        return f'{mbw / _MB:.2f} MB/s'
    if mbw > _KB:
        return f'{mbw / _KB:.2f} KB/s'
    return f'{int(mbw)} B/s'


def bandwidth(size_in_byte: int, total_cycles: int, freq_hz: int, txt: bool = False) -> Union[str, float]:
    """Compute the average memory bandwidth"""  # noqa: DAR101, DAR201
    bs_ = 0.0  # bytes/s
    if total_cycles > 0:
        bs_ = (size_in_byte * freq_hz) / total_cycles
    return mbw_to_str(bs_) if txt else bs_


def mean_round_up(vals: Union[float, List[float]]) -> int:
    """Round up float value to int. If list, arithhmetic mean is computed"""  # noqa: DAR101, DAR201
    vals = np.array(vals)
    return int(np.ceil(np.mean(vals)))


def compute_gops(n_ops: int, n_cycles: int, freq: int) -> float:
    """Return the number of operation by second (GOPS)"""  # noqa: DAR101, DAR201
    if n_cycles == 0:
        return 0.0
    return (freq * n_ops) / (n_cycles * 1000000000)


def get_mpool_descs(c_network_desc: CNpuNetworkDesc, strg_desc: StreamEngineUnit) -> Dict[MemoryPool, int]:
    """Return a dict with the associated memory pool descriptors and buffer size"""  # noqa: DAR101, DAR201
    mpools_: Dict[MemoryPool, int] = {}
    size_: int = strg_desc.size
    mpool_ = c_network_desc.mpools_by_id.get(strg_desc.mempool, None)
    if mpool_ and not mpool_.vpool:
        return {mpool_: size_}
    if not mpool_:
        return {}
    assert mpool_.vpool
    base_addr_ = mpool_.offset + strg_desc.addr_range[0]
    total_size_ = 0
    found_ = 0
    for pool_id in mpool_.mpools:
        mpool_desc_ = c_network_desc.mpools_by_id[pool_id]
        in_size_ = mpool_desc_.contains(base_addr_, size_, update_range=False)
        if in_size_:
            found_ += 1
            mpools_[mpool_desc_] = in_size_
            total_size_ += in_size_
    assert total_size_ == size_
    return mpools_


def get_epoch_desc(c_network_desc: CNpuNetworkDesc, selector: Union[int, str]) -> Optional[EpochBlockDesc]:
    """Return the associated epoch descriptor"""  # noqa: DAR101, DAR201
    for epoch in c_network_desc.epochs:
        if isinstance(selector, str):
            if epoch.name == selector:
                return epoch
        elif epoch.idx == selector:
            return epoch
    return None


class NpuDeviceDesc():
    """Class to handle the NPU IP desc/setting"""

    def __init__(self, name: str = 'Neural-ART 1.4 - STM32N6'):
        """Constructor"""  # noqa: DAR101, DAR201
        self.name = name
        self.dev_id: int = 0
        self.npu_freq: int = 0
        self.nic_freq: int = 0
        self.mcu_freq: int = 0
        self.noc_freq: int = 0

    def strg_id_to_busif(self, strg_id) -> int:
        """Return the associated busif"""  # noqa: DAR101, DAR201
        return 0 if strg_id < 5 else 1

    @property
    def npu_ram_freq(self) -> int:
        """Return freq associated to the npuRAM, axiram[3..6]"""
        # noqa: DAR101, DAR201
        return self.nic_freq

    @property
    def mcu_ram_freq(self) -> int:
        """Return freq associated to the mcuRAM, flexmem, axiram1 & axiram2"""
        # noqa: DAR101, DAR201
        return self.noc_freq


class MempoolUsageDesc():
    """Class to handle the mempool usage"""

    def __init__(self):
        """Constructor"""  # noqa: DAR101, DAR201
        self.r: int = 0  # number of read
        self.w: int = 0  # number of write
        self.nic_freq: int = 0
        self.mcu_freq: int = 0
        self.noc_freq: int = 0


class StrengMetric():
    """."""

    def __init__(self, streng_id: int = -1, cycles: int = 0, io_type: str = 'o'):
        """Constructor"""  # noqa: DAR101, DAR201
        self.id: int = streng_id  # strg id from RT
        self.cycles: int = cycles  # active npu cycles from RT
        self.io_type: str = io_type  # 'o' or 'i': strg type from RT
        self.busif: int = -1  # busif id from mdesc (fixed by NPU design)
        self.mpool_descs: Dict[MemoryPool, int] = {}  # pool desc / used size from compiler
        self.bytes_by_cycle: float = 0.0  # Byte by cycles
        self.size: int = 0  # size of the accessed memory range
        self.addr_range: Tuple[int, int] = (0, 0)
        self.type: str = ''

    def desc(self, max_cycles: int = 0, is_henv: bool = False) -> str:
        """Streng engine description"""  # noqa: DAR101, DAR201
        desc_ = f'STRENG.{self.id}.{self.io_type}: busif={self.busif}, {self.cycles} cycles'
        if self.mpool_descs:
            mpools_ = ', '.join([f'{key_.name}:{val_}' for key_, val_ in self.mpool_descs.items()])
            # desc_ += f', {self.addr_range}:{self.size}[{mpools_}]'
            desc_ += f', [{mpools_}]'
            if is_henv:
                desc_ += f', {self.bytes_by_cycle:.3f} B/cycle'
        else:
            desc_ += ', <no-data-size info>'
        if max_cycles > 0:
            ratio_ = (self.cycles * 100) / max_cycles
            desc_ += f', {ratio_:.0f}%'
        return desc_

    def __str__(self):
        """."""  # noqa: DAR101, DAR201
        return self.desc()

    __repr__ = __str__


class CyclesMetric(NamedTuple):
    """."""
    pre: int = 0
    core: int = 0
    post: int = 0

    def total(self) -> int:
        """Return total number of cycles"""  # noqa: DAR101, DAR201
        return self.pre + self.core + self.post

    def to_list(self) -> List[int]:
        """Return list"""  # noqa: DAR101, DAR201
        return [self.pre, self.core, self.post]

    def to_ms(self, freq: int) -> Union[float, List[float]]:
        """Return list"""  # noqa: DAR101, DAR201
        return to_ms(self.to_list(), freq)

    def __add__(self, o):
        return CyclesMetric(self.pre + o.pre, self.core + o.core,
                            self.post + o.post)


class NpuCacheMetric(NamedTuple):
    """."""
    r_hit: int = 0
    r_miss: int = 0
    r_alloc_miss: int = 0
    evict: int = 0
    w_hit: int = 0
    w_miss: int = 0
    w_alloc_miss: int = 0
    w_through: int = 0

    def __str__(self):
        """."""  # noqa: DAR101, DAR201
        desc_ = f'R[hit={self.r_hit}, miss={self.r_miss}, alloc-miss={self.r_alloc_miss}'
        desc_ += f', evict={self.evict}], W[hit={self.w_hit}, miss={self.w_miss}'
        desc_ += f', alloc-miss={self.w_alloc_miss}, through={self.w_through}]'
        return desc_


class NpuPortXMetric(NamedTuple):
    """."""
    # AW/RSIZE is always 3 (8 byte beats)
    id: int = 0
    r_b1_8: int = 0
    r_b2_8: int = 0
    r_b4_8: int = 0
    r_b8_8: int = 0
    w_b1_8: int = 0
    w_b2_8: int = 0
    w_b4_8: int = 0
    w_b8_8: int = 0

    def to_list(self):
        """Return list"""  # noqa: DAR101, DAR201
        return [self.id, self.r_b1_8, self.r_b2_8, self.r_b4_8, self.r_b8_8,
                self.w_b1_8, self.w_b2_8, self.w_b4_8, self.w_b8_8]

    @property
    def total_r(self):
        """Return total number of bytes (r)"""
        # noqa: DAR101, DAR201
        total = self.r_b1_8 * 1 + self.r_b2_8 * 2
        total += self.r_b4_8 * 4 + self.r_b8_8 * 8
        return total * 8

    @property
    def total_w(self):
        """Return total number of bytes (w)"""
        # noqa: DAR101, DAR201
        total = self.w_b1_8 * 1 + self.w_b2_8 * 2
        total += self.w_b4_8 * 4 + self.w_b8_8 * 8
        return total * 8

    @property
    def total(self):
        """Return total number of bytes (r+w)"""
        # noqa: DAR101, DAR201
        return self.total_r + self.total_w

    def to_desc(self):
        """Return summary"""  # noqa: DAR101, DAR201
        desc_ = f'r={self.total_r:<8d} w={self.total_w:<8d}'
        desc_ += f' rburst[1,2,4,8]x8=({self.r_b1_8},{self.r_b2_8},{self.r_b4_8},{self.r_b8_8})'
        desc_ += f' wburst[1,2,4,8]x8=({self.w_b1_8},{self.w_b2_8},{self.w_b4_8},{self.w_b8_8})'
        return desc_


class MetricRecords:
    """."""
    def __init__(self):
        self.strg_active: List[StrengMetric] = []
        self.strg_active_max: List[StrengMetric] = []
        self.strg_henv: List[StrengMetric] = []
        self.mcu_cycles: List[CyclesMetric] = []
        self.npu_cycles: List[CyclesMetric] = []
        self.npu_cache_r: List[Tuple[int, int, int, int]] = []
        self.npu_cache_w: List[Tuple[int, int, int, int]] = []
        self.port0_w: List[Tuple[int, int, int, int]] = []
        self.port0_r: List[Tuple[int, int, int, int]] = []
        self.port1_w: List[Tuple[int, int, int, int]] = []
        self.port1_r: List[Tuple[int, int, int, int]] = []


class AiNodeMetrics():
    """Class to handle the metrics for node"""  # noqa: DAR101, DAR201

    def __init__(self, node_name: str, c_idx: int):
        """Constructor"""  # noqa: DAR101, DAR201
        self.name: str = node_name.split(' ')[0]
        self.org_name: str = node_name
        self.c_idx: int = c_idx
        self.num: int = -1
        self.last_num: int = -1
        self.type: str = ''
        self._extra: int = 0  # number of associated extra epoch
        self._npu_cache: NpuCacheMetric = NpuCacheMetric()
        self._npu_port0: NpuPortXMetric = NpuPortXMetric()
        self._npu_port1: NpuPortXMetric = NpuPortXMetric()
        self._records: MetricRecords = MetricRecords()
        self._strg_active_max: StrengMetric = StrengMetric()
        self._strg_actives: List[StrengMetric] = []
        self._strg_henvs: List[StrengMetric] = []
        self._duration_ms: float = 0.0
        self._npu_cycles: CyclesMetric = CyclesMetric()
        self._npu_delta_cycles: int = 0  # max error
        self._mcu_cycles: CyclesMetric = CyclesMetric()
        self._mcu_extra_cycles: CyclesMetric = CyclesMetric()
        self._duration_extra_ms: float = 0.0
        self.ops: int = 0
        self.compute_cycles: int = 0
        self.max_cycles: int = 0
        self.mempools: Dict[str, List[Tuple[int, int]]] = {}

    @property
    def npu_cycles(self) -> CyclesMetric:
        """Return average of the npu cycles (pre, core, post)"""
        # noqa: DAR101, DAR201
        return self._npu_cycles

    @property
    def npu_delta_cycles(self) -> int:
        """Return core npu delta cycles (average)"""
        # noqa: DAR101, DAR201
        return self._npu_delta_cycles

    @property
    def mcu_cycles(self) -> CyclesMetric:
        """Return average of the mcu cycles (pre, core, post)"""
        # noqa: DAR101, DAR201
        return self._mcu_cycles

    @property
    def mcu_extra_cycles(self) -> CyclesMetric:
        """Return average of the mcu cycles (pre, core, post)"""
        # noqa: DAR101, DAR201
        return self._mcu_extra_cycles

    @property
    def npu_cache(self) -> NpuCacheMetric:
        """Return average of the npu cache counters"""
        # noqa: DAR101, DAR201
        return self._npu_cache

    def npu_busitf(self, idx: int = 0) -> NpuPortXMetric:
        """Return npu metric for a given busitf"""  # noqa: DAR101, DAR201
        return self._npu_port0 if idx == 0 else self._npu_port1

    @property
    def has_npu_statistics(self) -> bool:
        """Indicate if the npu statistics are available"""
        # noqa: DAR101, DAR201
        return self._npu_port0.total > 0 or self._npu_port1.total > 0

    @property
    def duration_ms(self) -> float:
        """Return total duration (ms)"""
        # noqa: DAR101, DAR201
        return self._duration_ms + self._duration_extra_ms

    @property
    def strg_active_max(self) -> StrengMetric:
        """Return streng active max"""
        # noqa: DAR101, DAR201
        return self._strg_active_max

    @property
    def strg_actives(self) -> List[StrengMetric]:
        """Return active stream-engines"""
        # noqa: DAR101, DAR201
        return self._strg_actives

    @property
    def strg_henvs(self) -> List[StrengMetric]:
        """Return henv stream-engines"""
        # noqa: DAR101, DAR201
        return self._strg_henvs

    def add_extra_metrics(self, mcu_freq: int,
                          npu: CyclesMetric,
                          mcu: CyclesMetric,
                          busif0: NpuPortXMetric,
                          busif1: NpuPortXMetric):
        """Add extra metrics"""  # noqa: DAR101, DAR201

        prev_ = self._mcu_extra_cycles.to_list()
        new_ = mcu.to_list()
        snew_ = [x + y for x, y in zip(prev_, new_)]
        self._mcu_extra_cycles = CyclesMetric(*snew_)

        prev_ = self._npu_port0.to_list()
        new_ = busif0.to_list()
        snew_ = [x + y for x, y in zip(prev_, new_)]
        self._npu_port0 = NpuPortXMetric(*snew_)

        prev_ = self._npu_port1.to_list()
        new_ = busif1.to_list()
        snew_ = [x + y for x, y in zip(prev_, new_)]
        self._npu_port1 = NpuPortXMetric(*snew_)
        self._extra += 1
        self._duration_extra_ms = to_ms(self._mcu_extra_cycles.total(), mcu_freq)

        prev_ = self._npu_cycles.to_list()
        new_ = npu.to_list()
        snew_ = [x + y for x, y in zip(prev_, new_)]
        self._npu_cycles = CyclesMetric(*snew_)

    @property
    def extra(self) -> int:
        """Return assciated extra epoch (for HYBRID epoch)"""
        # noqa: DAR101, DAR201
        return self._extra

    def _decode_s_msgs(self, s_msgs: List[str]):
        """Extract metrics from a list of 's:' messages"""  # noqa: DAR101, DAR201
        for s_msg_ in s_msgs:
            # s_msg format: s:<cat>:<sub-cat>:<values>
            values_ = s_msg_.split(':')
            values_ = values_[2:] if values_[0].startswith('s:') else values_
            if values_ and 'evt_pre_start' == values_[0]:
                # <c-idx:d>:<cur_num:d>:<num:d>:<num_last:d>:<flags:x>:<type:x>:<desc:s>
                self.c_idx = int(values_[1])
                self.num = int(values_[3])
                self.last_num = int(values_[4])
                self.type = values_[7]
            if values_ and 'mcu_cycles' == values_[0]:
                # <pre:d>:<core:d>:<post:d>
                pre_ = int(values_[1])
                core_ = int(values_[2])
                post_ = int(values_[3])
                cy_metric_ = CyclesMetric(pre_, core_, post_)
                self._records.mcu_cycles.append(cy_metric_)
            if values_ and 'npu_cycles' == values_[0]:
                # <pre:d>:<core:d>:<post:d>
                pre_ = int(values_[1])
                core_ = int(values_[2])
                post_ = int(values_[3])
                cy_metric_ = CyclesMetric(pre_, core_, post_)
                self._records.npu_cycles.append(cy_metric_)
            if values_ and 'npu_cache' == values_[0]:
                # <dir:c>:<r|w>:...
                if values_[1] == 'r':
                    # 'r':<r-hit:d>:<r-miss:d>:<r-alloc-miss:d>:<evict>
                    r_hit = int(values_[2])
                    r_miss = int(values_[3])
                    r_alloc_miss = int(values_[4])
                    evict = int(values_[5])
                    self._records.npu_cache_r.append((r_hit, r_miss, r_alloc_miss, evict))
                else:
                    # 'w':<w-hit:d>:<w-miss:d>:<w-alloc-miss:d>:<w-through:d>
                    w_hit = int(values_[2])
                    w_miss = int(values_[3])
                    w_alloc_miss = int(values_[4])
                    w_through = int(values_[5])
                    self._records.npu_cache_w.append((w_hit, w_miss, w_alloc_miss, w_through))
            if values_ and ('port0' == values_[0] or 'port1' == values_[0]):
                # port0|port1:burst:'r'|'w':<b1x8:d>:<b2x8:d>:<b4x8:d>:<b8x8:d>
                b1x8_, b2x8_ = int(values_[3]), int(values_[4])
                b4x8_, b8x8_ = int(values_[5]), int(values_[6])
                if 'port0' == values_[0] and values_[2] == 'w':
                    self._records.port0_w.append((b1x8_, b2x8_, b4x8_, b8x8_))
                if 'port0' == values_[0] and values_[2] == 'r':
                    self._records.port0_r.append((b1x8_, b2x8_, b4x8_, b8x8_))
                if 'port1' == values_[0] and values_[2] == 'w':
                    self._records.port1_w.append((b1x8_, b2x8_, b4x8_, b8x8_))
                if 'port1' == values_[0] and values_[2] == 'r':
                    self._records.port1_r.append((b1x8_, b2x8_, b4x8_, b8x8_))
            if values_ and 'streng_active' == values_[0]:
                # o|i:<id:d>:<cycles:d>:<diff:d>
                # max:i|o:<id:d>:<max_cycles:d>
                type_ = values_[1]
                if type_ == 'max':
                    cycles_ = int(values_[4])
                    id_ = int(values_[3])
                    type_ = values_[2]
                    strg_metric_ = StrengMetric(id_, cycles_, type_)
                    self._records.strg_active_max.append(strg_metric_)
                else:
                    cycles_ = int(values_[3])
                    id_ = int(values_[2])
                    strg_metric_ = StrengMetric(id_, cycles_, type_)
                    self._records.strg_active.append(strg_metric_)
            if values_ and 'streng_henv' == values_[0]:
                # i:<id:d>:<cycles:d>:<diff:d>
                type_ = values_[1]
                id_ = int(values_[2])
                cycles_ = int(values_[3])
                metric_ = StrengMetric(id_, cycles_, type_)
                self._records.strg_henv.append(metric_)

    def process_s_msgs(self, s_msgs_list: List[List[str]]):
        """Extract metrics from 's:' messages"""  # noqa: DAR101, DAR201
        for s_msgs_ in s_msgs_list:
            self._decode_s_msgs(s_msgs_)

    def adjust(self, device: NpuDeviceDesc, adjust: bool = False):
        """Adjust and process the collected records"""  # noqa: DAR101, DAR201

        # strg active - compute the average value
        strg_actives_ = {}  # type: ignore
        for strg_ in self._records.strg_active:
            if strg_.id in strg_actives_:
                strg_actives_[strg_.id]["cycles"].append(strg_.cycles)
            else:
                strg_actives_[strg_.id] = {"cycles": [strg_.cycles], "type": strg_.io_type}

        # max streng active?
        self._strg_active_max = StrengMetric()
        for key, val in strg_actives_.items():
            strg_ = StrengMetric(key, mean_round_up(val["cycles"]), val["type"])
            self._strg_actives.append(strg_)
            if self._strg_active_max.cycles < strg_.cycles:
                self._strg_active_max = strg_

        strg_henvs_ = {}
        for strg_ in self._records.strg_henv:
            if strg_.id in strg_henvs_:
                strg_henvs_[strg_.id]["cycles"].append(strg_.cycles)
            else:
                strg_henvs_[strg_.id] = {"cycles": [strg_.cycles], "type": strg_.io_type}
        for key, val in strg_henvs_.items():
            self._strg_henvs.append(StrengMetric(key, mean_round_up(val["cycles"]), val["type"]))

        # pre/core/post npu cycles (compute the average values)
        pres_ = [m_.pre for m_ in self._records.npu_cycles]
        cores_ = [m_.core for m_ in self._records.npu_cycles]
        posts_ = [m_.post for m_ in self._records.npu_cycles]
        self._npu_cycles = CyclesMetric(mean_round_up(pres_), mean_round_up(cores_),
                                        mean_round_up(posts_))

        # set the id of the busif
        for strg in self.strg_actives + self.strg_henvs + [self._strg_active_max]:
            strg.busif = device.strg_id_to_busif(strg.id)

        # evaluate max error
        self._npu_delta_cycles = 0
        if self._strg_active_max.cycles > self._npu_cycles.core:
            self._npu_delta_cycles = self._strg_active_max.cycles - self._npu_cycles.core
        if adjust:
            self._npu_cycles = CyclesMetric(self._npu_cycles.pre - self._npu_delta_cycles,
                                            self._npu_cycles.core + self._npu_delta_cycles,
                                            self._npu_cycles.post)

        # pre/core/post mcu cycles (compute the average values)
        pres_ = [m_.pre for m_ in self._records.mcu_cycles]
        cores_ = [m_.core for m_ in self._records.mcu_cycles]
        posts_ = [m_.post for m_ in self._records.mcu_cycles]
        self._mcu_cycles = CyclesMetric(mean_round_up(pres_), mean_round_up(cores_),
                                        mean_round_up(posts_))

        # total duration (based on mcu cycles)
        total_ = [m_.total() for m_ in self._records.mcu_cycles]
        self._duration_ms = to_ms(mean_round_up(total_), device.mcu_freq)

        # merge npu_cache counters
        nb_records = len(self._records.npu_cache_w)
        if nb_records:
            nb_op_r = np.empty((4,)).astype(np.int64)
            for rec_ in self._records.npu_cache_r:
                nb_op_r += np.array(rec_).astype(np.int64)
            nb_op_w = np.empty((4,)).astype(np.int64)
            for rec_ in self._records.npu_cache_w:
                nb_op_w += np.array(rec_).astype(np.int64)
            nb_op_r = [int(v_ / nb_records) for v_ in nb_op_r]
            nb_op_w = [int(v_ / nb_records) for v_ in nb_op_w]
            self._npu_cache = NpuCacheMetric(*nb_op_r, *nb_op_w)

        # merge port0/port1 burst counters
        nb_records = len(self._records.port0_r)
        if nb_records:
            # only one record is used
            self._npu_port0 = NpuPortXMetric(0, *self._records.port0_r[0],
                                             *self._records.port0_w[0])
            self._npu_port1 = NpuPortXMetric(1, *self._records.port1_r[0],
                                             *self._records.port1_w[0])

    def finalize(self, c_net_desc: CNpuNetworkDesc, device: NpuDeviceDesc):
        """Finalize the node with the info from the epoch descriptor (compiler)"""  # noqa: DAR101, DAR201

        if c_net_desc is None:
            return

        epoch_desc_ = c_net_desc.get_epoch_desc(self.name)
        self.ops = epoch_desc_.perfs["ops"]
        self.compute_cycles = epoch_desc_.perfs["compute_cycles"]
        self.max_cycles = epoch_desc_.perfs["max_cycles"]

        # create a dict by mempool with the number of memory accesses (bytes)
        mem_accesses_ = epoch_desc_.perfs["mem_accesses"]
        for key, value in mem_accesses_.items():
            if value[0] or value[2]:
                mpools_ = self.mempools.get(key, [0, 0])
                mpools_[0] += value[0]
                mpools_[1] += value[2]
                self.mempools[key] = mpools_

        if len(self.strg_actives) == 0:
            return

        strg_units_: List[StreamEngineUnit] = epoch_desc_.get_streng_units()

        def _c_streng_desc(id_) -> Optional[StreamEngineUnit]:
            """Return associated streng descriptor"""  # noqa: DAR101, DAR201
            return next((x_ for x_ in strg_units_ if x_.id == id_), None)

        # set the addessed memory range by stream engine
        for strg in self.strg_actives + self.strg_henvs + [self._strg_active_max]:
            c_strg_desc_ = _c_streng_desc(strg.id)
            if c_strg_desc_ is None:
                continue
            strg.mpool_descs = get_mpool_descs(c_net_desc, c_strg_desc_)
            strg.addr_range = c_strg_desc_.addr_range
            strg.size = c_strg_desc_.size
            strg.bytes_by_cycle = strg.size / strg.cycles

    def __str__(self):
        """."""  # noqa: DAR101, DAR201
        desc_ = f'NODE: {self.name} {self.type} {self.c_idx} ({self.num}, {self.last_num})'
        return desc_


class AiRunnerProfiler():
    """Collect the profiling metrics from a AiRunner instance"""  # noqa: DAR101, DAR201

    def __init__(self, ai_runner: Union[AiRunner, AiRunnerSession],
                 c_network_desc: Optional[CNpuNetworkDesc] = None,
                 logger: logging.Logger = None):
        """Constructor"""  # noqa: DAR101, DAR201, DAR401
        self._ai_runner: Union[AiRunner, AiRunnerSession] = ai_runner
        self._nodes: List[AiNodeMetrics] = []
        self._c_net_desc: Optional[CNpuNetworkDesc] = c_network_desc
        self._device: NpuDeviceDesc = NpuDeviceDesc()

        if logger is None:
            logger = get_logger(level=logging.INFO)
        self._logger = logger

        self._logger.debug('creating AiRunnerProfile object')

        model_info_ = ai_runner.get_info()
        extra_ = model_info_['device'].get('extra', None)
        if not extra_:
            raise RuntimeError('Only validation stack with "extra" info is supported')

        values_ = s_msg_get_values('version', extra_)
        if values_[0] != '1.0':
            msg_ = f'S:msg version "{values_[0]}" is not supported (expected "1.0")'
            self._logger.error(msg_)
            raise RuntimeError(msg_)

        values_ = s_msg_get_values('dev_id', extra_)
        self._device.dev_id = int(values_[0], base=16)
        if self._device.dev_id not in [0x486, 0x47B]:
            msg_ = f'Device 0x{self._device.dev_id:x} is not supported, expected [0x486/0x47B] - STM32N6xx/STM32H7Pxxx'
            self._logger.error(msg_)
            raise RuntimeError(msg_)

        values_ = s_msg_get_values('npu_freq', extra_)
        if not values_:
            raise RuntimeError('NPU frequency is not provided')
        self.npu_freq = int(values_[0])
        self._device.npu_freq = int(values_[0])

        values_ = s_msg_get_values('nic_freq', extra_)
        if not values_:
            values_ = s_msg_get_values('axi_freq', extra_)
            if not values_:
              raise RuntimeError('nic_freq/axi_freq frequency is not provided')
        self._device.nic_freq = int(values_[0])

        values_ = s_msg_get_values('mcu_freq', extra_)
        if not values_:
            raise RuntimeError('MCU frequency is not provided')
        self.mcu_freq = int(values_[0])
        self._device.mcu_freq = int(values_[0])

        values_ = s_msg_get_values('noc_freq', extra_)
        if not values_:
            values_ = s_msg_get_values('ahb_freq', extra_)
            if not values_:
              raise RuntimeError('noc_freq/ahb_freq frequency is not provided')
        self._device.noc_freq = int(values_[0])

        self.duration_ms: float = 0.0
        self.mcu_total_cycles: CyclesMetric = CyclesMetric(0, 0, 0)
        self.npu_delta_cycles: int = 0  # average error
        self.npu_total_cycles: CyclesMetric = CyclesMetric(0, 0, 0)
        self.npu_total_core_cycles: int = 0

        self.total_compute_cycles: int = 0
        self.total_max_cycles: int = 0
        self.total_ops: int = 0
        self.total_ms: float = 0.0
        self.total_mcu_cycles: int = 0
        self.total_npu_cycles: int = 0
        self.total_npu_core_cycles: int = 0

        self.adjust_core_npu_cycles: bool = False
        self.mempools: Dict[str, List[int, int]] = {}

    def _post_process(self):
        """Post-process to adjust the statistics"""  # noqa: DAR101, DAR201

        # Compute the total mcu cycles
        t_pre, t_core, t_post = 0, 0, 0
        t_npu_pre, t_npu_core, t_npu_post = 0, 0, 0
        for node_ in self._nodes:
            node_.adjust(self._device, self.adjust_core_npu_cycles)
            t_pre += node_.mcu_cycles.pre
            t_core += node_.mcu_cycles.core
            t_post += node_.mcu_cycles.post
            t_npu_pre += node_.npu_cycles.pre
            t_npu_core += node_.npu_cycles.core
            t_npu_post += node_.npu_cycles.post
        self.mcu_total_cycles = CyclesMetric(t_pre, t_core, t_post)
        self.npu_total_cycles = CyclesMetric(t_npu_pre, t_npu_core, t_npu_post)

        # Compute the total npu cycles
        npu_deltas_ = []
        for node_ in self._nodes:
            if node_.npu_delta_cycles:
                npu_deltas_.append(node_.npu_delta_cycles)
            self.duration_ms += node_.duration_ms
        self.npu_delta_cycles = mean_round_up(npu_deltas_) if npu_deltas_ else 0

        self.npu_total_core_cycles = 0
        for node_ in self._nodes:
            self.npu_total_core_cycles += node_.npu_cycles.core

        # Merge hybrid epoch with next extra epochs
        n_nodes_ = []
        for node_ in self._nodes:
            if node_.type == 'EXTRA':
                n_nodes_[-1].add_extra_metrics(self.mcu_freq,
                                               node_.npu_cycles,
                                               node_.mcu_cycles,
                                               node_.npu_busitf(0),
                                               node_.npu_busitf(1))
            else:
                n_nodes_.append(node_)
        self._nodes = n_nodes_

        # Compute the total values
        for node_ in self._nodes:
            node_.finalize(self._c_net_desc, self._device)
            for key_, val_ in node_.mempools.items():
                c_mpool_ = self.mempools.get(key_, [0, 0, 0, 0, 0, 0])
                c_mpool_[0] += val_[0]
                c_mpool_[1] += val_[1]
                self.mempools[key_] = c_mpool_

        for node_ in self._nodes:
            self.total_compute_cycles += node_.compute_cycles
            self.total_max_cycles += node_.max_cycles
            self.total_ops += node_.ops
            self.total_ms += node_.duration_ms
            self.total_mcu_cycles += node_.mcu_cycles.total()
            self.total_mcu_cycles += node_.mcu_extra_cycles.total()
            self.total_npu_cycles += node_.npu_cycles.total()
            self.total_npu_core_cycles += node_.npu_cycles.core

        msg_ = f'npu_delta_cycles={self.npu_delta_cycles} adjust={self.adjust_core_npu_cycles}'
        msg_ += f' duration={self.duration_ms:.3f}ms'
        self._logger.debug(msg_)

    def profile(self, inputs: Optional[Union[np.ndarray, List[np.ndarray]]] = None,
                batch_size: int = 2, debug: bool = False):
        """Profile/collect the data"""  # noqa: DAR101, DAR201

        collect_henv = False

        mode = AiRunner.Mode.PER_LAYER
        if debug:
            mode |= AiRunner.Mode.DEBUG

        batch_size = max(batch_size, 1)

        self._logger.info('')
        msg_ = f'-> collecting statistics (b={batch_size}, mode={mode})..'
        self._logger.info(msg_)

        if not inputs:
            inputs = self._ai_runner.generate_rnd_inputs(batch_size=batch_size)
            mode |= AiRunner.Mode.PERF_ONLY

        # Pre-run to remove the possible cache-effects
        self._ai_runner.invoke(inputs, mode=AiRunner.Mode.PERF_ONLY, disable_pb=True)

        # Collect EPOCH_LEN, NPU_CACHE & STRG_I_ACTIVE statistics
        self._logger.info('collect input streng activities and NPU cache counters')
        option = AiCounterType.STRG_I_ACTIVE | AiCounterType.EPOCH_LEN | AiCounterType.NPU_CACHE
        _, profiler = self._ai_runner.invoke(inputs, mode=mode, disable_pb=True, option=option)

        for idx, c_node in enumerate(profiler['c_nodes']):
            p_item = AiNodeMetrics(c_node["name"], idx)
            p_item.process_s_msgs(c_node["extra"])
            self._nodes.append(p_item)

        # Collect EPOCH_LEN, NPU_CACHE & STRG_O_ACTIVE statistics
        self._logger.info('collect output streng activities and NPU cache counters')
        option = AiCounterType.STRG_O_ACTIVE | AiCounterType.EPOCH_LEN | AiCounterType.NPU_CACHE
        _, profiler = self._ai_runner.invoke(inputs, mode=mode, disable_pb=True, option=option)

        for node, c_node in zip(self._nodes, profiler['c_nodes']):
            assert c_node["name"] == node.org_name, f"Oh no! {c_node['name']} != {node.org_name}"
            node.process_s_msgs(c_node["extra"])

        if collect_henv:
            # Collect EPOCH_LEN, STRG_HENV statistics
            self._logger.info('collect streng henv signals')
            option = AiCounterType.STRG_HENV | AiCounterType.EPOCH_LEN
            _, profiler = self._ai_runner.invoke(inputs, mode=mode, disable_pb=True, option=option)

            for node, c_node in zip(self._nodes, profiler['c_nodes']):
                assert c_node["name"] == node.org_name, f"Oh no! {c_node['name']} != {node.org_name}"
                node.process_s_msgs(c_node["extra"])

        # Collect the busif statistics
        self._logger.info('collect busif requests')
        option = AiCounterType.BUSIF_RW_DATA
        outputs, profiler = self._ai_runner.invoke(inputs, mode=mode, disable_pb=True, option=option)

        for node, c_node in zip(self._nodes, profiler['c_nodes']):
            assert c_node["name"] == node.org_name, f"Oh no! {c_node['name']} != {node.org_name}"
            node.process_s_msgs(c_node["extra"])

        self._logger.info('post-process the recorded data..')
        self._post_process()

        self._ai_runner.print_profiling(inputs, profiler, outputs,
                                        print_fn=self._logger.info,
                                        tensor_info=False)

        self._logger.info('<- done')

    def summary(self, pr_fct=None):
        """."""  # noqa: DAR101, DAR201

        def _get_epoch_desc(epoch_name_: str) -> EpochBlockDesc:
            if self._c_net_desc is None:
                return None
            return self._c_net_desc.get_epoch_desc(epoch_name_)

        def _attr_rw_bw_to_str(n_r, n_w, cycles_, freq_):
            bw_ = bandwidth(n_r + n_w, cycles_, freq_, True)
            return f'r={n_r:<10d} w={n_w:<10d} -> {bw_}'

        class Writter():
            """."""  # noqa: DAR101, DAR201

            def __init__(self, pr_fct=None):
                self._pr = print if pr_fct is None else pr_fct  # noqa: T202
                self.indent = 2
                self.max = 24

            def separator(self, simple_line: bool = False):
                """."""  # noqa: DAR101, DAR201
                if simple_line:
                    self._pr('')
                else:
                    self._pr('-' * 60)

            def section(self, title: str = ''):
                """."""  # noqa: DAR101, DAR201
                self._pr(f'[{title}]')

            def attr(self, attr: str, desc: str = '', sep: str = ':'):
                """."""  # noqa: DAR101, DAR201
                p_ = ' ' * (self.max - self.indent - len(attr))
                self._pr(' ' * self.indent + f'{attr}{p_} {sep} {desc}')

            def line(self, line_):
                """."""
                self._pr(' ' * self.indent + f'{line_}')

        printer = Writter(self._logger.info if pr_fct is None else pr_fct)

        printer.separator(True)

        for node in self._nodes:
            epoch_desc_: Optional[EpochBlockDesc] = _get_epoch_desc(node.name)
            printer.separator()
            attr_desc_ = f'{node.name} (c_idx={node.c_idx}, num={node.num}:{node.last_num}'
            attr_desc_ += f', c_type={node.type}, extra={node.extra})'
            printer.line(attr_desc_)
            printer.separator()

            n_max_cycles_ = 0
            n_compute_cycles_ = 0
            n_ops_ = 0

            printer.section('compiler')
            if epoch_desc_ is not None:
                assert node.num == epoch_desc_.epoch_num

                printer.attr('epoch type', f'{epoch_desc_.type}')
                printer.attr('operations', f'{epoch_desc_.ops_to_dict()}')
                printer.attr('processor units', f'{epoch_desc_.units_to_dict()}')

                n_ops_, n_compute_cycles_ = epoch_desc_.perfs["ops"], epoch_desc_.perfs["compute_cycles"]
                n_max_cycles_ = epoch_desc_.perfs["max_cycles"]

                printer.attr('ops', f'{epoch_desc_.perfs["ops"]}')
                printer.attr('compute cycles', f'{epoch_desc_.perfs["compute_cycles"]} (max_cycles={n_max_cycles_})')
                if n_ops_:
                    max_ops_ = compute_gops(n_ops_, n_compute_cycles_, self.npu_freq)
                    min_ops_ = compute_gops(n_ops_, n_max_cycles_, self.npu_freq)
                    printer.attr('ops/cycle', f'{min_ops_:.1f} GOPS (ideal={max_ops_:.1f})')
                else:
                    printer.attr('ops/cycle', '<no ops available>')
                attr_ = ' '.join([f'[{key_}: r={val_[0]}, w={val_[1]}]' for key_, val_ in node.mempools.items()])
                printer.attr('mem accesses', f'{attr_}')
            else:
                printer.attr('operations', '<no-info available from the compiler>')

            printer.section('target')

            attr_desc_ = f'{node.duration_ms:.03f}ms ({(node.duration_ms/self.duration_ms * 100):3.1f}%)'
            attr_desc_ += f' total={self.duration_ms:.03f}ms'
            printer.attr('duration', attr_desc_)

            mcu_cycles = node.mcu_cycles.to_list()
            mcu_ms = [f'{val:.3f}' for val in to_ms(mcu_cycles, self.mcu_freq)]
            attr_desc_ = f'{mcu_cycles} -> {",".join(mcu_ms)} ms (mcu_freq={int(self.mcu_freq / 1000000)}MHz)'
            attr_desc_ += f', {sum(to_ms(mcu_cycles, self.mcu_freq)):.03f}ms'
            printer.attr('mcu cycles', attr_desc_)

            if node.extra:
                mcu_cycles = node.mcu_extra_cycles.to_list()
                mcu_ms = [f'{val:.3f}' for val in to_ms(mcu_cycles, self.mcu_freq)]
                attr_desc_ = f'{mcu_cycles} -> {",".join(mcu_ms)} ms (mcu_freq={int(self.mcu_freq / 1000000)}MHz)'
                attr_desc_ += f', {sum(to_ms(mcu_cycles, self.mcu_freq)):.03f}ms'
                printer.attr('extra mcu', attr_desc_)
                mcu_cycles_ = node.mcu_cycles + node.mcu_extra_cycles
                mcu_cycles_ = mcu_cycles_.to_list()
                mcu_ms = [f'{val:.3f}' for val in to_ms(mcu_cycles_, self.mcu_freq)]
                attr_desc_ = f'{mcu_cycles_} -> {",".join(mcu_ms)} ms (mcu_freq={int(self.mcu_freq / 1000000)}MHz)'
                printer.attr('total mcu', attr_desc_)

            if node.has_npu_statistics:
                busitf0, busitf1 = node.npu_busitf(0), node.npu_busitf(1)
                npu_core_err = ''
                if n_max_cycles_:
                    diff_ = node.npu_cycles.core - n_max_cycles_
                    npu_core_err = f'diff. vs max_cycles from compiler: {"+" if diff_ > 0 else ""}{diff_}'
                    npu_core_err += f' ({diff_ * 100 /node.npu_cycles.core:.2f}%)'
                attr_desc_ = f'{node.npu_cycles.core} -> {to_ms(node.npu_cycles.core, self.npu_freq):.3f} ms'
                attr_desc_ += f' (npu_freq={int(self.npu_freq / 1000000)}MHz) {npu_core_err}'
                printer.attr('core npu cycles', attr_desc_)

                if n_compute_cycles_:
                    npu_compute_ = f'{(n_compute_cycles_ * 100)/node.npu_cycles.core:.2f}%'
                    real_npu_compute_ = f'{(n_compute_cycles_ * 100)/ node.npu_cycles.total():.2f}%'
                    printer.attr('compute cycles ratio', f'{real_npu_compute_} (core only: {npu_compute_})')
                else:
                    printer.attr('compute cycles ratio', '<no compute cycles available>')

                attr_desc_ = f'{busitf0.to_desc()}'
                attr_desc_ += f' -> {bandwidth(busitf0.total, node.npu_cycles.core, self.npu_freq, True )}'
                printer.attr('busif 0', attr_desc_)
                attr_desc_ = f'{busitf1.to_desc()}'
                attr_desc_ += f' -> {bandwidth(busitf1.total, node.npu_cycles.core, self.npu_freq, True )}'
                printer.attr('busif 1', attr_desc_)
                printer.attr('busif (total)', _attr_rw_bw_to_str(busitf0.total_r + busitf1.total_r,
                                                                 busitf0.total_w + busitf1.total_w,
                                                                 node.npu_cycles.core, self.npu_freq))

                strg_cycle_max = node.strg_active_max.cycles
                if n_ops_:
                    real_ops = compute_gops(n_ops_, node.npu_cycles.total(), self.npu_freq)
                    real_core_ops = compute_gops(n_ops_, node.npu_cycles.core, self.npu_freq)
                    printer.attr('ops/cycle', f'{real_ops:.1f} GOPS (core only: {real_core_ops:.1f})')
                else:
                    printer.attr('ops/cycle', '<no ops available>')
                attr_desc_ = f'{(strg_cycle_max * 100)/node.npu_cycles.core:.2f}% (id={node.strg_active_max.id})'
                printer.attr('strg engines', attr_desc_)
                for strg in node.strg_actives:
                    printer.attr(' active', f'{strg.desc(node.npu_cycles.core)}')

                for strg in node.strg_henvs:
                    printer.attr(' henv', f'{strg.desc(node.npu_cycles.core, True)}')

                printer.attr('NPU cache cnts', node.npu_cache)

                t_r, t_w = 0, 0
                for key, val in node.mempools.items():
                    t_r += val[0]
                    t_w += val[1]
                    printer.attr(f' {key}', _attr_rw_bw_to_str(val[0], val[1], node.npu_cycles.core, self.npu_freq))
                printer.attr(' total', _attr_rw_bw_to_str(t_r, t_w, node.npu_cycles.core, self.npu_freq))

            else:
                printer.attr('npu cycles', 'n.a.')

            printer.separator(True)

        printer.separator(True)
        printer.separator()
        printer.attr('Summary', '', '')
        printer.separator()

        if self._c_net_desc:
            self._c_net_desc.summary(full=False)

        printer.separator(True)

        assert self.mcu_total_cycles.total() == self.total_mcu_cycles

        if self._c_net_desc is not None:
            printer.line('Compiler')
            printer.attr(' cycles', f'{self.total_max_cycles} (total max_cycles)')
            printer.attr(' ideal cycles', f'{self.total_compute_cycles} (total compute_cycles)')
            printer.attr(' ops', f'{self.total_ops}')
            printer.attr(' ops/cycle', f'{int(self.total_ops/self.total_max_cycles)}')
            printer.attr(' inf/s', f'{self.npu_freq / self.total_max_cycles:.1f} (based on estimated total max_cycles)')
            printer.attr(' ideal ops/cycle', f'{int(self.total_ops/self.total_compute_cycles)}')
            printer.attr(' ideal inf/s', f'{self.npu_freq / self.total_compute_cycles:.1f}')
            printer.separator(True)

        printer.line('Measured')
        mcu_cycles = self.mcu_total_cycles.to_list()
        core_ms = to_ms(self.npu_total_core_cycles, self.npu_freq)
        attr_desc_ = f'{self.total_ms:.3f}ms, npu_core:{core_ms:.3f}ms'
        attr_desc_ += f' ({core_ms * 100 / self.total_ms:.2f}%), mcu_cycles={to_perc(mcu_cycles)}%'
        printer.attr(' total duration', attr_desc_)

        printer.attr(' mcu cycles', f'{self.total_mcu_cycles} (core only = {self.mcu_total_cycles.core})')
        printer.attr(' npu cycles', f'{self.total_npu_cycles} (core only = {self.total_npu_core_cycles})')
        if self.total_ops:
            real_ops = compute_gops(self.total_ops, self.total_npu_cycles, self.npu_freq)
            real_core_ops = compute_gops(self.total_ops, self.total_npu_core_cycles, self.npu_freq)
            printer.attr(' ops/cycle', f'{real_ops:.1f} GOPS / including SW epochs (core only = {real_core_ops:.1f})')
        else:
            printer.attr(' ops/cycle', '<no ops available>')
        attr_desc_ = f'{self.mcu_freq / self.total_mcu_cycles:.1f}'
        attr_desc_ += f' ({to_ms(self.total_mcu_cycles, self.mcu_freq):.3f}ms)'
        printer.attr(' inf/s', attr_desc_)
        if self.total_ops:
            npu_compute_ = f'{(self.total_compute_cycles * 100)/self.total_npu_core_cycles:.2f}%'
            real_npu_compute_ = f'{(self.total_compute_cycles * 100)/(self.total_npu_cycles):.2f}%'
            printer.attr(' compute cycles ratio', f'{real_npu_compute_} (core only: {npu_compute_})')
        else:
            printer.attr(' compute cycles ratio', '<no compute cycles available>')

        printer.separator(True)
        printer.line('Memory bandwidth / inference')
        if not self.mempools:
            printer.attr(' <mempool name>', '<no mempool info available>')
            printer.separator(True)
            return

        t_r, t_w = 0, 0
        for key_, val_ in self.mempools.items():
            t_r += val_[0]
            t_w += val_[1]
            attr_desc_ = _attr_rw_bw_to_str(val_[0], val_[1], self.total_npu_core_cycles, self.npu_freq)
            attr_desc_ += ' (peak)'
            average_ = bandwidth(val_[0] + val_[1], self.total_mcu_cycles, self.mcu_freq, True)
            attr_desc_ += f', {average_} (average)'
            printer.attr(f' {key_}', attr_desc_)

        average_ = bandwidth(t_r + t_w, self.total_mcu_cycles, self.mcu_freq, True)
        attr_desc_ = _attr_rw_bw_to_str(t_r, t_w, self.total_npu_core_cycles, self.npu_freq)
        printer.attr(' total r/w', f'{attr_desc_} (peak), {average_} (average)')

        printer.separator(True)

    def plot(self):
        """Plot a graph with the different epochs"""

        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            self._logger.warning('"plotly" Python module should be installed!')
            return

        def _name_x(node_: AiNodeMetrics) -> str:
            str_ = f'{node_.num}:{node_.type}'
            if 'EC' in node_.type:
                str_ += f' -> {node_.last_num}'
            return str_

        x_names = []
        y_mcu_cycles = []
        y_compute_cycles = []
        y_ops = []
        post_color = []
        for node in self._nodes:
            x_names.append(_name_x(node))
            y_mcu_cycles.append(node.mcu_cycles + node.mcu_extra_cycles)
            y_compute_cycles.append(node.compute_cycles)
            if 'SW' in node.type:
                post_color.append('darkgrey')
            elif 'HYBRID' in node.type:
                post_color.append('darkgreen')
            else:
                post_color.append('darksalmon')
            y_ops.append(node.ops)

        clk_ratio_ = self._device.npu_freq / self._device.mcu_freq
        y_ideal_ops = [compute_gops(ops_, cycles_, self._device.npu_freq)
                       for ops_, cycles_ in zip(y_ops, y_compute_cycles)]
        y_core_ops = [compute_gops(ops_, cycles_.core * clk_ratio_, self._device.npu_freq)
                      for ops_, cycles_ in zip(y_ops, y_mcu_cycles)]
        y_real_ops = [compute_gops(ops_, cycles_.total() * clk_ratio_, self._device.npu_freq)
                      for ops_, cycles_ in zip(y_ops, y_mcu_cycles)]

        fig = make_subplots(rows=2, cols=1, subplot_titles=('GOPs', 'Execution time (ms)'),
                            shared_xaxes=True,
                            vertical_spacing=0.05,
                            specs=[[{"type": "xy", "secondary_y": False}],
                                   [{"type": "xy"}]
                                   ])

        fig.add_trace(
            go.Scatter(x=x_names,
                       y=y_ideal_ops,
                       fill="tozeroy",
                       mode="lines+markers",
                       name='ideal ops',
                       marker_color='darkorange',
                       legend="legend1"
                       ), row=1, col=1,
            # secondary_y=False
        )

        fig.add_trace(
            go.Scatter(x=x_names,
                       y=y_core_ops,
                       # fill="tozeroy",
                       mode="lines+markers",
                       name='core ops',
                       zorder=2,
                       marker_color='darksalmon',
                       legend="legend1"
                       ), row=1, col=1,
            # secondary_y=True
        )

        fig.add_trace(
            go.Scatter(x=x_names,
                       y=y_real_ops,
                       fill="tozeroy",
                       mode="lines+markers",
                       name='real ops',
                       zorder=3,
                       marker_color='darkgoldenrod',
                       legend="legend1"
                       ), row=1, col=1,
            # secondary_y=True
        )

        fig.add_trace(
            go.Bar(x=x_names,
                   y=[to_ms(val_.pre, self._device.mcu_freq) for val_ in y_mcu_cycles],
                   name='pre',
                   marker_color='lightsalmon',
                   text='pre',
                   zorder=1,
                   textposition='outside',
                   legend="legend2"
                   ), row=2, col=1,
            # secondary_y=False
        )

        fig.add_trace(
            go.Bar(x=x_names,
                   y=[to_ms(val_.core, self._device.mcu_freq) for val_ in y_mcu_cycles],
                   name='core',
                   marker_color='darkred',
                   text='core',
                   zorder=1,
                   textposition='outside',
                   legend="legend2"
                   ), row=2, col=1,
            # secondary_y=False
        )

        fig.add_trace(
            go.Bar(x=x_names,
                   y=[to_ms(val_.post, self._device.mcu_freq) for val_ in y_mcu_cycles],
                   name='post',
                   # marker_color='darksalmon',
                   text='post',
                   zorder=1,
                   textposition='outside',
                   marker={'color': post_color},
                   legend="legend2"
                   ), row=2, col=1,
            # secondary_y=False
        )

        # Here we modify the tickangle of the xaxis, resulting in rotated labels.
        fig.update_layout(barmode='stack',  # barmode='group',
                          # bargap=0.15,
                          # scattermode="group",
                          # showlegend=False,
                          scattermode="overlay",
                          # bargroupgap=0,
                          # xaxis_tickangle=-45,
                          # legend1=dict(yanchor="top", y=0.99, xanchor="left",x=0.01),
                          # legend2=dict(yanchor="top", y=0.99, xanchor="left",x=0.01),
                          legend1=dict(y=0.99, x=0.01),
                          legend2=dict(y=0.43, x=0.01),
                          title=dict(text=f'{self._c_net_desc}')
                          )
        fig.show()


def run(args):
    """Main function"""  # noqa: DAR101,DAR201,DAR401

    lvl = logging.WARNING
    if args.verbosity > 0:
        lvl = logging.INFO
    if args.debug:
        lvl = logging.DEBUG

    if args.log is None:
        args.log = Path(__file__).stem + '.log'
    elif isinstance(args.log, str) and args.log == 'no-log':
        args.log = None

    logger = get_logger(level=lvl, color=not args.no_color,
                        filename=args.log, with_prefix=False)

    logger.info('%s (version %s)', __title__, __version__)
    logger.info('Creating date : %s', datetime.now().ctime())

    c_npu_network = None
    try:
        c_npu_network = CNpuNetworkDesc(args.cfile, logger=logger)
    except ErrorException as e:
        logger.info('')
        logger.warning(e)
    logger.info('')

    logger.info('Creating AiRunner session with `%s` descriptor', str(args.desc))
    runner = AiRunner(debug=args.debug, logger=logger)
    runner.connect(args.desc)

    if not runner.is_connected:
        msg_err_ = f'{runner.get_error()}'
        logger.error(msg_err_)
        msg_err_ = 'COM port is already opened or the --desc/-d option'
        msg_err_ += f' "{args.desc}" is not a valid path/descriptor'
        logger.error(msg_err_)
        return 1

    logger.info(runner)

    c_name = runner.names[0] if not args.name else args.name
    if c_name not in runner.names:
        msg_err_ = f'c-model "{c_name}" is not available'
        logger.error(msg_err_)
        return 1

    session: AiRunnerSession = runner.session(c_name)
    session.summary(print_fn=logger.info, indent=1)

    profiler = AiRunnerProfiler(session, c_network_desc=c_npu_network, logger=logger)
    profiler.profile(batch_size=args.batch, debug=args.debug)

    profiler.summary()

    if args.plot:
        profiler.plot()

    runner.disconnect()

    return 0


def main():
    """Main function to parse the arguments"""  # noqa: DAR101,DAR201,DAR401

    parser = argparse.ArgumentParser(description='AI runner')

    parser.add_argument('--desc', '-d', metavar='STR', type=str,
                        help='description', default=_DEFAULT)
    parser.add_argument('--batch', '-b', metavar='INT', type=int,
                        help='batch_size', default=1)
    parser.add_argument('--cfile', '-c', metavar='STR', type=str, help='generated c-file',
                        default=_DEFAULT_NETWORK_FILE_PATH)
    parser.add_argument('--name', '-n', metavar='STR', type=str,
                        help='c-model name', default=None)
    parser.add_argument('--log', metavar='STR', type=str, nargs='?',
                        help='log file', default='no-log')
    parser.add_argument('--verbosity', '-v',
                        nargs='?', const=1,
                        type=int, choices=range(0, 3),
                        help="set verbosity level",
                        default=1)
    parser.add_argument('--debug', action='store_true', help="debug option")
    parser.add_argument('--plot', action='store_true', help="plot")
    parser.add_argument('--no-color', action='store_const', const=1,
                        help='Disable log color support')

    args = parser.parse_args()

    return run(args)


if __name__ == '__main__':
    sys.exit(main())
