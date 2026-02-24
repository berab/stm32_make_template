from dataclasses import dataclass, field
from typing import Mapping, Any, List, Tuple
from pathlib import Path
import datetime
import json
import re

@dataclass
class MemoryPool:
    """
    Representation of a memory pool as cpuRAMx, npuRAMx, octoFlash
    """
    mem_type:       str = "NA"  # "Internal RAM", "External RAM", "External Flash"
    offset:         int = 0
    percent_used:   float = 0.0
    total_size:     int = 0
    used_size:      int = 0

    @classmethod
    def from_json(cls, dict_mempool):
        # Create an instance with initialized attributes from values of the dictionary
        self = cls( mem_type=    dict_mempool["Memory Type"],
                    offset=      dict_mempool["Offset"],
                    percent_used=dict_mempool["Percent used"],
                    total_size=  dict_mempool["Total size"],
                    used_size=   dict_mempool["Used Size"])
        return self
    
    def to_json(self) -> Mapping:
        d = {}
        d["Memory Type"] = self.mem_type
        d["Offset"] = self.offset
        d["Percent used"] = self.percent_used
        d["Total size"] = self.total_size
        d["Used Size"] = self.used_size

        return d


@dataclass
class MemoriesData:
    """
    Dictionary that contains all memory pools
    {cpuRAM:{MemoryPool}, npuRAM:{MemoryPool}, ...}
    """
    # Dictionary with keys as string and value is an object MemoryPool.
    mem_pools: Mapping[str, MemoryPool] = field(default_factory=dict)

    @classmethod    
    def from_json(cls, d):
        # Create an instance with initialized attributes from values of the dictionary
        self = cls()
        for k,v in d.items():
            self.mem_pools[k] = MemoryPool.from_json(v)
        return self
    
    def to_json(self) -> Mapping:
        d = {}
        for k,v in self.mem_pools.items():
            d[k] = v.to_json()
        return d
    
    def get_mem_size(self, mtype:str) -> int:
        """
        For each memory type passed as argument, retrieve the total size used in the current object.
        See MemoryMap of run_gen_validation_summary.py for the name of each pool ("Internal RAM CPU", etc...)
        mtype       Type of memory to calculate = "Internal RAM", "External RAM", "Internal Flash", "External Flash)
        Return      Sum of used sizes in bytes, for the given memory type

        """
        total = 0
        for key, value in self.mem_pools.items():
            if mtype in value.mem_type:     # e.g "Internal RAM" is in "Internal RAM CPU"
                total = total + value.used_size
        return total

    def get_mem_type(self, mtype:str) -> str:
        """
        Encodes the mtype given as argument as a "type" of memory used by the final json file
        mtype       Type of memory, "Internal RAM", "External RAM", "Internal Flash", "External Flash)
        Return      Short description of the memory type (matching power bi json spec)
        """
        # This method should return the type of memory by we don't know yet what it is
        if mtype == "External RAM":
            return "NA"
        elif mtype == "External Flash":
            return "NA"
        else:
            return "NA"


@dataclass
class Model:
    weight_compression: Any
    name:               str   # Model name
    full_name:          str
    nb_params:          int
    quantization_type:  str
    size:               int
    
    @classmethod
    def from_json(cls, d):
        # Create an instance with initialized attributes from values of the dictionary
        self = cls(weight_compression = d["Compression"],
                   name =               d["Name"],
                   full_name =          d["Full Name"],
                   nb_params =          d["Nb Params"],
                   quantization_type =  d["Quantization Type"],
                   size =               d["Size"])
        return self
    
    def to_json(self) -> Mapping:
        d = {}
        d["Compression"] = self.weight_compression
        d["Name"] = self.name
        d["Full Name"] = self.full_name
        d["Nb Params"] = self.nb_params
        d["Quantization Type"] = self.quantization_type
        d["Size"] = self.size
        return d
    
    def get_quantization_type(self) -> str:
        return self.quantization_type
    def get_weight_compression(self) -> str:
        return self.weight_compression


@dataclass
class Epochs:
    sw_count: int
    total_number: int
    hardware_epoch: Mapping[str, Any] = field(default_factory=dict) # Object dict with keys=str, values=any
    software_epoch: Mapping[str, Any] = field(default_factory=dict) # Object dict with keys=str, values=any
    first_epoch_hw: Mapping[str, Any] = field(default_factory=dict) # Object dict with keys=str, values=any


@dataclass
class ValidationData:
    # Init the object attributes with empty values
    date_time:      str
    device:         str
    runtime_library:str
    epochs:         Epochs = field(init=False)
    duration:       Mapping[str, float] = field(default_factory=dict) # Dictionary with keys=str, values=float
    inputs:         List[str] = field(default_factory=list) # List of string
    metrics:        List[Mapping[str, Any]] = field(default_factory=list) # List of dicts with keys=str, values=Any
    cpu_npu:        Mapping[str, Any] = field(default_factory=dict) # Dictionary with keys=str, values=Any (empty at init)
    outputs:        List[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, d):
        """
        Create an instance from values of a dictionary
        d   Dictionary Validation from json
        Return the instance
        """
        self = cls(date_time =  d["Date Time"],
                   device =     d["Device"],
                   runtime_library = d["RT Library"])
        # @TODO PARSE EPOCHS
        self.metrics =  d["Metrics"]
        self.duration = d["Duration"]
        self.epochs =   d["Epochs"]
        self.cpu_npu =  d["cpu_npu"]
        return self
    
    def to_json(self):
        # @TODO
        return {}

    def get_runtime_library(self) -> str:
        return self.runtime_library
    def get_avg_inference_time(self):
        return self.duration["avg"]

    def get_metrics(self) -> Tuple[str, str]:
        # type = "cos"
        # value = str(self.metrics[0][type])
        # return type, value
        return "NA", "0"

    def get_cpu_freq(self) -> str:
        return str(self.cpu_npu["cpu_freq"])
    def get_npu_freq(self) -> str:
        return str(self.cpu_npu["npu_freq"])

    def get_cpu_swctrl_percent(self) -> str:
        return self.cpu_npu["cpu_swctrl_percent"]
    def get_cpu_usage_percent(self) -> str:
        return self.cpu_npu["cpu_usage_percent"]
    def get_gpu_usage_percent(self) -> str:
        return self.cpu_npu["gpu_usage_percent"]
    def get_npu_usage_percent(self) -> str:
        return self.cpu_npu["npu_usage_percent"]


@dataclass
class VersionsData:
    cli:        Mapping[str, int] = field(default_factory=dict)     # Dictionary with key-value of type str-int
    tools:      str = ""
    tools_api:  Mapping[str, int] = field(default_factory=dict)     # = major, minor, micro, extra
    compiler:   Mapping[str, int] = field(default_factory=dict)     # = major, minor, micro, extra

    @classmethod
    def from_json(cls, dict):
        # Create an instance with initialized attributes from values of the dictionary
        self = cls(cli      = dict["CLI"],
                   tools    = dict["Tools"],
                   tools_api= dict["Tools API"],
                   compiler = dict["atonn Compiler"])
        return self

    def to_json(self):
        # @TODO
        return {}

    def get_cli_str(self) -> str:
        return f"""st_ai CLI - v{self.cli["major"]:d}.{self.cli["minor"]:d}.{self.cli["micro"]:d}"""

    def get_tools_str(self) -> str:
        return self.tools

    def get_compiler_str(self) -> str:
        return f"""atonn-v{self.compiler["major"]:d}.{self.compiler["minor"]:d}.{self.compiler["micro"]:d}-{self.compiler["extra"]}"""


@dataclass
class RunValidationJson:
    # -------------------------------------------------------------------------
    # Represent an object run of a model from summary.json
    # -------------------------------------------------------------------------
    compile_options:str
    model:          Model = field (init=False)          # Attribut is an instance of class Model
    validation:     ValidationData = field (init=False)
    versions:       VersionsData = field (init=False)
    memories:       MemoriesData = field(init=False)
    memory_usage:   Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """
        That method is called after the object has been initialized with its attributes
        """
        # Remove compilation options : --load-mpool-file file.mpool and --load-mdesc-file file.mdesc
        self.compile_options = re.sub("--load-m(pool|desc)-file [^ ]+ ", "", self.compile_options)
        # Remove compilation options below
        # self.compile_options = re.sub("(--continue-on-errors|--all-buffers-info|--mapping-recap) ","", self.compile_options)
        pass


    @classmethod
    def from_dict(cls, dict_run_json):
        """
        Return an object RunValidationJson initialized with data from a run from summary.json
        dict_run_json      A dictionary run from summary.json
        """
        run_validation = None
        # Create object and store data into attributs
        if "Validation" in dict_run_json:
            run_validation = cls(compile_options = dict_run_json["Compile options"])
            run_validation.memories = MemoriesData.from_json(dict_run_json["Memories"])
            for k, v in dict_run_json["Memory Usage"].items():
                run_validation.memory_usage[k] = v
            run_validation.model = Model.from_json(dict_run_json["Model"])
            run_validation.validation = ValidationData.from_json(dict_run_json["Validation"])
            run_validation.versions = VersionsData.from_json(dict_run_json["Versions"])
        return run_validation


    def to_dict(self):
        """
        Create and fill a dict from the object - NOT USED
        """
        d = {}
        d["Compile options"] = self.compile_options
        d["Memories"] = {}
        d["Memory Usage"] = {}
        for k,mem_desc in self.memories.items():
            d["Memories"][k] = mem_desc.to_json()
        for k,v in self.memory_usage.items():
            d["Memory Usage"][k] = v
        d["Model"] = self.model.to_json()
        d["Validation"] = self.validation.to_json()
        d["Versions"] = self.versions.to_json()
    
    def get_unknown_str(self) -> str:
        return "NA"

    def get_model_name(self) -> str:
        return self.model.full_name

    def get_engine(self) -> str:
        return "npu"

    def get_compilation_options(self) -> str:
        return self.compile_options

    # validation
    def get_run_date(self) -> str:
        return self.validation.date_time
    def get_cpu_freq(self) -> str:
        return self.validation.get_cpu_freq()
    def get_npu_freq(self) -> str:
        return self.validation.get_npu_freq()

    def get_cpu_swctrl_percent(self) -> str:
        return self.validation.get_cpu_swctrl_percent()
    def get_cpu_usage_percent(self) -> str:
        return self.validation.get_cpu_usage_percent()
    def get_gpu_usage_percent(self) -> str:
        return self.validation.get_gpu_usage_percent()
    def get_npu_usage_percent(self) -> str:
        return self.validation.get_npu_usage_percent()

    def get_runtime(self) -> str:
        return self.validation.get_runtime_library()

    def get_inference_time_us(self) -> str:
        avg_ms = self.validation.get_avg_inference_time()
        avg_us = int(1000 * avg_ms)
        return str(avg_us)

    def get_metrics(self) -> Tuple[str, str]:
        return self.validation.get_metrics()

    def get_os(self) -> str:
        return self.get_unknown_str()

    # versions
    def get_tool_version(self) -> str:
        return self.versions.get_tools_str()

    def get_compiler_version(self) -> str:
        return self.versions.get_compiler_str()
    def get_ais_package(self) -> str:
        return self.versions.get_cli_str()

    def get_quant_type(self) -> str:
        return self.model.get_quantization_type()

    def get_sw_stack(self) -> str:
        return self.get_unknown_str()

    def get_weight_compression(self) -> str:
        return str(self.model.get_weight_compression())

    # memories usage
    def get_int_ram_usage(self) -> str:
        return str(self.memories.get_mem_size("Internal RAM"))
        #return str(self.memory_usage["ram_int"])

    def get_int_flash_usage(self) -> str:
        return str(self.memories.get_mem_size("Internal Flash"))

    def get_ext_ram_usage(self) -> str:
        return str(self.memories.get_mem_size("External RAM"))

    def get_ext_flash_usage(self) -> str:
        return str(self.memories.get_mem_size("External Flash"))


    def get_ext_ram_type(self) -> str:
        return self.memories.get_mem_type("External RAM")
    def get_ext_flash_type(self) -> str:
        return self.memories.get_mem_type("External Flash")


    def get_mA(self) -> str:
        return self.get_unknown_str()
    def get_voltage(self) -> str:
        return self.get_unknown_str()
    def get_joule(self) -> str:
        return self.get_unknown_str()


class ValidationJSON:
    # -------------------------------------------------------------------------
    # First object to create by reading validation_summary.json
    # data attribut contains a list of runs for each model as:
    # "model1":[ {RunValidationJson}, {RunValidationJson} ]
    # "model2":[ {RunValidationJson}, {RunValidationJson} ]
    # -------------------------------------------------------------------------

    def __init__(self):
        # Constructor of the class.
        # Create the dict data that will contain all keys model name and the value is list of RunValidationJson
        self.data = {}
    
    @classmethod
    def from_json(cls, file:Path):
        """
        Create an instance and read the dict from the json input file.
        file    Input json file
        Return the object oValidationJSON that contains the list of run for all models
        """
        # Create new instance of object
        self = cls()

        # Init dict data with dict from json file
        with file.open() as f:
            self.data = json.load(f)

        # Loop on each key model, the value is a list of runs into the model
        for model_name_json, list_runs_json in self.data.items():
            list_runs_out = []

            # Loop on each json run, create an object run and add to the list of current model
            for run in list_runs_json:
                obj_run = RunValidationJson.from_dict(run)
                if obj_run is not None:
                    list_runs_out.append(obj_run)

            self.data[model_name_json] = list_runs_out

        return self


    def items(self) -> Tuple[str, List[RunValidationJson]]:
        for k, v in self.data.items():
            yield k, v


if __name__ == "__main__":
    d={
            "Compile options": "--continue-on-errors --all-buffers-info --cache-maintenance --Oauto-sched --load-mdesc-file N6_4A_mid --load-mpool-file stm32n6__all_except_FMC --enable-virtual-mem-pools --native-float --optimization 3 --Os --Omax-ca-pipe 4 --Ocache-opt --mapping-recap  ",
            "Memories": {
                "npuRAM3": {
                    "Offset": 874512384,
                    "Percent used": 1.7924107142857142,
                    "Total size": 458752,
                    "Used Size": 8222
                },
                "octoFlash": {
                    "Offset": 1879048192,
                    "Percent used": 0.030731201171875,
                    "Total size": 67108864,
                    "Used Size": 20623
                }
            },
            "Memory Usage": {
                "ROM": 20476
            },
            "Model": {
                "Compression": None,
                "Name": "mnist_int8_io_i8",
                "Nb Params": 20410,
                "Quantization Type": "ss/sa per-channel",
                "Size": 20476
            },
            "Validation": {
                "Date Time": "Thu Apr 20 14:39:51 2023",
                "Device": "STM32N6",
                "Duration": {
                    "avg": 0.475,
                    "hwrun": 0.3492871904629187,
                    "max": 0.479,
                    "min": 0.475,
                    "std": 0.475,
                    "swcleanup": 0.14412898408207694,
                    "swprog": 0.5065838254550044
                },
                "Epochs": {
                    "SW count": 3,
                    "Total number": 8,
                    "epoch": {
                        "Total": 5,
                        "Total ratio": 0.625
                    },
                    "epoch (SW)": {
                        "Total": 3,
                        "Total ratio": 0.375
                    },
                    "first_epoch_hw": {
                        "percent": "7.8%",
                        "time": "0.158 ms"
                    }
                },
                "Inputs": [
                    "Input_0_out_0       :   Input_0_out_0, (1,28,28,1), int8, 784 bytes, S:0.00392157 O:-128 SA, in activations buffer"
                ],
                "Metrics": [
                    {
                        "acc": "100.00%",
                        "cos": 0.999988853931427,
                        "desc": "X-cross #1",
                        "l2r": 0.0047496589832007885,
                        "mae": 0.0002734375011641532,
                        "mean": -3.9062499126885086e-05,
                        "nse": 0.9999747877066116,
                        "rmse": 0.001408418407663703,
                        "std": 0.0014149693306535482,
                        "ts_name": "nl_4_0_conversion, ai_i8, (1,1,1,10), m_id=[4]"
                    }
                ],
                "Outputs": [
                    "Quantize_13_out_0   :   Quantize_13_out_0, (1,1,1,10), int8, 10 bytes, S:0.00390625 O:-128 SA, in activations buffer"
                ],
                "RT Library": "under development",
                "cpu_npu": {
                    "cpu_freq": 800000000,
                    "cpu_swctrl_percent": "0.00%",
                    "cpu_usage_percent": "31.60%",
                    "gpu_usage_percent": "0.00",
                    "npu_freq": 1000000000,
                    "npu_usage_percent": "68.40%"
                }
            },
            "Versions": {
                "CLI": {
                    "major": 1,
                    "micro": 0,
                    "minor": 7
                },
                "Tools": {
                    "extra": "DEV",
                    "major": 8,
                    "micro": 0,
                    "minor": 1
                },
                "Tools API": {
                    "major": 1,
                    "micro": 0,
                    "minor": 7
                }
            }
        }
    # Create an object to get all runs of all models from the json file
    v = ValidationJSON.from_json(Path("../summary/validation_summary.json"))
    RunValidationJson.from_dict(d)
    run = RunValidationJson()
