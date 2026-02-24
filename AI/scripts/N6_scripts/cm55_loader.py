from __future__ import annotations
import logging
import argparse
from pathlib import Path
from typing import List
import re
import subprocess
import shutil
import sys
from n6_utils_pkg.config_reader import ConfigReader, CM55LoaderConfig
from n6_utils_pkg.compilers import CompilerType, IARCompiler, GCCCompiler

#default logger
logger = logging.getLogger(__name__)
log_filename = "cm55_loader.log"

def set_logger():
    global logger
    global log_indent
    if "run_validate_on_target" in {name for name in logging.root.manager.loggerDict}:
        logger = logging.getLogger("run_validate_on_target").getChild(__name__)
        log_indent = " "*5 + "- "
    else:
        logger.setLevel(logging.DEBUG)
        # create console handler and set level to debug
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        # create formatter
        formatter = logging.Formatter('%(asctime)s  %(name)s -- %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
        # add formatter to ch
        ch.setFormatter(formatter)
        # add ch to logger
        logger.addHandler(ch)
        log_indent = ""
        # create file handler and set level to debug
        fh = logging.FileHandler(log_filename, mode='w')
        fh.setLevel(logging.DEBUG)
        # add formatter to fh
        fh.setFormatter(formatter)
        # add fh to logger
        logger.addHandler(fh)

def log(level, msg):
    logger.log(level, f"{log_indent}{msg}")

def show_returncode(desc:str, rv:int):
    """Logs return code value and logs it"""
    if rv == 0:
        # log(logging.INFO, f"{desc} successful")
        pass
    else:
        log(logging.ERROR, f"{desc} failed")

def find_while_line(main_c: Path) -> int:
    f = main_c.read_text(encoding=None, errors=None)
    return re.match(r"(.*)^\s+MX_X_CUBE_AI_Init\(\);\n", f, flags=re.MULTILINE|re.DOTALL).group(1).count("\n")+1

def safe_copy(src: Path, dst: Path):
    """Copy file only if the source exists, raise a FileNotFoundError otherwise"""
    if Path(src).exists():
        shutil.copy2(src, str(dst))
    else:
        log(logging.ERROR, f"Copying {str(src)} failed (file does not exist)")
        raise FileNotFoundError(f"{str(src)} does not exists")


def copy_files_to_project(src_network_c: Path, tgt_directory:Path):
    file_names_to_copy = ["network.c", "network.h", "network_c_info.json",
                          "network_config.h", "network_generate_report.txt",
                          "network_data.c", "network_data.h",
                          "network_data_params.c", "network_data_params.h",
                          "network_data.bin"]
    for fn in file_names_to_copy:
        src_file = src_network_c.with_name(fn)
        if src_file.exists():
            log(logging.INFO, f"Copying {src_file.name} to project: {src_file} -> {tgt_directory}")
            safe_copy(src_file, tgt_directory / fn)
        else:
            raise FileNotFoundError(f"File {src_file} does not exist, exit")



def main_cm55_loader(path_to_network_c:List[Path] = None,
                   path_to_memorydumps:Path = None,
                   clean_before_build:bool = False,
                   stlink_sn:str = None,
                   port:str = 'SWD',
                   args:Mapping[str,Any]=None):
    """
    Main cm55 loader entry point:
    :param path_to_network_c: List of Path objects [0] is the network.c file, other indices (optional) are extra files to be copied into the project
    :param path_to_memorydumps: Path to the memory dumps directory
    :param clean_before_build: If True, clean the project before building it
    :param stlink_sn: ST-Link serial number
    :param port: Port to use when calling CubeProgrammer
    :param args: Arguments from the command line if any
    """
    set_logger()
    # Get info from config file
    if args.config is not None:
        o = Path(args.config).resolve()
    else:
        o = Path(__file__).with_name("config.json").resolve()
    c = ConfigReader(o)
    c.add_cm55_loader_config(args)
    path_to_c_project = c.get_project_path()
    # X-CUBE-AI\atonn\models contains the network.c
    # main.c is @ root
    # n6.cspy is at EWARM/
    # cspy.bat/xcls are in EWARM/settings/Project.xxxx.cspy.bat
    # project.ewp is in EWARM
    path_to_main = path_to_c_project / "Core" / "Src" / "main.c"
    path_to_network_in_project = path_to_c_project / "X-CUBE-AI" / "App"
    path_to_compiler = c.get_compiler_binary_path()
    path_to_cube = c.get_cubeprogrammer_path()
    build_conf = c.get_project_build_conf()
    if "nucleo" in build_conf.lower():
        path_to_stldr = c.get_stldr_path(board_type="NUCLEO")
    else:
        path_to_stldr = c.get_stldr_path(board_type="DK")
    skip_extflash_prog = c.get_skip_prog_flash()
    skip_ramdata_prog = c.get_skip_prog_ramdata()
    compiler_type = c.get_compiler_type()
    if compiler_type == CompilerType.IAR:
        log(logging.INFO, f"Preparing compiler IAR")
        compiler = IARCompiler(path_to_compiler_binary=path_to_compiler/"iarbuild",
                               path_to_debugger_binary=path_to_compiler/"CSpyBat",
                               path_to_project=path_to_c_project,
                               path_to_debugger_template=Path(__file__).with_name("cspy_cm55_template.mac"),
                               project_config_name=build_conf,
                               st_link_sn=stlink_sn,
                               logger=log)
    elif compiler_type == CompilerType.GCC:
        log(logging.INFO, f"Preparing compiler GCC")
        compiler = GCCCompiler(path_to_compiler_binary=path_to_compiler/"arm-none-eabi-gcc",
                        path_to_debugger_binary=path_to_compiler/"arm-none-eabi-gdb",
                        path_to_project=path_to_c_project,
                        path_to_debugger_template=Path(__file__).with_name("gdb_cm55_template.gdb"),
                        project_config_name=build_conf,
                        st_link_sn=stlink_sn,
                        logger=log,
                        path_to_gdb_server=c.get_gdb_path(),
                        path_to_cube_programmer=c.get_cubeprogrammer_path(),
                        path_to_make=c.get_make_path())

    skip_build=c.get_skip_build()

    # If no arguments, read contents from the config file
    if not path_to_network_c:
        path_to_network_c = [c.get_loader_network()]
        path_to_memorydumps = c.get_loader_memdump_path()

    # Add breakpoint
    lineno = find_while_line(path_to_main)
    log(logging.INFO, f"Setting a breakpoint in main.c at line {lineno} (before the infinite loop)")
    compiler.add_breakpoint_to_main_macro(lineno)
    compiler.dump_macro_file()

    # Copy network .c to & extra files to project
    pout = path_to_network_in_project / "network.c"
    net_c = path_to_network_c.pop(0)  # The .c file should be the first file in the list, other files are extra files to be copied
    copy_files_to_project(src_network_c=net_c, tgt_directory=path_to_network_in_project)


    # Extract memory pool info from the c-file
    log(logging.INFO, f"Extracting weights location from c-files")
    c_data = (path_to_network_in_project / "network_data.c").read_text()
    weights_location = re.search(r"AI_NETWORK_DATA_WEIGHTS_ADDR\s+\((.*?)\)", c_data)
    if not weights_location:
        log(logging.ERROR, "Could not find weights location in network_data.c -> When generating, make sure to use the --address option together with the --binary option")
        raise ValueError("Could not find weights location in network_data.c")
    weights_location = weights_location.group(1).strip()
    log(logging.INFO, "\tWeights location: " + weights_location)
    weights_location = int(weights_location, 0)  # Convert to int, base 0 (auto-detects hex or decimal)
    if weights_location < 0x70000000 or weights_location > 0x7FFFFFFF:
            raise ValueError(f"Weights location {weights_location:#x} is not in the expected range [0x70000000, 0x7FFFFFFF]")
    weights_file = path_to_network_in_project /"network_data.bin"

    # Reset the complete board before doing stuff on memories (FIX for bad flash handling by cubeProgrammer)
    log(logging.INFO, f"""Resetting the board...""")
    cmd = [str(path_to_cube), '-q', '-c', 'port='+port, 'mode=powerdown', 'freq=2000', 'ap=1']
    if stlink_sn:
        cmd.insert(cmd.index("port=SWD")+1, f"sn={stlink_sn}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log(logging.DEBUG, f"Launching command: {' '.join(cmd)}")
    log(logging.DEBUG, result.stdout.decode('utf-8').replace("\r\n","\n"))
    # Add memories
    # log(logging.INFO, f"Patching macro file for automatically loading Intel-Hex files upon breakpoint")
    size_kb = weights_file.stat().st_size / 1000

    # A flash loader exists, use it
    # Arguments for cube programmer:
    #   -q: quiet
    #   -c: connect / port=SWD / mode=hotplug -UR does not work- / freq=200 (shall be <1000 in the current versions of n6)
    #                  ap=access port 1: port 0 is not useable
    #   -extloader: External loader for the flash
    #   --download: file to download to flash (.hex file or .bin file with offset)
    #   --verify: Verify the file has been correctly written to flash for success
    cmd = [str(path_to_cube), '-q', '-c', 'port='+port, 'mode=hotplug', 'ap=1', '--extload', str(path_to_stldr), '--download', str(weights_file), f"{weights_location:#10x}", "--verify"]
    if stlink_sn:
        cmd.insert(cmd.index("port=SWD")+1, f"sn={stlink_sn}")

    # flashes using cube programmer, all outputs are redirected to the greater void
    if skip_extflash_prog:
        log(logging.INFO, f"Skipping flashing memory {weights_file.name} -- {size_kb:,.3f} kB")
    else:
        log(logging.INFO, f"Flashing external memory -- {size_kb:,.3f}".replace(',', ' ') + " kB")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log(logging.DEBUG, f"Flashing memory command: {' '.join(cmd)}")
        log(logging.DEBUG, result.stdout.decode('utf-8').replace("\r\n","\n"))
        # log(logging.INFO, f"""Flashing memory {mem_file_type} -- return code {"ERROR" if result.returncode else "OK"}""")
        # Early return if error (everything will fail anyway...)
        if result.returncode:
            log(logging.INFO, f"Flashing memory {weights_file.name} @ {weights_location:#10x} -- return code ERROR")
            return result.returncode

    if not skip_build:
        step_s = f"Building project (conf= {build_conf})"
        if clean_before_build is True:
            step_s = f"Cleaning and {step_s}"
        log(logging.INFO, step_s)
        rv = compiler.compile_project(clean=clean_before_build)
        show_returncode("Compilation", rv)
        if rv:
            # error on compilation: exit
            return rv
    log(logging.INFO, f"Running the program")
    rv = compiler.load_and_run()
    show_returncode("Running", rv)
    return rv

    return rv


class PathConverter(argparse.Action):
    """
    Function returning a class subclassing argparse.Action
    to be used ad action kw in parser.add_argument
    This function convert a string to a Path (if the string exists)
    """
    def __call__(self, parser, args, values, option_string=None):
            if values:
                values = Path(values)
            setattr(args, self.dest, values)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program to load data to the N6",
                                     epilog="Only temporary, for internal use...")
    parser.add_argument("-sn", "--serial-number", dest="st_link_serialnr",
                    default=None, help="Force the ST-Link serial number to use for communication with the N6"
                    )
    parser.add_argument("--port", dest="st_link_port", default='SWD', help="Force the use of CubeProgrammer port (default: SWD)")
    parser.add_argument("--clean", action="store_true", dest="project_clean",
                    default=False, help="Clean the project before building it (default: False)")
    parser.add_argument("--config", type=Path, help="Path to config.json file", default=None)
    CM55LoaderConfig.add_args(parser=parser)
    args = parser.parse_args()
    rv = main_cm55_loader(path_to_network_c=None,     # First and second arguments are forced to None (will be handled by n6loader config after)
                    path_to_memorydumps=None,
                    clean_before_build=args.project_clean,
                    stlink_sn=args.st_link_serialnr,
                    port=args.st_link_port,
                    args=args)
    if rv == 0:
        log(logging.INFO, "Start operation achieved successfully")
    else:
        log(logging.ERROR, "Start operation did not achieve successfully")
    sys.exit(rv)
