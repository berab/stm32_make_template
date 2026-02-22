from __future__ import annotations
import logging
import argparse
from pathlib import Path
from typing import List
import subprocess
import shutil
import sys
from n6_utils_pkg.config_reader import ConfigReader, N6LoaderConfig
from n6_utils_pkg.compilers import CompilerType, IARCompiler, GCCCompiler
from n6_utils_pkg.intel_hex import IHex
from n6_utils_pkg.c_file import CFile
from n6_utils_pkg.mpool import N6_TARGET_MCU

## Current script variable
TEMPLATE_PATH = "./cspy_n6_template.mac"

# By default create the logger "n6_loader"
logger = logging.getLogger(__name__)
log_filename = "n6_loader.log"
log_indent_str = ""

def set_logger():
    global logger
    global log_indent_str

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s  %(name)s -- %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

    if "run_validate_on_target" in {name for name in logging.root.manager.loggerDict}:
        # Create the child logger : "run_validate_on_target.n6_loader"
        logger = logging.getLogger("run_validate_on_target").getChild(__name__)
        log_indent_str = " " * 5 + "- "
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.DEBUG)
        # Create the handler for the console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # Create the handler for the file
    fh = logging.FileHandler(log_filename, mode='w')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

def close_file_loggers():
    """
    Force closing all logging file handlers
    (used for upper-lever scripts to save logfiles per-n6-loader call)
    """
    if logger is not None:
        for hdl in logger.handlers:
            if isinstance(hdl, logging.FileHandler):
                hdl.close()     # Closes the file used by the handler.

def log(level, msg):
    logger.log(level, f"{log_indent_str}{msg}")

def find_while_line(main_c: Path) -> int:
    i = 1
    f = main_c.read_text(encoding=None, errors=None)
    for curline in f.splitlines():
        #print(curline)aiValidationInit();
        #if "USER CODE BEGIN WHILE" in curline:
        if "aiValidationInit();" in curline: #  TODO: Adapt for the current main.c structure !
            return i
        else:
            i = i + 1
    return

def convert_mem_files(memdir:Path, c_file:CFile, objcopy_path:Path=None) -> List[Path]:
    """Converts memory files to hex with offsets (offset wrt 0x0)"""
    rv = []
    memprefix = "*"
    mempool_offsets = c_file.get_all_offsets()
    mempool_suffixes = list(mempool_offsets.keys())
    file_pfx = c_file.get_cname()
    # @TODO ADD NAME PREFIX for mf in memdir.glob(f"**/{prefix}*"):
    for mf in memdir.glob(f"**/{file_pfx}_{memprefix}"):
        # The only files to be considered have a correct name pattern + have been modified roughly at the same time
        # as the c_file (the atonn compiler did it all). This prevents from taking into account older files that may
        # match the same name pattern...
        if abs(mf.stat().st_mtime - c_file.get_mtime()) < 10:
            mem_file_type = mf.suffixes[0][1:].upper()  # get memory pool from file extension
            # try to ensure the file is really a memory "dump" file (as there is no way for the "c_file" to know exactly the name of the file...)
            # This is done by looking whether the memory_pool suffix is part of the name.... (not 100% faultproof)
            if mem_file_type not in mempool_suffixes:
                continue
            offset = mempool_offsets[mem_file_type]      # Get offset from C-file...   #memory_pool.get_offset(mem_file_type)     # get offset from MPOOL
            if mf.suffix == '.raw':
                obj = objcopy_path.resolve()
                output_name = mf.with_suffix('.hex')
                # --start-address  doesnt work
                cmd = [obj, "--change-addresses", offset, "-Ibinary", "-Oihex", mf, output_name]
                cmd_str = " ".join([str(k) for k in cmd]).replace(str(mf.parent / mf.stem), mf.stem).replace(str(obj), obj.name)
                log(logging.DEBUG, cmd_str)
                #print(f"+ {mf} found -> converting to hex : {cmd}")
                v = subprocess.run(cmd, capture_output=True, shell=False)
                if (IHex(output_name).get_data_size() != 0):
                    rv.append(output_name)
                #print(v.returncode)
            elif mf.suffix == '.hex':
                if (IHex(mf).get_data_size() != 0):
                    rv.append(mf)
                #print(f"+ {mf} found")
            else:
                pass
                #print(f"- {mf} ignored")
    return rv

def set_project_path(s:str, projdir: Path) -> str:
    exe_path = (projdir / "EWARM").resolve().as_posix()
    exe_path = exe_path.replace("/", "\\\\")
    return s.replace("$PROJ_DIR$", exe_path)


def show_returncode(desc:str, rv:int):
    """Logs return code value and logs it"""
    if rv == 0:
        # log(logging.INFO, f"{desc} successful")
        pass
    else:
        log(logging.ERROR, f"{desc} failed")


def safe_copy(src: Path, dst: Path):
    """Copy file only if the source exists, raise a FileNotFoundError otherwise"""
    if Path(src).exists():
        shutil.copy2(src, str(dst))
    else:
        log(logging.ERROR, f"Copying {str(src)} failed (file does not exist)")
        raise FileNotFoundError(f"{str(src)} does not exists")


def main_n6_loader(path_to_network_c:List[Path] = None,
                   path_to_memorydumps:Path = None,
                   clean_before_build:bool = False,
                   stlink_sn:str = None,
                   port:str = 'SWD',
                   args:Mapping[str,Any]=None):

    set_logger()
    ret = _main_n6_loader(path_to_network_c   = path_to_network_c,
                          path_to_memorydumps = path_to_memorydumps,
                          clean_before_build  = clean_before_build,
                          stlink_sn           = stlink_sn,
                          port                = port,
                          args                = args)

    # Error loading memories and start, try again
    if ret == 5:
        log(logging.INFO, "Start operation did not achieve successfully! Trying again ...")
        ret = _main_n6_loader(path_to_network_c=path_to_network_c, path_to_memorydumps=path_to_memorydumps,
                              clean_before_build=clean_before_build, stlink_sn=stlink_sn, port=port, args=args)

    if ret != 0:
        log(logging.ERROR, "Start operation did not achieve successfully.")
    else:
        log(logging.INFO, "Start operation achieved successfully")

    close_file_loggers()
    return ret

def _main_n6_loader(path_to_network_c:List[Path] = None,
                    path_to_memorydumps:Path = None,
                    clean_before_build:bool = False,
                    stlink_sn:str = None,
                    port:str = 'SWD',
                    args:Mapping[str,Any]=None):
    """
    Main n6 loader entry point:
        :param path_to_network_c: List of Path objects [0] is the network.c file, other indices (optional) are extra files to be copied into the project
    :param path_to_memorydumps: Path to the memory dumps directory
    :param clean_before_build: If True, clean the project before building it
    :param stlink_sn: ST-Link serial number
    :param port: Port to use when calling CubeProgrammer
    :param args: Arguments from the command line if any
    :return:    0 is success else it is an error code. 5 is an error of loading memories
    """

    # Get info from config file
    if args.config is not None:
        o = Path(args.config).resolve()
    else:
        o = Path(__file__).with_name("config.json").resolve()
    c = ConfigReader(o)
    c.add_n6_loader_config(args)
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
    path_to_objcopy = c.get_objcopy_path()
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
                               path_to_debugger_template=Path(__file__).with_name("cspy_n6_template.mac"),
                               project_config_name=build_conf,
                               st_link_sn=stlink_sn,
                               logger=log)
    elif compiler_type == CompilerType.GCC:
        log(logging.INFO, f"Preparing compiler GCC")
        compiler = GCCCompiler(path_to_compiler_binary=path_to_compiler/"arm-none-eabi-gcc",
                               path_to_debugger_binary=path_to_compiler/"arm-none-eabi-gdb",
                               path_to_project=path_to_c_project,
                               path_to_debugger_template=Path(__file__).with_name("gdb_n6_template.gdb"),
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

    # ---------- Copy network .c to & extra files to project ----------
    pout = path_to_network_in_project / "network.c"
    net_c = path_to_network_c.pop(0)  # The .c file should be the first file in the list, other files are extra files to be copied
    log(logging.INFO, f"Copying {net_c.name} to project: -> {pout}")
    try:
        safe_copy(net_c, pout)
        if net_c.with_suffix(".h").exists():
            safe_copy(net_c.with_suffix(".h"), pout.with_suffix(".h"))
        # Copy blobs if any (and more recent than the .c file)
        blob_expected_file = net_c.with_name(net_c.stem + "_ecblobs.h")
        if blob_expected_file.exists() and (blob_expected_file.stat().st_mtime >= net_c.stat().st_mtime):
            # blob name should not be changed, as the .c file refers to this file name.
            log(logging.INFO, f"Copying {blob_expected_file.name} to project: {blob_expected_file} -> {pout.parent}")
            safe_copy(blob_expected_file, pout.parent)
        # Copy extra files if any
        if path_to_network_c is not None:
            for k in path_to_network_c:
                log(logging.INFO, f"Copying {k.name} to project: {k} -> {path_to_network_in_project / k.name}")
                safe_copy(k, path_to_network_in_project / k.name)
    except FileNotFoundError:
        return 1

    # ---------- Extract memory pool info from the c-file ----------
    log(logging.DEBUG, f"Extracting information from the c-file")
    cf = CFile(str(pout))
    mp = cf.get_mpools()
    mp.add_loaders(path_to_stldr, target=N6_TARGET_MCU)  # Attach loader for external flash to mpools definition


    log(logging.DEBUG, f"Converting memory files in results/<model>/generation/ to Intel-hex with proper offsets")
    # log(logging.INFO, f"Converting memory files in {path_to_memorydumps} to Intel-hex with proper offsets")
    mem_hex_dumps = convert_mem_files(path_to_memorydumps, cf, path_to_objcopy)
    if not mem_hex_dumps:
        log(logging.ERROR, f"No memory file converted")

    # ---------- Reset the complete board before doing stuff on memories (FIX for bad flash handling by cubeProgrammer)
    log(logging.INFO, f"""Resetting the board...""")
    cmd = [str(path_to_cube), '-q', '-c', 'port='+port, 'mode=powerdown', 'freq=2000', 'ap=1']
    if stlink_sn:
        cmd.insert(cmd.index("port=SWD")+1, f"sn={stlink_sn}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log(logging.DEBUG, f"Launching command: {' '.join(cmd)}")
    log(logging.DEBUG, result.stdout.decode('utf-8').replace("\r\n","\n"))

    # ---------- Add memories ----------
    # log(logging.INFO, f"Patching macro file for automatically loading Intel-Hex files upon breakpoint")
    for mf in mem_hex_dumps:
        mem_file_type = mf.suffixes[0][1:]
        flshl = mp.get_loader(mem_file_type)
        hx = IHex(mf)
        size_kb = hx.get_data_size() / 1000
        if flshl:
            # A flash loader exists, use it
            # Arguments for cube programmer:
                #   -q: quiet
            #   -c: connect / port=SWD / mode=hotplug -UR does not work- / freq=200 (shall be <1000 in the current versions of n6)
            #                  ap=access port 1: port 0 is not useable
            #   -extloader: External loader for the flash
            #   --download: file to download to flash (.hex file or .bin file with offset)
            #   --verify: Verify the file has been correctly written to flash for success
            cmd = [str(path_to_cube), '-q', '-c', 'port='+port, 'mode=hotplug', 'ap=1', '--extload', flshl, '--download', str(mf), "--verify"]
            if stlink_sn:
                cmd.insert(cmd.index("port=SWD")+1, f"sn={stlink_sn}")

            # flashes using cube programmer, all outputs are redirected to the greater void
            if skip_extflash_prog:
                log(logging.INFO, f"Skipping flashing memory {mem_file_type} -- {size_kb:,.3f} kB")
            else:
                # ---------- Flashing memory ------------------------------------------------------------
                log(logging.INFO, f"Flashing memory {mem_file_type} -- {size_kb:,.3f}".replace(',', ' ') + " kB")
                log(logging.DEBUG, f"Flashing memory command: {' '.join(cmd)}")
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                log(logging.DEBUG, result.stdout.decode('utf-8').replace("\r\n","\n"))
                # If error flashing
                if result.returncode:
                    log(logging.ERROR, f"Flashing memory {mem_file_type} -- return code ERROR")
                    return result.returncode
        else:
            # no flash loader, this must be an internal ram...
            if skip_ramdata_prog:
                log(logging.INFO, f"""Not planning to load ram data {mem_file_type} -- {size_kb:,.3f}kB""")
            else:
                log(logging.INFO, f"""Loading {mem_file_type} after program start -- {size_kb:,.3f}kB""")
                compiler.add_memory_file_to_load(mem_file_type, Path(mf).resolve())

    # log(logging.INFO, f"Dumping macro file")
    compiler.dump_macro_file()

    # ---------- Building project ----------
    if not skip_build:
        step_s = f"Building project (conf= {build_conf})"
        if clean_before_build is True:
            step_s = f"Cleaning and {step_s}"
        log(logging.INFO, step_s)
        rv = compiler.compile_project(clean=clean_before_build)
        # If error
        if rv:
            log(logging.ERROR, f"Compilation failed !")
            return rv

    # ---------- Loading app and model and run the program ----------
    log(logging.INFO, f"Loading internal memories & Running the program")
    rv = compiler.load_and_run()
    # If error
    if rv:
        log(logging.ERROR, f"Loading memories failed !")
        return 5

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
    N6LoaderConfig.add_args(parser=parser)
    args = parser.parse_args()
    rv = main_n6_loader(path_to_network_c=None,     # First and second arguments are forced to None (will be handled by n6loader config after)
                        path_to_memorydumps=None,
                        clean_before_build=args.project_clean,
                        stlink_sn=args.st_link_serialnr,
                        port=args.st_link_port,
                        args=args)
    sys.exit(rv)
