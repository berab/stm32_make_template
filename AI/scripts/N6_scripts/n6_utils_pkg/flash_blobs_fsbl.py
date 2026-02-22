from enum import Enum
from pathlib import Path
from dataclasses import dataclass
import intelhex
from typing import List, Tuple
from functools import partial
import logging
import struct

from n6_utils_pkg.c_file import CFile

logging.basicConfig(level=logging.DEBUG)
DEFAULT_ALIGNMENT = 5 # Data aligned on 0x20 addresses

def get_next_aligned_address(addr:int, alignment:int) -> int:
    """
    Returns the next address that is aligned with the given alignment arg
    -- If the current address is already aligned, return it --

    Parameters
    ----------
    addr : int
        Current address to work from
    alignment : int
        Alignment to be found (i.e. find the next address after addr that is aligned with 1<<alignment )

    Returns
    -------
    int
        The address aligned correctly
    """
    # Alignment = nb of bits
    #print(f"{get_next_aligned_address(0x489764548,0x40):#x}")
    if addr % (1<<alignment) == 0:
        return addr
    v = addr >> alignment
    v += 1
    v = v << alignment
    return v

# Default alignment function
align_addr = partial(get_next_aligned_address, alignment=DEFAULT_ALIGNMENT)

def bytes_to_dict(offset:int, data:bytes):
    return {offset+i:k for i,k in enumerate(data)}

class DataBlob:
    """
    Contains data from _one_ .raw file to be placed in flash
    The structure is as follows:
    HEADER: 
            - magic word (4B) : "AIDB" (ai datablob)
            - Offset (32b) : destination address = "self.dest_addr"
            - Size (32b)   : in bytes - size of the data
            - is_last(8b)  : Is this blob the last one ? 
            - Type (8b)    : TYPE_xxx
            - NextBlob(32b): Offset to the next blob
            - Padding      : so that data is properly aligned on 0x04
    DATA (contents of the RAW file)
    Padding
    """
    class BlobType(Enum):
        TYPE_STD   = 0x01
        TYPE_ZEROS = 0xAA

    def __init__(self, filen: Path, blob_offset: int=None, destination_offset:int=None):
        self.data = filen.read_bytes()
        # Handle the case where all values are zeros
        if all(self.data) == 0:
            self.data = struct.pack("<I", len(self.data))
            self.type = self.BlobType.TYPE_ZEROS
        else:
            self.type = self.BlobType.TYPE_STD
        self.blob_offset = blob_offset
        self.dest_addr = destination_offset    # Destination offset is the address in internal ram for example
        self.is_last = True
        self.next = 0                          # address of the next data blob
        self.padding_len = 0
        self.hdr_padding_len = 0
        self.update_paddings()
    
    def set_next(self, next_offset:int):
        self.next = next_offset

    def get_offset(self) -> int:
        return self.blob_offset
    
    def get_length(self) -> int:
        return len(self.dump())

    def get_header(self, padding:bool=True) -> bytes:
        data = b"--DATABLOB--" + struct.pack("<ccccIIBB", b"A", b"I", b"D", b"B", self.dest_addr, len(self.data), self.is_last, self.type.value)
        data = struct.pack("<ccccIIIBB", b"A", b"I", b"D", b"B", self.dest_addr, len(self.data), self.next, self.is_last, self.type.value)
        if padding is True:
            return data + b"X" * self.hdr_padding_len
        else:
            return data

    def update_paddings(self):
        """
        Update all paddings needed to dump the current object
        (There is one padding after the header + one padding after data)
        """
        addr = len(self.get_header(padding=False))
        self.hdr_padding_len = get_next_aligned_address(addr, 0x04) - addr
        addr = len(self.get_header() + self.data)
        self.padding_len = align_addr(addr) - addr


    def dump(self, silent:bool = True, base_addr:int = 0) -> bytes:
        data = self.get_header() + self.data + b"X"*self.padding_len
        if silent is False:
            s = f"\t\tDatablob @ {base_addr + self.blob_offset:#x}, destination: {self.dest_addr:#x}, full size: {len(data):#x}, type={self.type.name}, last={self.is_last}/ next @ {base_addr + self.next:#x} / hdrpad: {self.hdr_padding_len}"
            if self.type == self.BlobType.TYPE_ZEROS:
                s += f"""/ {struct.unpack("<I", self.data)[0]:,d} zeroed-out bytes"""
            logging.debug(s)
        return data


class ModelBlob:
    """
    Contains all data for one model (list of datablobs + possible additional data)
    The structure is as follows:
    - HEADER
        - ptr to the first blob
        - padding
    - Datablobs one after another
    """
    def __init__(self, start_address:int):
        self.db_list:List[DataBlob] = []
        self.start_address = start_address
        self.hdr_padding_len = 0
        self.update_padding()
    
    def add_datablob(self, filen:Path, offset:int):
        """
        Computes the address of the next blob, adds it to the current list
        Data blobs are aligned on DEFAULT_ALIGNMENT
        """
        lastblob:DataBlob = None
        current_addr = len(self.get_header()) #Address of the blob is "relative to the current Model blob address"
        # read previous offset and previous blob length, align the new address to DEFAULT_ALIGNMENT
        if len(self.db_list) != 0:
            lastblob = self.db_list[-1]
            lastblob.is_last = False
            current_addr = lastblob.get_offset() + lastblob.get_length()    # this address is already padded to be aligned correctly
            lastblob.set_next(current_addr)     # Set the pointer of the previous blob to the current one being created
        new_addr = align_addr(current_addr)     # Just ensure everything is aligned (should be useless)
        self.db_list.append(DataBlob(filen, blob_offset=new_addr, destination_offset=offset))
        
    def get_end_address(self) -> int:
        """
        Computes the end address of the current model blob, this can be useful for higher-level objects
        """
        if len(self.db_list) != 0:
            lastblob = self.db_list[-1]
            rv = self.start_address + lastblob.get_offset() + lastblob.get_length()
        else:
            rv = self.start_address + len(self.get_header())
        return rv
    
    def update_padding(self):
        addr = len(self.get_header(padding=False))
        self.hdr_padding_len = align_addr(addr) - addr

    def get_header(self, padding:bool=True) -> bytes:
        """
        Returns the header for the current ModelBlob

        Parameters
        ----------
        padding : bool, optional
            generate the header with padding(by default True) or without it (without padding can be useful for finding the padding length)

        Returns
        -------
        bytes
            Header
        """
        if len(self.db_list) != 0:
            first_blob_addr = self.db_list[0].get_offset()
        else:
            first_blob_addr = 0
        data = b"MODEL_BLOB:" + struct.pack("<I", first_blob_addr)
        data = struct.pack("<I", first_blob_addr)
        
        if padding is True:
            return data + b"X" * self.hdr_padding_len
        else:
            return data
    
    def get_size(self) -> int:
        return len(self.dump()) #self.get_end_address() - self.start_address
    
    def dump(self, silent:bool=True, base_addr:int=0) -> bytes:
        mdl_start_addr = base_addr + self.start_address
        if silent is False:
            logging.debug(f"\tMODELBLOB @ {mdl_start_addr:#x} --> {base_addr+self.get_end_address():#x} (padding {self.hdr_padding_len})")
        b = bytearray(self.get_header())
        for k in self.db_list:
            # all datablobs are aligned, just copy them side by side 
            b += k.dump(silent, base_addr=mdl_start_addr)
        return bytes(b)

@dataclass
class BTableRecord:
    """
    Represent one line of the "Models table"
    The structure is as follows:
            - model_id (32 chars)
            - Offset (32b) : Offset from start of table
            - Padding
    """
    blob: ModelBlob
    model_id: str
    offset: int
    padding_len: int = 0
    
    def __post_init__(self):
        """
        Model ID is cropped to 31 characters
        """
        if len(self.model_id) > 31:
            self.model_id = self.model_id[:31]

    @classmethod
    def empty_record(cls):
        """
        Creates an empty record
        """
        return cls(None, "Empty", 0)
    
    def is_empty(self) -> bool:
        return self.blob is None

    def dump(self, silent: bool=True, base_addr:int=0) -> bytes:
        """
        Dumps the current "line" of the table
        """
        bytes_id = bytes(self.model_id, encoding ="ascii") + b"\0"
        bytes_id = bytes_id + b"*"*(32-len(bytes_id))
        #bytes_id = bytes(f"{self.model_id:>32s}", encoding="ascii")
        hdr = bytes_id + struct.pack("<I", self.offset)
        self.padding_len = align_addr(len(hdr)) - len(hdr)
        data = hdr + b"X" * self.padding_len
        if silent is False:
            logging.debug(f"Table record@{base_addr:#10x}: ID={self.model_id:>32s}, offset= {self.offset:#10x}, size = {self.get_blob_size():#10x} - padding {self.padding_len}")
        return data

    def get_blob_size(self) -> int:
        if self.blob is None:
            return 0
        else:
            return self.blob.get_size()
    
    def get_offset(self) -> int:
        return self.offset

    def get_id(self) -> str:
        return self.model_id
    
    def get_model_blob(self) -> ModelBlob:
        return self.blob


class BlobsTable:
    TABLE_SIZE = 10 # at most 10 models in there...
    def __init__(self):
        self.table: List[BTableRecord] = [BTableRecord.empty_record() for _ in range(self.TABLE_SIZE)]
        self.padding_len = 0
        self.update_hdr_padding_len()

    def get_last_blob_idx(self) -> int:
        idx = -1
        for k in self.table:
            if k.is_empty() is True:
                break
            else:
                idx += 1
        return idx
    
    def get_next_blob_address(self) -> int:
        """
        When adding a new model to the current table, it is needed to know
        where to store the next model, 
        """
        last_blob_idx = self.get_last_blob_idx()
        if last_blob_idx == - 1:
            # First blob
            addr = len(self.dump())                         # Use relative addresses
            addr = align_addr(addr)
        else:
            k = self.table[last_blob_idx]
            addr = k.get_blob_size() + k.get_offset()
        return addr

    def add_blob(self, model_id:str) -> ModelBlob:
        """
        Add a model to the current table
        """
        blob_addr = self.get_next_blob_address()
        b = ModelBlob(start_address=blob_addr)
        # find the first empty slot
        for k in range(self.TABLE_SIZE):
            if self.table[k].is_empty():
                self.table[k] = BTableRecord(b, model_id, blob_addr)
                break
        return b

    def update_hdr_padding_len(self):
        self.padding_len = align_addr(len(self.get_header())) - len(self.get_header())
    
    def get_header(self) -> bytes:
        hdr = b"BLOBSTABLE:" + struct.pack("<B", self.padding_len)
        hdr = b""#struct.pack("<B", self.padding_len)
        return hdr

    def dump(self, silent:bool=True, base_addr:int=0) -> bytes:
        if silent is False:
            logging.debug(f"==== Table @ {base_addr:#x} ====")
        img = bytearray()
        img += self.get_header()
        img += b"X" * self.padding_len
        for k in self.table:
            img += k.dump(silent, base_addr + len(img))
        return img
    
    def get_models(self) -> Tuple[str, ModelBlob]:
        """
        Generator returning each (model_id, ModelBlob) not empty present in the table
        """
        for m in self.table:
            if m.is_empty() is True:
                #raise StopIteration
                return
            else:
                yield m.get_id(), m.get_model_blob()

class GenuineAtonnBlocks:
    def __init__(self):
        self.data = {}
    
    def add_block(self, address:int, data:bytes):
        # Sanity check
        if type(address) not in [int] or address < 0:
            raise ValueError(f"{type(self).__name__}: When adding a raw atonnc block - address is not valid: {address}")
        # ensure there is no overlap, or issue a warning
        if self.overlaps(address, len(data)):
            logging.error("Overlapping flash atonn blocks ! Overriding data - This will most likely fail at some point...")
        self.data[address] = bytes(data)
    
    def overlaps(self, address:int, size:int) -> bool:
        """
        Assesses whether the block passed in argument overlaps some of the blocks contained in self

        Parameters
        ----------
        address : int
            Start address of the block
        size : int
            size of the block

        Returns
        -------
        bool
            is there an overlap between some of the blocks & the argument
        """
        max_addr = address + size
        for k, v in self.data.items():
            max_item_addr = k + len(v)
            # overlap if address < k and max_addr > k or  max_item_addr > address > k 
            if (address <= k and max_addr >= k) or (address >= k and address <= max_item_addr):
                return True
        return False
    
    def get_data(self):
        return self.data
    

class FlashImage:
    """
    Contains table + blobs
    A flash image should be flashed @ an address aligned with 0x4
    """
    BASE_ADDR = 0x7000_0000
    def __init__(self,base_addr:int=0x7000_0000):
        self.current_address = base_addr
        self.padding_len = 0
        self.table_offset = 0 
        self.update_padding_len()
        self.table_offset = len(self.get_header())
        self.table:BlobsTable = BlobsTable()
        self.raw_data = GenuineAtonnBlocks()

    def add_network(self, filename:Path, memory_initializers_path:Path, net_name:str=None):
        """
        Add a network to the current flash image
        Only memory initializers present in memory_initializers_path and created ~ the same time as the network.c
            will be added to the current flash image.
            
        Parameters
        ----------
        filename : Path
            Path to the network.c file
        memory_initializers_path : Path
            Path to where the memory initializers are located
        net_name : str
            Name of the network to set in the blobs table
        """
        if net_name is None:
            table_entry_name = filename.name
        else:
            table_entry_name = net_name
        blb = self.table.add_blob(table_entry_name)
        cf = CFile(filename)
        mempool_offsets = cf.get_all_offsets()
        mempool_suffixes = list(mempool_offsets.keys())
        file_pfx = cf.get_cname()
        for mf in memory_initializers_path.glob(f"**/{file_pfx}_*"):
            if abs(mf.stat().st_mtime - cf.get_mtime()) < 10:
                mem_file_type = mf.suffixes[0][1:].upper()  # get memory pool from file extension
                # try to ensure the file is really a memory "dump" file (as there is no way for the "c_file" to know exactly the name of the file...)
                # This is done by looking whether the memory_pool suffix is part of the name.... (not 100% faultproof)
                if mem_file_type not in mempool_suffixes:
                    continue
                offset = int(mempool_offsets[mem_file_type], base=16)
                # Only add data that is not meant to be fetched from flash in the blob !
                if (offset < 0x7000_0000) or (offset >= 0x7400_0000):
                    blb.add_datablob(mf, offset)
                else:
                    self.raw_data.add_block(address=offset, data=mf.read_bytes())

    def update_padding_len(self):
        self.padding_len = align_addr(len(self.get_header(padding=False))) - len(self.get_header(padding=False))
    
    def get_header(self, padding:bool=True) -> bytes:
        """
        Header :
            Address of the table [1 uint32_t]
        """
        hdr = struct.pack("<B", self.table_offset)
        if padding is True:
            hdr += b"X" * self.padding_len
        return hdr
    
    def dump(self, silent=False) -> bytes:
        if silent is False:
            logging.debug(f"==== START ====")
        d = bytearray()
        d += self.get_header()
        d += self.table.dump(silent=silent, base_addr=self.current_address + len(d))
        models_address = self.current_address
        if silent is False:
            logging.debug(f"==== Models details ====")
        for bid, b in self.table.get_models():
            # b is a BTable Record
            if silent is False:
                logging.debug(f"\t== {bid:^32s} ==")
            d += b.dump(silent=silent, base_addr=models_address)
        if silent is False:
            logging.debug(f"==== END ====")
        return d
    
    def dump_hex(self, f:Path):
        ihex_bytes_field_len = 32
        total_size = 0
        ih = intelhex.IntelHex()
        logging.debug(f"==== HEX contents ====")
        build_image = bytes(self.dump(silent=True))
        for addr, data in self.raw_data.get_data().items():
            total_size += len(data)
            logging.debug(f"""({"RAW DATA":^10s}) @ {addr:#10x} - {len(data)/1024:10,.3f} kB""")
            ih.fromdict(bytes_to_dict(addr, data))
        if self.raw_data.overlaps(self.current_address, len(build_image)):
            logging.error("Overlapping flash atonn blocks with inner-memory blocks - Overriding data - This will most likely fail at some point...")
        
        total_size += len(build_image)
        logging.debug(f"""({"BLOB":^10s}) @ {self.current_address:#10x} - {len(build_image)/1024:10,.3f} kB""")
        logging.debug(f"""--------------""")
        ihex_size = total_size / ihex_bytes_field_len #nb of lines : all lines seems to contain 0x10 bytes of data
        ihex_size = ihex_size * (9 + ihex_bytes_field_len*2 + 2 + 2)    # 9= control chars 2=CRC 2=CR LF
        logging.debug(f"""({"TOTAL":^10s}) {total_size/1024:10,.3f} kB -- iHex size estimate: {ihex_size/1024:10,.3f} kB""")
        ih.fromdict(bytes_to_dict(self.current_address,build_image))

        ih.write_hex_file(f, byte_count=ihex_bytes_field_len)

def _main():
    data_dir = Path(__file__).parent / ".." / ".." / "DATA" / "my_test_fsbl_blobs"
    img = FlashImage()
    img.add_network(data_dir / "network.c", data_dir)
    img.add_network(data_dir / "yamnet_512_f32_quant_int8_int8_random_2__extflsh__1414.c", data_dir)
    
    with Path("toto.bin").open("wb") as f:
        f.write(img.dump())

if __name__ == "__main__":
    _main()

