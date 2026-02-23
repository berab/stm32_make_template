from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

class IHex():
    """
    Intel-Hex file representation object
    with utilities to retrieve info from it
    """
    @dataclass
    class Record:
        byte_count: int = 0
        address: int = 0
        record_type: int = 0
        data: str = ""
        checksum: int = 0

    def __init__(self, filepath:Path):
        self.file = filepath
    
    def _extract_line_fields(self, l:str) -> Record:
        """
        Extract fields of the Intel-hex file for a record given as argument

        The syntax of a record is as follows:
        :<byte_count:1B><address:2B><record_type:1B><data:byte_countB><checksum:1B>
        record_type can be something like an "instruction" or can indicate that the record holds data only
        Size of the data to be loaded on the target from the hex file is only contained in the data records
        """
        bc = int(l[1:3], 16)
        return self.Record(byte_count=bc,
                           address=int(l[3:7],16),
                           record_type=int(l[7:9],16),
                           data=l[9:9+2*bc],
                           checksum=l[9+2*bc:9+2*bc+2]
                           )

    def get_data_size(self) -> int:
        """
        Returns the size of the data (in bytes) found in the Intel-hex records

        Returns
        -------
        int
            Size of the data in bytes
        """
        size = 0
        with self.file.open() as f:
            content = f.readlines()
        # Sum size of data-records only
        for l in content:
            rec = self._extract_line_fields(l)
            if rec.record_type == 0:  # 0 = data record
                size = size + rec.byte_count
        return size