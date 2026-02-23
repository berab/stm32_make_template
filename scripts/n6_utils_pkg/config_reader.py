import argparse
import json
import os
import re
from pathlib import Path
import shutil
from typing import Any, Mapping, Tuple, Optional, List
import platform
import logging
from n6_utils_pkg.compilers import CompilerType, GCCCompiler, IARCompiler, parse_compiler_type
from n6_utils_pkg.cubeIDE_toolbox import CubeIDEToolBox

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s  %(name)s -- %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
ch.setFormatter(formatter)
logger.addHandler(ch)

def parse_jsonc(filename:Path) -> Mapping[str, Any]:
    if filename.exists():
        s = filename.read_text()
        # Remove comments
        s = '\n'.join(l for l in s.split('\n') if not l.lstrip(' ').lstrip("\t").startswith('//'))
        try:
            data = json.loads(s)
        except json.JSONDecodeError as e:
            raise SyntaxError(f"Bad Json syntax ({e.msg}) at line: {s.splitlines()[e.lineno-1]}")
    else:
        raise FileNotFoundError(f"Cannot find required file {filename.resolve()}")
    return data

def get_default_tools_dir(d:Mapping[str, str]=None) -> Mapping[str, Any]:
    # Extract paths of the tools if they are found in $PATH / set it to None otherwise
    # Update the given dictionary with found paths if some entries are missing in the dictionary, if a dict is passed as argument.
    gdb_s = shutil.which(GCCCompiler.get_debugger_server_exe())
    gdb_b = shutil.which(GCCCompiler.get_debugger_exe())
    iar_b = shutil.which(IARCompiler.get_compiler_exe())
    obj_b = shutil.which("arm-none-eabi-objcopy") # no need to put ".exe" for windows -> this line is approximately os-agnostic 
    cub_b = shutil.which("STM32_Programmer_CLI")
    make_b= shutil.which("make")
    cubi_b= shutil.which("stm32cubeide")
    c_type = "gcc"  # default = gcc because it is multiplatform...
    if (gdb_s is None or gdb_b is None) and (iar_b is not None):
        c_type = "iar"

    tools = {
            "compiler_type": c_type,
            "gdb_server_path": Path(gdb_s).parent.as_posix() if gdb_s is not None else None,
            "gcc_binary_path": Path(gdb_b).parent.as_posix() if gdb_b is not None else None,
            "iar_binary_path": Path(iar_b).parent.as_posix() if iar_b is not None else None,
            "make_binary_path": Path(make_b).as_posix() if make_b is not None else None,
            "objcopy_binary_path": Path(obj_b).as_posix() if obj_b is not None else None,
            "cubeProgrammerCLI_binary_path": Path(cub_b).as_posix() if cub_b is not None else None,
            "cubeide_path": Path(cubi_b).parent.as_posix() if cubi_b is not None else None
    }
    if d is None:
        return tools
    else:
        # Update the dictionary with the paths found in the $PATH for missing entries (if applicable)
        for k, v in tools.items():
            if d.get(k) is None and v is not None:
                logger.debug(f"Using {k} from $PATH: {v}")
                d[k] = v


def get_value_DEFAULT(key:str) -> Any:
    raise ValueError(f"Config entry {key} has not been initialized")

def check_path_entry_ok(d: Mapping[str, str], key: str) -> None:
    """Checks if a key exist and is associated to a valid path"""
    rv = d.setdefault(key)
    if not rv:
        raise ValueError(f"Required config entry {key} does not exist")
    if not Path(rv).exists():
        raise ValueError(f"Path for entry {key} does not exist: {rv}")

class ConfigReader:
    def __init__(self, tools_filename:Path):
        try:
            self.data = parse_jsonc(tools_filename)
        except FileNotFoundError:
            self.data = get_default_tools_dir()
        self.__get_tool_value = self.get_value
        self.loader = None
        self.__get_N6_loader_value = lambda self, x : get_value_DEFAULT(x)
        self.validation_tools = None
        self.__get_valid_on_tgt_value = lambda self, x : get_value_DEFAULT(x)
        self.handle_cubeIDE()
        get_default_tools_dir(self.data)
        self.sanitize_config()

    def sanitize_config(self):
        """Ensures all keys work"""
        if "compiler_type" not in self.data:
            raise ValueError(f"Required config entry compiler_type does not exist")
        else:
            _ = parse_compiler_type(self.data["compiler_type"]) # This will raise an error if the compiler type is not known

        # check for tools that are required anyways
        for k in ["objcopy_binary_path", "cubeProgrammerCLI_binary_path"]:
            check_path_entry_ok(self.data, k)

        # check for compiler binaries
        if parse_compiler_type(self.data["compiler_type"]) == CompilerType.GCC:
            check_path_entry_ok(self.data, "gdb_server_path")
            check_path_entry_ok(self.data, "gcc_binary_path")
            check_path_entry_ok(self.data, "make_binary_path")
            self.data["compiler_binary_path"] = self.data["gcc_binary_path"]
        elif parse_compiler_type(self.data["compiler_type"]) == CompilerType.IAR:
            check_path_entry_ok(self.data, "iar_binary_path")
            self.data["compiler_binary_path"] = self.data["iar_binary_path"]

    def handle_cubeIDE(self):
        # Even if the compiler is not gcc, use this entry to overwrite 
        # objcopy etc... 
        ci_b = self.data.get("cubeide_path", None)
        if ci_b is None:
            # Cannot use cube ide path (not provided or does not exist)
            return
        if not Path(ci_b).exists():
            logger.warning(f"Cube IDE path {ci_b} does not exist, either comment it or fix it in the config file. Ignoring it.")
            return
        # Cube IDE path exists, overwrite all tools by cubeIDE tools
        cide = CubeIDEToolBox(cubeide_path=Path(ci_b))
        binaries_to_seek = (
            ("gdb_server_path", cide.gdb_server),
            ("gcc_binary_path", cide.gcc),
            ("objcopy_binary_path", cide.objcopy),
            ("cubeProgrammerCLI_binary_path", cide.cube_programmer),
            ("make_binary_path", cide.make)
        )
        p = Path(ci_b)
        for key, val in binaries_to_seek:
            if key in self.data.keys():
                # Do not overwrite user values
                logger.debug(f"Found {val} in cubeIDE install: {key} not overwritten because already provided by the user")
                continue
            if key in ["objcopy_binary_path", "cubeProgrammerCLI_binary_path", "make_binary_path"]:
                self.data[key] = val.expanduser().absolute().as_posix()
            else:
                # for gdb and gdbserver, provide path only (as IAR)
                self.data[key] = val.parent.expanduser().absolute().as_posix()
            logger.debug(f"Found {val.name} in <CUBE_IDE_PATH>/{val.relative_to(p)}, using it for {key}")

    def get_value(self, key:str) -> Any:
        v = self.data[key]
        if v is not None:
            return v
        else:
            raise ValueError(f"[TOOLS] Required config entry {key} does not exist")

    def add_n6_loader_config(self, args) -> None:
        self.loader = N6LoaderConfig(args)

    def add_cm55_loader_config(self, args) -> None:
        self.loader = CM55LoaderConfig(args) # Use the same class as N6LoaderConfig, but with different defaults (at least for now)

    def add_h7p_loader_config(self, args) -> None:
        self.loader = H7PLoaderConfig(args) # Use the same class as N6LoaderConfig, but with different defaults (at least for now)

    def add_validation_tools_config(self, args) -> None:
        self.validation_tools = ValidationToolsConfig(args)

    def get_compiler_binary_path(self) -> Path:
        return Path(self.__get_tool_value("compiler_binary_path"))
    def get_gdb_path(self) -> Path:
        return Path(self.__get_tool_value("gdb_server_path"))
    def get_make_path(self) -> Path:
        return Path(self.__get_tool_value("make_binary_path"))
    def get_compiler_type(self) -> CompilerType:
        return parse_compiler_type(self.__get_tool_value("compiler_type"))
    def get_objcopy_path(self) -> Path:
        return Path(self.__get_tool_value("objcopy_binary_path"))
    def get_cubeprogrammer_path(self) -> Path:
        return Path(self.__get_tool_value("cubeProgrammerCLI_binary_path"))
    def get_stldr_path(self, board_type:str) -> Path:
        cp = self.get_cubeprogrammer_path().parent
        if board_type == "NUCLEO":
            return cp / "ExternalLoader" / "MX25UM51245G_STM32N6570-NUCLEO.stldr" 
        else:
            return cp / "ExternalLoader" / "MX66UW1G45G_STM32N6570-DK.stldr" 

    def get_loader_network(self) -> Path:
        return Path(self.loader.get_value("network.c"))
    def get_loader_memdump_path(self) -> Path:
        return Path(self.loader.get_value("memdump_path"))
    def get_project_path(self) -> Path:
        return Path(self.loader.get_value("project_path"))
    def get_project_build_conf(self) -> str:
        return self.loader.get_value("project_build_conf")
    def get_skip_prog_flash(self) -> bool:
        return self.loader.get_value("skip_external_flash_programming")
    def get_skip_prog_ramdata(self) -> bool:
        return self.loader.get_value("skip_ram_data_programming")
    def get_skip_build(self) -> bool:
        return self.loader.get_value("skip_build")
    

    def get_models_pattern(self) -> str:
        v = self.validation_tools.get_value("models_pattern")
        return v
    def get_datasets_pattern(self) -> str:
        v = self.validation_tools.get_value("datasets_pattern")
        return v
    def get_neural_art_profile(self) -> str:
        v = self.validation_tools.get_value("neural_art_profile")
        return v
    def get_stmai_binairies_path(self) -> str:
        v = self.validation_tools.get_value("stmai_binaries_path")
        return Path(v)
    def get_stmai_python_path(self) -> str:
        v = self.validation_tools.get_value("stmai_python_path")
        return Path(v)
    def get_ignore_errors(self) -> str:
        return self.validation_tools.get_value("ignore_errors")
    def get_ignore_processed_models(self) -> bool:
        return self.validation_tools.get_value("ignore_processed_mdls")

    def get_relocatable(self) -> bool:
        return self.validation_tools.get_value("relocatable")
    def get_use_qmn(self) -> bool:
        return self.validation_tools.get_value("use_qmn")
    def get_use_python(self) -> bool:
        return self.validation_tools.get_value("use_python")
    def get_test_purpose(self) -> str:
        return self.validation_tools.get_value("test_purpose")

    def get_test_step(self) -> str:
        return self.validation_tools.get_value("test_step")
    def get_target_name(self) -> str:
        return self.validation_tools.get_value("target")
    def get_batch(self) -> int:
        v = self.validation_tools.get_value("batch")
        return int(v)
    def get_stlink_sn(self) -> str:
        v = self.validation_tools.get_value("st_link_sn")
        if v == "None":
            return None
        return v
    def get_usb_comport(self) -> str:
        v = self.validation_tools.get_value("usb_comport")
        if v == "None":  # usb_comport is of type str, so it can be "None" as a string (the default)
            return None
        return v

    def __str__(self) -> str:
        s = f"== TOOLS\n{str(self.data)}\n"
        if self.loader is not None:
            s += f"== N6_LOADER\n{str(self.loader.data)}\n"
        if self.validation_tools is not None:
            s += f"== Validation Tools\n{str(self.validation_tools.data)}\n"
        return s

"""
Helper functions for tools parsers
"""
# helper function to build default args dictionary
def make_default_arg(value, atype, dest,  help_str:str):
    return {"val": value, "atype": atype, "dest":dest, "help":help_str}

# helper function to add arguments with default value = None and dest/help messages taken from the args dictionary
def add_arg_from_default_args(*args, parser_obj, dict_entry, **kwargs):
    parser_obj.add_argument(*args, default=None, dest=dict_entry["dest"], help=dict_entry["help"], **kwargs)

# helper function to take an existing dictionary of arguments, apply CLI values if they exist, or default values if neither of them exist
def get_args(config_file:str, default_args, args) -> Mapping[str, Any]:
    data = {}
    # Read values from the config file
    if config_file is not None:
        data = parse_jsonc(Path(config_file))
    # Override values of the JSON with what has been provided in the CLI
    # For values provided neither in the CLI or the JSON, use default values
    for k, v in default_args.items():
        # get cli value from args 
        cli_value = args.__getattribute__(v["dest"])
        if cli_value is not None:
            # CLI value is not none: override config file value / set value
            data[k] = v["atype"](cli_value)
        else:
            if k not in data:
                # Value not in the json: update it with default value
                logger.debug(f"Setting default value for {k} to default: {v['val']}")
                data[k] = v["atype"](v["val"])
            else:
                # Value in the json, don't override it with defaults
                pass
    return data
class LoaderConfig():
    default_args={}
    config_type_name = "N6_Loader"
    config_file_option_name = "n6-loader-config"
    @classmethod
    def _get_network_c_default_path(cls) -> Path:
        """ Returns the network.c path """
        # Default network.c location
        networkc_dir = Path(os.getcwd()) / "st_ai_output" / "network.c"
        return networkc_dir.resolve()

    @classmethod
    def _get_c_project_default_path(cls) -> Path:
        ## Compute default values: (assume the script is in a pack or in the repo)
        # Default project:
        scripts_dir = Path(__file__).parents[1].resolve()   # Location of the n6_loader.py
        project_pack_dir = scripts_dir / ".." / ".." / "Projects" / "STM32N6570-DK" / "Applications" / "NPU_Validation"
        project_repo_dir = scripts_dir / ".." / ".." / "Projects" / "NPU_Validation"
        project_path = project_pack_dir.resolve()   # Use the "pack" location by default
        if not project_pack_dir.exists():
            if project_repo_dir.exists():   # But if the pack location does not exist and the repo location exists, use it
                project_path = project_repo_dir.resolve()
        return project_path

    @classmethod
    def _get_available_build_configs(cls) -> List[str]:
        return ["N6-DK", "N6-DK-USB", "N6-Nucleo", "N6-Nucleo-USB", "N6-DK-legacy"]
    
    @classmethod
    def add_args(cls, parser:argparse.ArgumentParser) -> None:
        """
        Updates the parser with arguments specific to n6_loader
        @TODO: make something cleaner maybe ...
        """
        # Get default project path and network.c path
        project_path = cls._get_c_project_default_path()
        networkc_dir = cls._get_network_c_default_path()
        build_confs = cls._get_available_build_configs()
        # Build default arguments
        cls.default_args = {
            "network.c":          make_default_arg(value=networkc_dir, atype=Path, dest="ldr_nf", help_str=f"Location of the network file to add to the project (default: {str(networkc_dir)})"),
            "project_build_conf": make_default_arg(value=build_confs[0],      atype=str,  dest="ldr_bc", help_str=f"Build config to use for the project (default: {build_confs[0]})"),
            "project_path":       make_default_arg(value=project_path, atype=Path, dest="ldr_projectp", help_str=f"Location of the validation project (ends with NPU_Validation) (default: {str(project_path)})"),
            "skip_external_flash_programming": make_default_arg(value=False, atype=bool, dest="ldr_skipf", help_str="Skip programming of the external flash memory (default: False)"),
            "skip_ram_data_programming":       make_default_arg(value=False, atype=bool, dest="ldr_skipr", help_str="Skip programming of all RAM memories (internal & external) (default:False)"),
            "skip_build":                      make_default_arg(value=False, atype=bool, dest="ldr_skipb", help_str="Skip copy and build steps in the process (default: False)")
        }
        # Add arguments to the CLI (default = None) to post-process default values afterwards
        arggrp = parser.add_argument_group(cls.config_type_name, cls.config_type_name + 'specific options')
        add_arg_from_default_args("--network-file", "-nf",      parser_obj=arggrp, dict_entry=cls.default_args["network.c"])
        add_arg_from_default_args("--build-config", "-bc",      parser_obj=arggrp, dict_entry=cls.default_args["project_build_conf"], choices=build_confs)
        add_arg_from_default_args("--project-path", "-project", parser_obj=arggrp, dict_entry=cls.default_args["project_path"])
        add_arg_from_default_args("--skip-flash",               parser_obj=arggrp, dict_entry=cls.default_args["skip_external_flash_programming"], action="store_true")
        add_arg_from_default_args("--skip-ramprog",             parser_obj=arggrp, dict_entry=cls.default_args["skip_ram_data_programming"], action="store_true")
        add_arg_from_default_args('--skip-build',               parser_obj=arggrp, dict_entry=cls.default_args["skip_build"], action='store_true')
        arggrp.add_argument("--"+cls.config_file_option_name,  dest=cls.config_file_option_name, default=None, help=f"Config file for {cls.config_type_name}")
    
    def __init__(self, args):
        self.data = get_args(vars(args)[self.config_file_option_name], self.default_args, args)
        self.sanitize_config()
    
    def sanitize_config(self):
        """Ensures all keys work"""
        # if some entries are missing, they are automatically set to default value by "get_args"
        # only remains checking if the paths are valid etc...
        check_path_entry_ok(self.data, "project_path")
        
        # Post-process sanitized config (eg. replace None values with computed fields)
        if self.data.get("memdump_path") is None and self.data.get("network.c") is not None:
            self.data["memdump_path"] = str(Path(self.data["network.c"]).parent)
    
    def get_value(self, key:str) -> Any:
        v = self.data[key]
        if v is not None:
            return v
        else:
            raise ValueError(f"[{self.config_type_name}] Required config entry {key} does not exist")
        
class N6LoaderConfig(LoaderConfig):
    """ N6 Loader config class, inherits from LoaderConfig """
    def __init__(self, args):
        super().__init__(args)

class CM55LoaderConfig(LoaderConfig):
    config_type_name = "CM55_Loader"
    config_file_option_name = "cm55-loader-config"
    """ CM55 Loader config class, inherits from LoaderConfig """
    def __init__(self, args):
        super().__init__(args)
    
    @classmethod
    def _get_c_project_default_path(cls) -> Path:
        ## Compute default values: (assume the script is in a pack or in the repo)
        # Default project:
        scripts_dir = Path(__file__).parents[1].resolve()   # Location of the n6_loader.py
        project_pack_dir = scripts_dir / ".." / ".." / "Projects" / "STM32N6570-DK" / "Applications" / "CM55_Validation"
        project_repo_dir = scripts_dir / ".." / ".." / "Projects" / "CM55_Validation"
        project_path = project_pack_dir.resolve()   # Use the "pack" location by default
        if not project_pack_dir.exists():
            if project_repo_dir.exists():   # But if the pack location does not exist and the repo location exists, use it
                project_path = project_repo_dir.resolve()
        return project_path

class H7PLoaderConfig(LoaderConfig):
    config_type_name = "H7P_Loader"
    config_file_option_name = "h7p-loader-config"
    """ H7P Loader config class, inherits from LoaderConfig """
    def __init__(self, args):
        super().__init__(args)
    
    @classmethod
    def _get_c_project_default_path(cls) -> Path:
        ## Compute default values: (assume the script is in a pack or in the repo)
        # Default project:
        scripts_dir = Path(__file__).parents[1].resolve()   # Location of the n6_loader.py
        project_pack_dir = scripts_dir / ".." / ".." / "Projects" / "STM32H7P5I-Nucleo" / "Applications" / "NPU_Validation"
        project_repo_dir = scripts_dir / ".." / ".." / "Projects" / "STM32H7P5I-Nucleo" / "NPU_Validation"
        project_path = project_pack_dir.resolve()   # Use the "pack" location by default
        if not project_pack_dir.exists():
            if project_repo_dir.exists():   # But if the pack location does not exist and the repo location exists, use it
                project_path = project_repo_dir.resolve()
        return project_path
    @classmethod
    def _get_available_build_configs(cls) -> List[str]:
        return ["H7P-Nucleo"]
class ValidationToolsConfig():
    # Static attribut for all instances
    default_args={}
    @classmethod
    def add_args(cls, parser:argparse.ArgumentParser) -> None:
        """
        Updates the parser with arguments specific to validation scripts
        """
        scripts_dir = Path(__file__).parents[1].resolve()   # Location of the run_xxx.py files
        tools_pack_dir = scripts_dir / ".." / ".." / "Utilities"
        st_ai_dir = scripts_dir / ".." / ".." / ".." / "stm.ai" / "new_root" / "src" / "scripts" / "st_ai_cli"
        uname = platform.uname()
        tools_pack_dir = tools_pack_dir / uname.system.lower()
        if uname.system.lower() in ["windows", "linux"]: 
            pass #default value=ok
        elif uname.system.lower() == "darwin":
            if uname.machine.lower() == "arm64":
                tools_pack_dir = tools_pack_dir / "macarm"
            else:
                tools_pack_dir = tools_pack_dir / "mac"   
        tools_pack_dir = tools_pack_dir.resolve()

        # Set values by defaults of arguments (Create a dictionary with key:value)
        cls.default_args = {
            "stmai_python_path":    make_default_arg(value=st_ai_dir, atype=Path, dest="val_st_ai",           help_str=f"Location of st_ai.py (default: {str(st_ai_dir)})"),
            "stmai_binaries_path":  make_default_arg(value=tools_pack_dir, atype=Path, dest="val_binaries",   help_str=f"Location of the stmai binaries (default: {str(tools_pack_dir)})"),
            "models_pattern":       make_default_arg(value=".*tflite",      atype=str,  dest="val_pattern",   help_str=f"Pattern used to find models to process (default: *.tflite)"),
            "datasets_pattern":     make_default_arg(value=None, atype=str, dest="val_datasets",              help_str=f"Pattern used to find datasets (default: None)"),
            "ignore_errors":        make_default_arg(value=False, atype=bool, dest="val_ignore_errors",       help_str=f"Continue looping on profiles for a given model, even if one profile fails (default behaviour is go to the next model) (default: False)"),
            "ignore_processed_mdls":make_default_arg(value=False, atype=bool, dest="val_ignore_processed_mdl",help_str=f"Ignore models in validation loop if the results directory already contains it (default: False)"),
            "relocatable":          make_default_arg(value=False, atype=bool, dest="relocatable",       help_str=f"Activate the generation of the relocatable binary model (default: False)"),
            "use_qmn":              make_default_arg(value=False, atype=bool, dest="val_use_qmn",     help_str="Use the Qmn flow (provide the neural-art compiler with a Qmn-formatted JSON) (default: False)"),
            "use_python":           make_default_arg(value=False, atype=bool, dest="val_use_python",  help_str="Use st_ai.py instead os stedgeai.exe (default: False)"),
            "target":               make_default_arg(value="stm32n6", atype=str, dest="target",         help_str="Select stm32 target: default is 'stm32n6'"),
            "test_purpose":         make_default_arg(value="", atype=str, dest="test_purpose",          help_str="Select the test purpose ('', 'NO_INOUT_BUFFER_ALLOCATION', 'NO_INPUT_ALLOCATION', 'ONNX_CHANGE_DATA'): default is ''"),
            "test_step":            make_default_arg(value="ALL", atype=str, dest="test_step",          help_str="Select the test step ('ONLY_GENERATE', 'ONLY_ONNX_EXPORTER', 'ONLY_TARGET'): default is 'ALL'"),
            "batch":                make_default_arg(value=10, atype=int, dest="val_batch",           help_str="Batch number"),
            "st_link_sn":           make_default_arg(value=None, atype=str, dest="val_stlinksn",      help_str="ST-Link serial number to be used for validation on target"),
            "usb_comport":          make_default_arg(value=None, atype=str, dest="val_usb_comport",       help_str="COM-port to use for validation when using USB-compliant projects (default is None: auto-detect with STEdgeAI)"),
        }
        # Add arguments to the CLI (default = None) to post-process default values afterwards
        arggrp = parser.add_argument_group('Validation Tools', 'Validation tools specific options')
        add_arg_from_default_args("--stmai-binaries",      parser_obj=arggrp, dict_entry=cls.default_args["stmai_binaries_path"])
        add_arg_from_default_args("--stmai-python",        parser_obj=arggrp, dict_entry=cls.default_args["stmai_python_path"])
        add_arg_from_default_args("--pattern",             parser_obj=arggrp, dict_entry=cls.default_args["models_pattern"])
        add_arg_from_default_args("--datasets",            parser_obj=arggrp, dict_entry=cls.default_args["datasets_pattern"])
        add_arg_from_default_args('--continue-looping-on-errors', parser_obj=arggrp, dict_entry=cls.default_args["ignore_errors"], action="store_true")
        add_arg_from_default_args('--skip-processed-mdls', parser_obj=arggrp, dict_entry=cls.default_args["ignore_processed_mdls"], action="store_true")
        add_arg_from_default_args('--relocatable',         parser_obj=arggrp, dict_entry=cls.default_args["relocatable"], action="store_true")
        add_arg_from_default_args('--qmn',                 parser_obj=arggrp, dict_entry=cls.default_args["use_qmn"], action="store_true")
        add_arg_from_default_args('--use-python',          parser_obj=arggrp, dict_entry=cls.default_args["use_python"], action="store_true")
        add_arg_from_default_args('--target',              parser_obj=arggrp, dict_entry=cls.default_args["target"])
        add_arg_from_default_args('--test-purpose',        parser_obj=arggrp, dict_entry=cls.default_args["test_purpose"], choices=['', 'NO_INOUT_BUFFER_ALLOCATION', 'NO_INPUT_ALLOCATION', 'ONNX_CHANGE_DATA'])
        add_arg_from_default_args('--test-step',           parser_obj=arggrp, dict_entry=cls.default_args["test_step"],    choices=['ALL', 'ONLY_GENERATE', 'ONLY_ONNX_EXPORTER', 'ONLY_TARGET'])
        add_arg_from_default_args("--batch",               parser_obj=arggrp, dict_entry=cls.default_args["batch"])
        add_arg_from_default_args("--sn",                  parser_obj=arggrp, dict_entry=cls.default_args["st_link_sn"])
        add_arg_from_default_args("--usb_comport",         parser_obj=arggrp, dict_entry=cls.default_args["usb_comport"])
        arggrp.add_argument("--valtools-config", dest="val_config_file", default=None, help="Config file for validation tools")

    def __init__(self, args):
        # Load the keys:value from config_valid.json into data
        self.data = get_args(args.val_config_file, self.default_args, args)
        # Check the mandatory key exists
        self.sanitize_config()
    
    def sanitize_config(self):
        # if some entries are missing, they are automatically set to default value by "get_args"
        # only remains checking if the paths are valid etc...
        check_path_entry_ok(self.data, "stmai_binaries_path")
    
    def get_value(self, key:str) -> Any:
        v = self.data[key]
        if v is not None:
            return v
        else:
            raise ValueError(f"[Validation Tools] Required config entry {key} does not exist")

class NeuralArtJSON:
    filename: Path
    data: Mapping[str,Any]

    def __init__(self, file_p:Path):
        self.filename = file_p
        data = file_p.read_text()
        # Remove lines(parts) that are not JSON compliant -- comments
        data = re.sub(r"\s*//.*?$", "", data, flags=re.DOTALL|re.MULTILINE)
        self.data = json.loads(data)
    
    def get_profile(self, profile_name:str) -> Tuple[Path, Optional[str], str]:
        """Returns path to mpool/mdesc/compiler arguments"""
        if  (prof:=self.data["Profiles"].get(profile_name)) is None:
            raise ValueError(f"E: Cannot find profile {profile_name} in profile file {self.filename}")
        else:
            mp = Path(prof.get("memory_pool")).resolve()
            md = prof.get("machine_desc")        # MAY RETURN NONE !!!
            if md is not None:
                md = Path(md).resolve()
            aton_opts = prof.get("options")
            return mp, md, aton_opts

if __name__ == "__main__":
    c = ConfigReader(Path(__file__).parents[1] / "config.json")
    c.add_n6_loader_config(Path(__file__).parents[1] / "config_n6l.json", None)
    print(c)
    pass

