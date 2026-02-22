import argparse
from dataclasses import dataclass, field
from pathlib import Path
import shutil
import stat     # To check if a file is executable
import subprocess
from typing import List
import logging


# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)    # <---- Change level here for verbosity...
formatter = logging.Formatter('%(asctime)s  %(name)s -- %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
ch.setFormatter(formatter)
logger.addHandler(ch)

@dataclass
class CubeIDE_Plugin():
    plugin_id: str = None               # ID of the plugin (internal name in this module)
    plugin_partial_name: str = None     # Part of the plugin dir to look for
    _plugin_paths: List[Path] = field(default_factory=list) # possible locations of the plugin (temporary)
    executable_name: str = None         # Name of the executable to look for
    executable: Path = None             # Final executable path to use

    def add_possible_path(self, path: Path) -> None:
        """
        Add a possible path to the plugin
        """
        self._plugin_paths.append(path)
    
    def resolve_executable(self) -> None:
        if len(self._plugin_paths) == 0:
            raise FileNotFoundError(f"Tool {self.executable_name} not found")
        # Retrieve the (int) timestamp part of a plugin path (end of the pathname after the last point)
        get_timestamp= lambda p:int(p.parts[p.parts.index("plugins")+1].rsplit(".", 1)[1])
        # Sort the plugin paths by the name of the plugin (to get the most recent one)
        self._plugin_paths.sort(key=get_timestamp, reverse=True)
        self.executable = self._plugin_paths[0]
        if len(self._plugin_paths) > 1:
            logger.debug(f"Multiple versions of {self.plugin_id} found, using the most recent one: {self.executable}")

class CubeIDEToolBox():
    """
    Class to store the tools found in the cubeIDE path
    """
    gdb_server: Path
    gdb_client: Path
    cube_programmer: Path
    cubeide_path: Path
    gdb_server_portno: int
    __toollist__: List

    def __init__(self, cubeide_path: Path = None):
        # Tools to discover w/o extension
        self.__toollist__:List =  [
            CubeIDE_Plugin(plugin_id="gdb-server", plugin_partial_name="gdb-server", executable_name="ST-LINK_gdbserver"),
            CubeIDE_Plugin(plugin_id="gdb", plugin_partial_name="gnu-tools-for-stm32", executable_name="arm-none-eabi-gdb"),
            CubeIDE_Plugin(plugin_id="gcc", plugin_partial_name="gnu-tools-for-stm32", executable_name="arm-none-eabi-gcc"),
            CubeIDE_Plugin(plugin_id="objcopy", plugin_partial_name="gnu-tools-for-stm32", executable_name="arm-none-eabi-objcopy"),
            CubeIDE_Plugin(plugin_id="make", plugin_partial_name="externaltools.make", executable_name="make"),
            CubeIDE_Plugin(plugin_id="cubeprog", plugin_partial_name="cubeprogrammer", executable_name="STM32_Programmer_CLI")
        ]
        self.gdb_server_portno = 36789
        if cubeide_path is not None:
            self.set_cubeide_path(cubeide_path)

    def set_cubeide_path(self, cubeide_path: Path) -> None:
        """
        Set the cubeIDE path to the tools
        """
        def find_executable(base_p: Path):
            """ Search for the executable in the identified plugin directory """
            for p in base_p.glob("**/*"):
                if (not p.is_file() or p.suffix not in [".exe", ""] or (p.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) == 0)):  # os.access(k, os.X_OK) seems not to work
                    # Not an executable file
                    continue
                for plugin in self.__toollist__:
                    if p.stem == plugin.executable_name:
                        plugin.add_possible_path(p)
                        logger.debug(f"Found {plugin.executable_name} at {p}")

        self.cubeide_path = cubeide_path
        for p in (cubeide_path/"plugins").glob("*"):
            for k in self.__toollist__:
                if k.plugin_partial_name in p.name:
                    find_executable(p)

        # Ensure every tool is found or raise an error
        for plugin in self.__toollist__:
            try:
                plugin.resolve_executable()
            except FileNotFoundError as e:
                logger.error(f"Tool {plugin.executable_name} not found")
                raise FileNotFoundError(f"Cannot find all plugins in {cubeide_path}") from e 

    def get_tool_path(self, key):
        for plugin in self.__toollist__:
            if key == plugin.plugin_id:
                if plugin.executable is None:
                    raise RuntimeError("Tools discovery not done, call set_cubeide_path first")
                # If the plugin is found, return the executable path
                return plugin.executable
        raise ValueError(f"Tool {key} not found (not provided as a tool to discover)")

    @property
    def gdb_server(self) -> Path:
        return self.get_tool_path("gdb-server")

    @property
    def gdb_client(self) -> Path:
        return self.get_tool_path("gdb")

    @property
    def cube_programmer(self) -> Path:
        return self.get_tool_path("cubeprog")

    @property
    def make(self) -> Path:
        return self.get_tool_path("make")

    @property
    def objcopy(self) -> Path:
        return self.get_tool_path("objcopy")

    @property
    def gcc(self) -> Path:
        return self.get_tool_path("gcc")

    def reset_board(self) -> None:
        """
        Reset the board using Cube Programmer CLI
        """
        logger.info("Resetting the board")
        cmd = [self.cube_programmer, '-q', '-c', 'port=SWD', 'mode=powerdown', 'freq=2000', 'ap=1']
        rv = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        # Do not check return code as it will always fail
        if rv.returncode != 0:
            pass

    def flash_board(self, file:Path, address: int) -> None:
        """Flash the board using Cube Programmer CLI"""
        # Reset first
        self.reset_board()
        # Ensure the file is a ".bin" file (or create a temporary file...)
        tmp_file = None
        if file.suffix != ".bin":
            tmp_file = file.with_name(file.name + ".bin")
            shutil.copy(file, tmp_file)
        else:
            tmp_file = file
        # External loader for external flash (of the stm32n6-dk)
        external_loader = self.cube_programmer.parent / "ExternalLoader" / "MX66UW1G45G_STM32N6570-DK.stldr"
        cmd = [self.cube_programmer, '-q', '-c', 'port=SWD', 'mode=hotplug', 'freq=2000', 'ap=1', '--extload', str(external_loader), '--download', str(tmp_file), hex(address), "--verify"]
        logger.info(f"Loading {file.name} to the board at address {hex(address)}")
        rv = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        if tmp_file != file:
            #cleanup
            tmp_file.unlink()
        if rv.returncode != 0:
            logger.error(f"Error while flashing the weights: {rv.stdout.decode()}")
            raise RuntimeError("Error while flashing the weights")

    def _launch_gdb_server(self) -> None:
        # Start GDB Server
        # Popen is needed for background process
        logger.info("Starting GDB server")
        cmd = [self.gdb_server, "-d", "--frequency", "2000", "--apid", "1", "-v", "--port-number", str(self.gdb_server_portno), "-cp", str(self.cube_programmer.parent)]
        logger.debug(f'Command: {" ".join([str(k) for k in cmd])}')
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def launch_elf(self, file: Path) -> None:
        """Launch the ELF file on the board using GDB"""
        self._launch_gdb_server()
        # Start GDB Client (launch elf file provided)
        logger.info("Starting GDB client")
        cmd = [
            self.gdb_client,
            "-ex", f"target remote :{self.gdb_server_portno}",
            "-ex", "monitor reset",
            "-ex", "load",
            "-ex", "detach",
            "-ex", "quit",
            str(file)
        ]
        logger.debug(f'Command: {" ".join([str(k) for k in cmd])}')
        v = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        if v.returncode != 0:
            logger.error(f"Error while loading the ELF file: {v.stdout.decode()}")
            return

    def attach(self, file: Path, start_debug:bool) -> None:
        """Attach to the running target or show command to debug"""
        self._launch_gdb_server()
        # Start GDB Client (attach to the board)
        logger.info("Starting GDB client")
        cmd = [
            self.gdb_client,
            "-ex", f"\"target remote 127.0.0.1:{self.gdb_server_portno}\"",
            file
        ]
        if start_debug is True:
            to_add = ["-ex", "\"monitor reset\"", "-ex", "load"]
            cmd[3:3] = to_add
        # make command for bash
        cmd_cpy = cmd[:]
        for i,k in enumerate(cmd_cpy):
            if isinstance(k, Path):
                #cmd_cpy[i] = str(k)
                #cmd_cpy[i] = k.as_posix().replace("C:", "/c")
                cmd_cpy[i] = str(k) #k.as_posix().replace("C:", "/c")
        cmd_cpy = " ".join(cmd_cpy)
        logger.info(f'Run this to attach/debug: \n\n{cmd_cpy}\n\n')

    def show_tools(self) -> None:
        """
        Show the tools found in the cubeIDE path
        """
        logger.info("Tools found:")
        for plugin in self.__toollist__:
            if plugin.executable is not None:
                logger.info(f"{plugin.plugin_id}: {plugin.executable}")
            else:
                logger.warning(f"{plugin.plugin_id} not found, please check your CubeIDE installation")


def assert_file_provided(args):
    """
    Ensure that the file argument is provided
    """
    if args.file is None:
        raise ValueError("File argument is required for this command")
    if not args.file.exists():
        raise FileNotFoundError(f"File {args.file} does not exist")

def flash(args, toolbox: CubeIDEToolBox):
    """
    Flash the board using Cube Programmer CLI
    """
    # Convert address to int:
    try:
        args.address = int(args.address, 0)
    except ValueError:
        logger.error(f"Invalid address: {args.address}")
        return
    toolbox.flash_board(args.file, args.address)
    logger.info("Flashing done")

def launch(args, toolbox: CubeIDEToolBox):
    """
    Launch the ELF file on the board using GDB
    """
    toolbox.launch_elf(args.file)
    logger.info("Launching done")

def attach(args, toolbox: CubeIDEToolBox):
    """
    Attach to the running target
    """
    toolbox.attach(args.file, args.init)
    logger.info("Attaching done")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CubeIDE Toolbox")
    parser.add_argument("--cubeide_path", type=Path, required=True, help="Path to the CubeIDE installation")
    parser.add_argument("--file", type=Path, help="File to flash or launch")
    parser.add_argument("-v", "--verbose", action="store_true", help="Be verbose...")
    subparsers = parser.add_subparsers(help="Subcommands help", dest="subcommand")
    # Flasher
    flash_parser = subparsers.add_parser("flash", help="Flash the file to the board")
    flash_parser.add_argument("--address", required=True,  help="Address to flash the file to")
    flash_parser.set_defaults(func=flash)
    # Launcher
    launch_parser = subparsers.add_parser("launch", help="Launch the ELF file on the board")
    launch_parser.set_defaults(func=launch)
    # Attach
    attach_parser = subparsers.add_parser("attach", help="Attach to the running target")
    attach_parser.add_argument("--init", action="store_true", default=False, help="add load commands in the gdb arguments")
    attach_parser.set_defaults(func=attach)
    # show_tools
    show_tools_parser = subparsers.add_parser("show_tools", help="Show the tools found in the CubeIDE path")
    show_tools_parser.set_defaults(func=lambda args, toolbox: toolbox.show_tools())
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    if args.subcommand in ["flash", "launch", "attach"]:
        # Ensure the file argument is provided
        assert_file_provided(args)
    cide_tbx = CubeIDEToolBox(args.cubeide_path)
    # Call the specialized "main"
    args.func(args, toolbox=cide_tbx)