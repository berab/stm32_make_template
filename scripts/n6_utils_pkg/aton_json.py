from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Mapping, Tuple, List, Any
import copy
import json
import re

def format_size(size: int) -> str:
    """
    Converts an integer to a string representing the size of a memory

    Parameters
    ----------
    size : int
        Size of the memory in bytes

    Returns
    -------
    str
        String representing the memory size with proper prefixes
    """
    if size >= 1024 ** 2:
        return f"""{size/(1024 ** 2):>10,.3f} MB"""
    elif size >= 1024:
        return f"""{size/1024:>10,.3f} kB"""
    else:
        return f"""{size:>10}  B"""


class EpochType(Enum):
    UNDEFINED  = auto()
    HARDWARE   = auto()
    SOFTWARE   = auto()
    MIXED      = auto()
    EPOCH_CTRL = auto()

    @classmethod
    def parse(cls, s):
        if s == "NODE_UNDEF":
            return cls.UNDEFINED
        elif s == "NODE_HW":
            return cls.HARDWARE
        elif s == "NODE_SW_HW":
            return cls.MIXED
        elif s == "NODE_SW":
            return cls.SOFTWARE
        elif s == "NODE_EC":
            return cls.EPOCH_CTRL
        else:
            return cls.UNDEFINED

    def __str__(self) -> str:
        return self.name
    
    def __repr__(self) -> str:
        return self.name

class BufferType(Enum):
    UNDEFINED  = auto()
    ACTIVATION = auto()
    WEIGHT     = auto()

    @classmethod
    def parse(cls, s:bool):
        if s == "activation":
            return cls.ACTIVATION
        elif s == "weight":
            return cls.WEIGHT
        else:
            return cls.UNDEFINED
    @classmethod
    def from_isparam(cls, s:bool):
        if s is True:
            return cls.WEIGHT
        elif s is False:
            return cls.ACTIVATION
        else:
            return cls.UNDEFINED

    def __repr__(self) -> str:
        return self.name
    def __str__(self) -> str:
        return self.__repr__()

class Address:
    """
    Represents an address (relative or absolute) and provide methods to handle both representations
    """
    class AddrType(Enum):
        RELATIVE = auto()
        ABSOLUTE = auto()

    _offset: int
    _atype: AddrType
    _base: int
    _base_symbol: str
    value:int       # Either a pure offset if the address type is relative or absolute value

    def __init__(self, base: Optional[int|str], offset:int):
        self._offset = offset
        if base.isdigit() is True:
            self._atype = Address.AddrType.ABSOLUTE
            self._base = int(base)
            self._base_symbol = "ABSOLUTE ADDRESS"
        else:
            self._atype = Address.AddrType.RELATIVE
            self._base = 0
            self._base_symbol = base
    
    @property
    def value(self):
        if self._atype == Address.AddrType.RELATIVE:
            return self._offset
        else:
            return self._base + self._offset
    
    def __add__(self, other:Address|int) -> Address:
        if isinstance(other, int):
            o = copy.deepcopy(self)
            o._offset += other
            return o
        if self._atype != other._atype:
            raise ValueError("Cannot add an absolute and a relative address")
        if self._atype == Address.AddrType.RELATIVE and self._base_symbol != other._base_symbol:
            raise ValueError("Cannot add relative addresses with different base symbol")
        if self._atype == Address.AddrType.RELATIVE:
            return Address(self._base_symbol, self._offset + other._offset)
        else: # Absolute address
            # bases can be different, chose the smallest one as the base
            b = min(self._base, other._base)
            offset = self.value + other.value - b
            return Address(b, offset)
    
    def __str__(self) -> str:
        return f"{self._atype.name} - {self.value:#x}"
    def __repr__(self) -> str:
        return f"{self._atype.name} - {self.value:#x}"


@dataclass
class MemoryMapping:
    """
    Class representing a list of non-overlapping ranges used in memory
    """
    used_ranges: List[Tuple[int, int]] = field(default_factory=list)

    def add_range(self, base: int, end: int):
        """
        Adds a new range in the mapping (possibly extending old existing ranges)

        Parameters
        ----------
        base : int
            start address of the range to add
        end : int
            end address of the range to add
        """
        # Set "end" to be aligned with 0x10
        end = end + (0x10 - (end % 0x10))
        # handle easy cases
        if not self.used_ranges:
            # empty list
            self.used_ranges.append((base, end))
        else:
            # at least one element in the list
            for idx, (i, j) in enumerate(self.used_ranges):
                if base < i and end < i:
                    # new range before the current index
                    self.used_ranges.insert(idx, (base, end))
                    break
                elif base > j:
                    if idx < len(self.used_ranges) - 1:
                        # to be placed after the current range
                        continue
                    else:
                        # last loop
                        self.used_ranges.append((base, end))
                else:
                    # then it is overlapping a range...
                    new_base = min(base, i)
                    new_end = max(end, j)
                    self.used_ranges[idx] = (new_base, new_end)
                    break

        # ensure there is no overlap, or merge ranges
        continue_looping = True
        while continue_looping:
            if len(self.used_ranges) <= 1:
                continue_looping = False
                break
            for k in range(1, len(self.used_ranges)):
                if self.used_ranges[k][0] <= self.used_ranges[k - 1][1]:  # Overlap

                    if self.used_ranges[k][1] >= self.used_ranges[k - 1][1]:  # Interesting overlap
                        # @TODO Take into account addresses not aligned to 0x04 ?
                        self.used_ranges[k - 1] = (self.used_ranges[k - 1][0], self.used_ranges[k][1])
                        self.used_ranges.pop(k)
                        break
                    elif self.used_ranges[k][1] <= self.used_ranges[k - 1][1]:  # Should not happen
                        self.used_ranges.pop(k)
                        break

            if k == len(self.used_ranges) - 1:
                continue_looping = False

    def get_size(self) -> int:
        """Returns the size (in bytes) of the current memory mapping"""  # noqa: DAR101,DAR201,DAR401
        return sum([e - i for i, e in self.used_ranges])

    def get_range_list(self) -> List[str]:
        """Returns a string representation of the used ranges"""  # noqa: DAR101,DAR201,DAR401
        rv = []
        for i, e in self.used_ranges:
            rv.append(f"0x{i:08X}-0x{e:08X}")
        return rv

    def get_range(self, desc: str) -> str:
        """Return a string representation of the ranges - prepending a descriptor to it"""  # noqa: DAR101,DAR201,DAR401
        s = f"\t{desc:15s} -- {str(self)}"
        return s

    def __str__(self) -> str:
        full_size = self.get_size()
        rv = f"Used size: {format_size(full_size)}"
        for i, e in self.used_ranges:
            rv += f"\n\t\t0x{i:8X} - 0x{e:8X} ({format_size(e - i)})"
        return rv

        
class InputModel:
    name: str
    signature: str
    n_params: int
    size: int
    
    @classmethod
    def parse_dict(cls, d:Mapping[str,Any]) -> InputModel:
        v = cls()
        d_model_files = d["model_files"][0]        # @TODO : remove - fix for current atonn files
        v.name = d_model_files["name"]
        v.signature = d_model_files["signature"]
        v.n_params = d["n_params"]
        v.size = d["size"]
        return v
    
    def __str__(self) -> str:
        return f"Model: {self.name} / Signature: {self.signature}"


class Tool:
    name: str
    version: str
    arguments: str
    environment: List[Any]
    input_model: InputModel

    @classmethod
    def parse_dict(cls, d:Mapping[str,Any]) -> Tool:
        obj = cls()           # Create new instance of class Tool
        obj.name = d["name"]
        obj.version = d["version"]
        obj.arguments = d["arguments"]
        obj.environment = d["environment"]
        obj.input_model = InputModel.parse_dict(d["input_model"])
        return obj

    def get_version(self) -> str:
        """
        Return the version of the tool as : "2.1.0-20122 162da6099" or "1.0.0-109 ...."
        """
        return self.version

    def get_arguments(self) -> str:
        """
        Return the arguments of the command aton or stedgeai
        """
        return self.arguments

class GraphEdge:
    # @TODO: implement
    ...


class GraphNode:
    name: str
    node_id: int
    inputs: List[int]       # Input Buffer IDs
    outputs: List[int]      # Output Buffer IDs
    scratchs: List[int]     # Scratch Buffer IDs
    subgraph_nodes: List[GraphNode]
    macc: str
    mapping: EpochType
    original_nodes: str
    type: str
    sw_functions: str

    @classmethod
    def parse_dict(cls, d:Mapping[str,Any]) -> GraphNode:
        gn = GraphNode()
        gn.name = d["name"]
        gn.node_id = d["id"]
        gn.inputs = d["inputs"]
        gn.outputs = d["outputs"]
        gn.scratchs = d["scratchs"]
        gn.mapping = EpochType.parse(d["mapping"])
        gn.type = d["type"]
        gn.macc = d["macc"]
        gn.subgraph_nodes = [GraphNode.parse_dict(gg) for gg in d["subgraph_nodes"]]
        return gn

    def get_sw_layer(self) -> str:
        """
        Return the name of the layer that is implemented in software (or None, otherwise)
        """
        if self.mapping == EpochType.SOFTWARE:
            # For software layers, details are found in the subgraph 1st node
            if self.type == "":
                return self.subgraph_nodes[0].get_sw_layer()
            else:
                return self.type.replace("Node kind=", "")
        else:
            return None

    def get_sw_layers_from_mixed(self) -> List[Optional[str]]:
        if self.mapping == EpochType.MIXED:
            # For mixed epochs, find subnodes that are of type SOFTWARE
            rv = []
            for n in self.subgraph_nodes:
                if n.mapping == EpochType.SOFTWARE:
                    rv.append(n.type.replace("Node kind=", ""))
            return rv
        else:
            return [None]

    def get_node_by_name(self, s:str) -> Optional[GraphNode]:
        """
        Returns a node with the name as argument contained in the current node, or None (not found)
        """
        if self.name == s:
            return self
        else:
            for sn in self.subgraph_nodes:
                v = sn.get_node_by_name(s)
                if v is not None:
                    return v
        return None

    def get_node_by_id(self, nid:str) -> Optional[GraphNode]:
        """
        Returns a node with the ID as argument contained in the current node, or None (not found)
        """
        if self.node_id == nid:
            return self
        else:
            for sn in self.subgraph_nodes:
                v = sn.get_node_by_id(nid)
                if v is not None:
                    return v
        return None


class Graph:
    name: str
    graph_id: int
    inputs: List[int]       # Graph Input Buffer IDs
    outputs: List[int]      # Graph Output Buffer IDs
    nodes: List[GraphNode]
    edges: List[GraphEdge]

    @classmethod
    def parse_dict(cls, d:Mapping[str,Any]) -> Graph:
        g = Graph()
        g.name = d["name"]
        g.graph_id = d["id"]
        g.inputs = d["inputs"]
        g.outputs = d["outputs"]
        g.nodes = [GraphNode.parse_dict(gg) for gg in d["nodes"]]
        g.edges = []
        return g

    def get_epoch_summary(self) -> Mapping[EpochType, int]:
        """
        Returns the number of epochs of each type
        """
        return {e: sum([n.mapping is e for n in self.nodes]) for e in EpochType}

    def get_epoch_sw_details(self) -> Mapping[str, int]:
        v = [n.get_sw_layer() for n in self.nodes]
        n_sw_epochs_by_name = {layer_name: sum([name==layer_name for name in v]) for layer_name in set(v)}
        if None in n_sw_epochs_by_name:
            n_sw_epochs_by_name.pop(None)
        return n_sw_epochs_by_name

    def get_epoch_mixed_sw_details(self) -> Mapping[str, int]:
        v = []
        for n in self.nodes:
            v += n.get_sw_layers_from_mixed()
        n_sw_epochs_by_name = {layer_name: sum([name==layer_name for name in v]) for layer_name in set(v)}
        n_sw_epochs_by_name.pop(None)
        return n_sw_epochs_by_name

    def get_node_by_id(self, id_node:int) -> GraphNode:
        for k in self.nodes:
            v = k.get_node_by_id(id_node)
            if v is not None:
                return v
        raise ValueError(f"Cannot find node ID {id_node} in graph {self.name}")

    def get_node_by_name(self, name_node:str) -> GraphNode:
        for k in self.nodes:
            v = k.get_node_by_name(name_node)
            if v is not None:
                return v
        raise ValueError(f"Cannot find node {name_node} in graph {self.name}")

class Buffer:
    name: str
    buffer_id: int
    alignment: int
    _mpool_id: Optional[int]
    memory_pool: MemoryPool
    _offset_start: int       #  Offset from start of the memory pool
    size_bytes: int
    buffer_type: bool       #  Weight/activation
    flags: Optional[str]
    epochs: Mapping[str, int]
    shape: List[int]
    format: str
    nbits: int
    qmn: Mapping[str, int]
    intq: Mapping[str, Any]
    address: Address

    @classmethod
    def parse_dict(cls, d:Mapping[str,Any]) -> Buffer:
        v = cls()
        v.name = d["name"]
        v.buffer_id = d["id"]
        v.alignment = d["alignment"]
        v._mpool_id = d["mpool_id"]      
        v._offset_start = d["offset_start"]
        v.size_bytes = d["size_bytes"]
        v.buffer_type = BufferType.from_isparam(d["is_param"])
        v.flags = d["flags"]
        v.epochs = d["epochs"]
        v.shape = d["shape"]
        v.format = d["format"]
        v.nbits = d["nbits"]
        v.qmn = d["qmn"]
        #v.intq = d["intq"]
        return v

    def update_address(self):
        self.address = self.memory_pool.address + self._offset_start
    
    def force_memory_pool(self, mp:MemoryPool):
        self.memory_pool = mp
        self.update_address()
        
    def __str__(self) -> str:
        return f"(buffer {self.name}) [{self.buffer_type}]"
    
    def __repr__(self) -> str:
        return f"{self.name} @ {self.address} - {format_size(self.size_bytes)} - [{self.buffer_type}]"

class MemoryPool:
    # @TODO: implement (already done in the c-parsing package)
    name: str
    mempool_id: int
    alignment: int
    address: Address
    _offset_start: int
    size_bytes: int         # Size in the JSON file (does not include virtual memory pools contributions)
    used_size_bytes: int
    buffers: List[Buffer]
    virtual: bool

    memory_map_activations: MemoryMapping
    memory_map_weights: MemoryMapping

    @classmethod
    def parse_dict(cls, d:Mapping[str,Any]) -> MemoryPool:
        v = cls()
        v.name = d["name"]
        v.mempool_id = d["id"]
        v.alignment = d["alignment"]
        v.address = d["address"]
        v._offset_start = d["offset_start"]
        v.size_bytes = d["size_bytes"]
        v.used_size_bytes = d["used_size_bytes"]
        v.buffers = d["buffers"]
        if "virtual" in d:
            v.virtual = bool(d["virtual"])
        else:
            v.virtual = False

        if v.address.isdigit():
            # The memory pool is absolute.
            v.address = Address(v.address, v._offset_start)
        else:
            # The memory pool is "relative"-addressed: use its name as the base symbol / offset_start should be 0
            v.address = Address(v.name, v._offset_start)
        return v

    def get_activations_size_bytes(self) -> int:
        return sum([b.size_bytes for b in self.buffers if b.buffer_type == BufferType.ACTIVATION])

    def get_weights_size_bytes(self) -> int:
        return sum([b.size_bytes for b in self.buffers if b.buffer_type == BufferType.WEIGHT])

    def add_buffer(self, b:Buffer):
        self.buffers.append(b)

    def add_buffer_by_split(self, b:Buffer):
        """
        if the buffer overlaps the current mpool, take only the part that is overlapping the memorypool
        and adds it to the memory pool. The name of the buffer is suffixed by the mpool name.
        """
        if self.address is None:
            # Warning NotImplementedError("Using relative addresses for memory pool is not handled when splitting buffers")
            return
        # Get "absolute" addresses if possible ( @TODO this is dirty, to be improved)
        mp_start = self.address.value
        mp_end = mp_start + self.size_bytes
        b_start = b.address.value
        b_end = b_start + b.size_bytes
        # case 1: b_start <= mp_start and b_end >= mp_end (buffer fully overlaps)
        if b_start <= mp_end and b_end >= mp_start:
            ba = copy.deepcopy(b)
            ba.name = ba.name + "__SPLIT__" + self.name
            # First, keep absolute addresses everywhere to compute sizes
            if b_start < mp_start:
                ba._offset_start = mp_start   # Offset from this mpool start is 0 (mpstart is removed later on)
            else:
                ba._offset_start = b_start

            if b_end < mp_end:  # buffer in the current mpool
                ba.size_bytes = b_end - ba._offset_start
            else: # buffer ends after the current mpool
                ba.size_bytes = mp_end - ba._offset_start
            # After computing sizes, remove "mp_start" from start offset of the buffer
            ba._offset_start -= mp_start
            # Update memory pool associated with this split buffer
            ba.force_memory_pool(self)
            #print(f"Adding buffer {ba.name} after split to {self.name} [{ba.address.value:#x} - {ba.address.value + ba.size_bytes:#x}] size = {format_size(ba.size_bytes)}")
            self.add_buffer(ba)
        else:
            #buffer not in the current mpool do nothing
            pass

    def update_memory_map(self):
        self.memory_map_weights = MemoryMapping()
        self.memory_map_activations = MemoryMapping()
        for b in self.buffers:
            b_s = b.address.value
            b_e = b_s + b.size_bytes
            if b.buffer_type == BufferType.ACTIVATION:
                self.memory_map_activations.add_range(b_s, b_e)
            elif b.buffer_type == BufferType.WEIGHT:
                self.memory_map_weights.add_range(b_s, b_e)       
        #print(f"Updated memory mapping - {self.name}: {self.memory_map.get_size()/1000.0} kB")

    def __repr__(self) -> str:
        return f"{self.name} @ {self.address} - {format_size(self.size_bytes)}"

class Environment:
    tools: List[Tool]
    generated_model: Any
    network_signature: str
    device: Optional[str]
    test_name: Optional[str]

    @classmethod
    def parse_dict(cls, d:Mapping[str,Any]) -> GraphNode:
        v = cls()
        v.tools= [Tool.parse_dict(dd) for dd in d["tools"]]
        v.generated_model = d["generated_model"]
        #v.network_signature = d["network_signature"]
        return v

    def get_tool(self, name:str) -> Tool:
        for t in self.tools:
            if name == t.name:
                return t
        return None

    def get_model(self) -> InputModel:
        # The model info is extracted from stedgeai if possible / ATONN compiler otherwise
        if (t:=self.get_tool("ST.EdgeAI.Core")) is not None:
            return t.input_model
        elif (t:=self.get_tool("ATONN Compiler")) is not None:
            return t.input_model
        else:
            raise ValueError("No valid tool information found to extract model info")
        
    @property
    def get_version_atonn(self) -> str:
        return self.get_tool("ATONN Compiler").get_version()
    def get_version_stedgeai_core(self) -> str:
        return self.get_tool("ST.EdgeAI.Core").get_version()


class AtonJson:
    """
    JSON output file of the atonn compiler
    """
    json_version: str
    environment: Environment
    buffers: List[Buffer]
    graphs: List[Graph]
    memory_pools: List[MemoryPool]
    #memory_accesses: List[MemoryAccess]    # @TODO: implement
    #power_estimates: List[PowerEstimate]   # @TODO: implement
    # compiler_version:str

    def __init__(self, filename:Path):
        self.filename = filename
        self.data = json.loads(filename.read_bytes())
        self._reorganize_data()

    def _reorganize_data(self):
        self.environment = Environment.parse_dict(self.data["environment"])
        self.graphs = [Graph.parse_dict(g) for g in self.data["graphs"]]
        self.buffers = [Buffer.parse_dict(g) for g in self.data["buffers"]]
        self.memory_pools = [MemoryPool.parse_dict(g) for g in self.data["memory_pools"]]
        # @TODO: Continue reading json data
        self._create_links()
        self._update_addresses()
        self._update_memory_maps()
        # WARNING: THIS STEP CANNOT BE UNDONE !!! (but allows to show proper memory mapping)
        self._split_virtual_memory_buffers()
        pass

    def _resolve_buffer_links(self, list_to_resolve:List[int], buffer_list: List[Buffer]):
        buffers_id = [k.buffer_id for k in buffer_list]
        for i, b_id in enumerate(list_to_resolve):
            try:
                idx = buffers_id.index(b_id)
                list_to_resolve[i] = buffer_list[idx]
            except ValueError as exc:
                raise ValueError(f'Cannot find buffer with ID = {list_to_resolve[i]}') from exc

    def _resolve_memory_pool_links(self):
        memory_pools_id = [k.mempool_id for k in self.memory_pools]
        for b in self.buffers:
            try:
                idx = memory_pools_id.index(b._mpool_id)
                b.memory_pool = self.memory_pools[idx]
            except ValueError as exc:
                raise ValueError(f'Cannot find memory pool with ID = {b.mpool_id}') from exc

    def _create_links(self):
        """
        For each element that  referencing other objects, resolve the link
        """
        def resolve_node(node:GraphNode, b_list:List[Buffer]):
            """Recursive resolving of buffer objects in graph nodes"""
            self._resolve_buffer_links(node.inputs, b_list)
            self._resolve_buffer_links(node.outputs, b_list)
            self._resolve_buffer_links(node.scratchs, b_list)
            for gn in node.subgraph_nodes:
                resolve_node(gn, b_list)

        # Memory pools contains references to buffers
        for m in self.memory_pools:
            self._resolve_buffer_links(m.buffers, self.buffers)

        # Buffers contain references to Memory pools
        self._resolve_memory_pool_links()

        # Graph have buffers as inputs and outputs
        for g in self.graphs:
            self._resolve_buffer_links(g.inputs, self.buffers)
            self._resolve_buffer_links(g.outputs, self.buffers)
            # Graph nodes have buffers input output
            for gn in g.nodes:
                resolve_node(gn, self.buffers)
    
    def _update_addresses(self):
        # resolve addresses of all buffers (make them absolute if possible)
        for b in self.buffers:
            b.update_address()

    def _update_memory_maps(self):
        # For each memory pool, compute the size of the pool based on buffers
        for mp in self.memory_pools:
            mp.update_memory_map()

    def _split_virtual_memory_buffers(self):
        """
        Unrecoverable step: splits all the buffers in virtual memory pools into smaller buffers
        that will fully fit into memory pool objects
        (this is used to compute the size used for each memory pool)
        """
        to_delete = []
        for vmp in self.memory_pools:
            if vmp.virtual is True:
                to_delete.append(vmp)
                for b in vmp.buffers:
                    # Split the buffer b into all mpools that are not virtual....
                    for mp in self.memory_pools:
                        if mp.virtual is False:
                            mp.add_buffer_by_split(b)
        # Remove virtual memory pools
        for k in to_delete:
            self.memory_pools.remove(k)
        # Update sizes / ranges
        self._update_memory_maps()

    def get_memory_summary(self) -> str:
        arr = []
        for mp in self.memory_pools:
            s = f"{mp.name:15s} {mp.address.value:#x} - {mp.address.value + mp.size_bytes:#x} - [{format_size(mp.used_size_bytes)} / {format_size(mp.size_bytes)}] : "
            activations_size = mp.memory_map_activations.get_size()
            weights_size = mp.memory_map_weights.get_size()
            s +=f"Activations: {format_size(activations_size)} Weights: {format_size(weights_size)}"
            arr.append(s)
        return "\n".join(arr)
    
    def get_model(self):
        return self.environment.get_model()

    def get_version_atonn(self) -> str:
        return self.environment.get_tool("ATONN Compiler").get_version()

    def has_atonn(self) -> bool:
        return self.environment.get_tool("ATONN Compiler") is not None

    def get_version_stedgeaicore(self) -> str:
        return self.environment.get_tool("ST.EdgeAI.Core").get_version()



def _main():
    obj = AtonJson((Path(__file__).parent / "MY_c_info.json").resolve())
    version_atonn = obj.get_version_atonn()
    version_stedgeaicore = obj.get_version_stedgeaicore()
    print(f"Atonn version: {version_atonn}")
    print(f"stedgeai core version: {version_stedgeaicore}")
    print(f"""Epochs:    {obj.graphs[0].get_epoch_summary()}""")
    print(f"""SW Epochs: {obj.graphs[0].get_epoch_sw_details()}""")
    def print_sec(s):
        sep = "*"*80
        print ("\n".join([sep, s, sep]))
    
    print_sec(f"Compiler version: {obj.environment.get_version_atonn}")
    print_sec(f"""Epochs:    {obj.graphs[0].get_epoch_summary()}""")
    print_sec(f"""SW Epochs: {obj.graphs[0].get_epoch_sw_details()}""")
    print_sec(f"""SW layers for HW_SW Epochs: {obj.graphs[0].get_epoch_mixed_sw_details()}""")
    # Get inputs of an epoch
    epc = obj.graphs[0].get_node_by_name("epoch_5")
    print_sec(f"""Name of buffers input of Epoch 5 {[e.name for e in epc.inputs]}""")
    # Get inputs of any node
    #epc = obj.graphs[0].get_node_by_name("Conv2D_313_off_bias_747")
    #print(f"""Name of buffers input of Conv2D_313_off_bias_747 {[str(e)+e.name for e in epc.inputs]}""")
    # Show memory pools summary
    print_sec(obj.get_memory_summary())
    # Get model info
    print_sec(str(obj.environment.get_model()))

if __name__ == "__main__":
    _main()