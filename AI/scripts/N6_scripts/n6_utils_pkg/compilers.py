from dataclasses import dataclass
from enum import Enum, auto
import logging
import os
from pathlib import Path
import re
import subprocess
from typing import Protocol
import time
import platform
import shlex
import shutil

# Timeout in seconds when running a command. 15s is needed to load 1MB
TIMEOUT_PROCESS = 300


class CompilerType(Enum):
    IAR = auto()
    GCC = auto()
    EWARM = auto()
    MDK_ARM = auto()
    STM32CubeIDE = auto()
    Nucleo_App = auto()

def parse_compiler_type(s: str) -> CompilerType:
    arg = s.lower()
    for k in CompilerType:
        if arg == k.name.lower():
            return k
    raise ValueError(f"Compiler type {s} unknown (valid values are iar, gcc)")

class Compiler(Protocol):
    path_to_compiler_binary: Path
    path_to_debugger_binary: Path
    path_to_project: Path
    path_to_debugger_template: Path
    project_config_name: str
    logger: logging.Logger
    launch_timeout: int
    st_link_sn: str
    macro_name: str

    def compile_project(self, clean:bool = False) -> int:
        """Compiles the project for the current compiler

        Parameters
        ----------
        clean : bool
            If True, cleans the project before compiling

        Returns
        -------
        int
            Return code from the binary call
        """
        ...
    
    def load_and_run(self) -> int:
        """
        Loads the board with the program & the memory files then run

        Returns
        -------
        int
            Return code from the binary call
        """
        ...

    def add_memory_file_to_load(self, memory_name: str, memory_path: Path) -> None:
        """
        Add a memory file to load to the macro file that is launched before "running"
        the target

        Parameters
        ----------
        memory_name : str
            Name of the memory range to load
        memory_path : Path
            Path to the memory file to load (should be a .hex file)
        """
        ...

    def add_breakpoint_to_main_macro(self, lineno: int) -> None:
        """
        Replaces the placeholder of the template macro file for breakpoint

        Parameters
        ----------
        lineno : int
            Line to establish a breakpoint (that will load memories on hit)
        """
        ...

    def dump_macro_file(self) -> None:
        """
        Dumps the macro file (template that has been modified)
        """
        ...

@dataclass
class IARCompiler:
    path_to_compiler_binary: Path
    path_to_debugger_binary: Path
    path_to_project: Path
    path_to_debugger_template: Path
    project_config_name: str
    logger: logging.Logger
    launch_timeout: int = TIMEOUT_PROCESS
    st_link_sn: str = None
    project_name: str = "Project"  # Name of the project (hardcoded)
    macro_name: str = "n6.mac"  # Name of the macro file (hardcoded)

    def __post_init__(self) -> None:
        self.macro_text = self.path_to_debugger_template.resolve().read_text()

    @classmethod
    def get_compiler_exe(cls) -> str:
        """
        Returns the name of the executable for the compiler
        """
        return "iarbuild.exe"
    
    def compile_project(self, clean:bool = False) -> int:
        project_file = self.path_to_project / "EWARM" / (self.project_name + ".ewp")
        # use the first project file found
        cmd = [self.path_to_compiler_binary, project_file, "-make", self.project_config_name, '-log', 'all']
        if clean is True:
            # "rebuild": the default -make only compiles changes, -build cleans first, then rebuilds
            cmd[2] = "-build"
        cmd = [str(c) for c in cmd]
        self.logger(logging.DEBUG, f"Compiling project with command: {' '.join([str(k) for k in cmd])}")
        v = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        with Path("compile.log").open('w') as f:
            f.write(v.stdout.decode('utf-8').replace("\r\n","\n"))
        return v.returncode
    
    def load_and_run(self) -> int:

        def change_path_ending_with(end:str, replacement:Path, to_search:str) -> str:
            out_s = to_search
            for k in re.findall(f"\"(.*{end})\"", to_search):
                if end.startswith("."):
                    # If this is only a file extension, replace the stuff without creating a new path
                    out_s = out_s.replace(k, str(replacement) + end)
                else:
                    out_s = out_s.replace(k, str(replacement / end))
            return out_s
        def change_full_path_to_file(file_pattern:str, full_path:Path, to_search:str) -> str:
            """ 
            try to find all pathes in the string that match the file_pattern
            replace all the path up to the filename with the full_path argument
            """
            out_s = to_search
            while (m:=re.search(fr"\"(.*)([\\/].*{file_pattern})\"", out_s)) is not None:
                # Replace all paths with the final filename with the fullpath given as argument
                replaced_out = out_s.replace(m.group(1), str(full_path))
                if replaced_out == out_s:
                    break
                out_s = replaced_out
            for k in re.findall(f"\"(.*?[\\/]{file_pattern})\"", to_search):
                out_s = out_s.replace(k, str(full_path) + "\\" + "")
            return out_s
        
        def verify_general_xcl(f:Path):
            """
            Check that the current project path is contained in information stored in the XCL file
            This file is not re-generated after moving files and may result in inconsistent behaviour

            Parameters
            ----------
            f : Path
                Path to the .xcl file
            """
            s = f.read_text()
            s_out = s
            compiler_base_path = (self.path_to_compiler_binary.parent / ".." / "..").resolve()
            s_out = change_full_path_to_file(r"arm[\\/].*.dll", compiler_base_path, s_out)
            s_out = change_full_path_to_file(r"arm[\\/].*.board", compiler_base_path, s_out)
            s_out = change_path_ending_with("Project.out", self.path_to_project / "EWARM" / self.project_config_name / "Exe", s_out)
            s_out = change_path_ending_with(self.macro_name, self.path_to_project / "EWARM" , s_out)
            m = re.match(r".*^\"(?P<O_FILE>.*?\.out)\".*?\n.*^--macro=\"(?P<MAC_FILE>.*?)\"", s, flags=re.MULTILINE|re.DOTALL)
            if s_out != s:
                with f.open("w") as fop:
                    self.logger(logging.WARNING, f"Patching general.xcl file")
                    fop.write(s_out)
            
        def verify_driver_xcl(f:Path):
            """
            Check that the current project path is contained in information stored in the driverXCL file
            This file is not re-generated after moving files and may result in inconsistent behaviour

            Parameters
            ----------
            f : Path
                Path to the .xcl file
            """
            s = f.read_text()
            s_out = s
            compiler_base_path = (self.path_to_compiler_binary.parent / ".." / "..").resolve()
            s_out = change_full_path_to_file(r"arm[\\/].*.ddf", compiler_base_path, s_out)
            if s_out != s:
                with f.open("w") as fop:
                    self.logger(logging.WARNING, f"Patching driver.xcl file")
                    fop.write(s_out)

        xcldir = self.path_to_project / "EWARM" / "settings"
        xcls = [f for f in xcldir.glob(f"**/*.xcl")]
        # filter xcls to only use the ones with the proper project
        xcls = [k for k in xcls if re.match(rf"{self.project_name}\.{self.project_config_name}\.(?:driver|general)", k.name)]

        generalxcl = ""
        backendxcl = ""
        for f in xcls:
            if "general" in f.name:
                verify_general_xcl(f)
                generalxcl = str(f)
            if "driver" in f.name:
                verify_driver_xcl(f)
                backendxcl = str(f)

        if generalxcl == "" or backendxcl == "":
            self.logger(logging.ERROR, "file driver.xcl or general.xcl not found for " + str(self.project_config_name) + " into " + str(xcldir))
            raise Exception("")

        cmd = [str(self.path_to_debugger_binary), "-f", generalxcl, "--backend", "-f", backendxcl]
        
        # Add serial number arguments for St-link if needed
        if self.st_link_sn is not None:
            # add this to the command line, not in the driver.xcl file as this change is not meant to be permanent
            cmd.append(f"--drv_communication=USB:#{self.st_link_sn}")
        
        # Better to run the command with a timeout, in case the board crashes
        # process = subprocess.run(cmd, capture_output=True, shell=True)
        process = run_with_timeout(cmd, loggr=self.logger, timeout=self.launch_timeout)

        return process.returncode


    def add_memory_file_to_load(self, memory_name: str, memory_path: Path) -> None:
        """
        (the link is written as a windows path with backslashes as iar seems to have issues
        with other formats)"""
        # Duplicate template line
        ss = re.sub(r"^## (.*)$", r"  \1\n## \1", self.macro_text, flags=re.MULTILINE)
        # Compute path to hex file with \\ only (MAC files seems not to handle /)
        sanitized_path = memory_path.as_posix().replace("/",r"\\\\")
        # Proceed with replacements
        ss = re.sub(r"##RAMNAME##", memory_name, ss, count = 1)
        ss = re.sub(r"##RAMFILE##", sanitized_path, ss, count = 1 )
        self.macro_text = ss
    
    def add_breakpoint_to_main_macro(self, lineno: int) -> None:
        """Replaces the ##BREAKLINE## placeholder by a line number (str)"""
        self.macro_text = self.macro_text.replace("##BREAKLINE##", str(lineno))

    def dump_macro_file(self) -> None:
        self.macro_text = re.sub("^##.*$", "",self.macro_text, flags=re.MULTILINE)

        with (self.path_to_project / "EWARM" / self.macro_name).resolve().open('w') as f:
            f.write(self.macro_text)

@dataclass
class GCCCompiler:
    path_to_compiler_binary: Path
    path_to_debugger_binary: Path
    path_to_project: Path
    path_to_debugger_template: Path
    project_config_name: str # Not used for now
    logger: logging.Logger
    path_to_gdb_server: Path        #-- specific to gcc
    path_to_cube_programmer: Path   #-- specific to gcc
    path_to_make: Path   #-- specific to gcc
    macro_name: str = "n6_commands.gdb"  # Name of the macro file (hardcoded)
    
    launch_timeout: int = TIMEOUT_PROCESS
    st_link_sn: str = None
    gdb_port_number: int = 61234    #-- specific to gcc

    def __post_init__(self) -> None:
        self.path_to_command_out = self.path_to_project / "armgcc" / self.macro_name
        self.path_to_cube_programmer = self.path_to_cube_programmer.parent
        self.macro_text = self.path_to_debugger_template.resolve().read_text()
        # @ TODO : ensure this is mandatory (calling <executable> without the .exe extension on windows seems to work)
        self._gdb_server_exe = self.path_to_gdb_server.resolve()/ self.get_debugger_server_exe()
        self._gdb_exe = self.path_to_compiler_binary.parent.resolve() / self.get_debugger_exe()
        # Ensure computed executable paths exist
        for p,s in zip([self._gdb_server_exe, self._gdb_exe], ["GDB server", "GCC"]):
            if not p.exists():
                raise FileNotFoundError(f"Executable {p} does not exist. Please check the path to the {s} binaries.")

    @classmethod
    def get_debugger_server_exe(cls) -> str:
        """
        Returns the name of the debug server executable
        """
        if platform.system().lower() == "windows":
            return "ST-LINK_gdbserver.exe"
        else:
            return "ST-LINK_gdbserver"

    @classmethod 
    def get_debugger_exe(cls) -> str:
        """
        Returns the name of the debugger executable
        """
        if platform.system().lower() == "windows":
            return "arm-none-eabi-gdb.exe"
        else:
            return "arm-none-eabi-gdb"
        
    def compile_project(self, clean:bool = False) -> int:
        targets = ["all"]
        if clean is True:
            # Call the clean target before building all
            targets.insert(0, "clean")
        cmd = [str(self.path_to_make), *targets, shlex.quote(f"GCC_PATH={self.path_to_compiler_binary.parent.as_posix()}"), shlex.quote(f"BUILD_CONF={self.project_config_name}")]
        # Prepend the path to make in the PATH (as it may contain useful tools such as rm, mkdir, ...)
        env = os.environ.copy()
        env["PATH"] = str(self.path_to_make.parent) + os.pathsep + env["PATH"]
        self.logger(logging.DEBUG, f"Compiling project with command: {' '.join([str(k) for k in cmd])}")
        v = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, env=env, cwd=str((self.path_to_project/"armgcc").resolve()))
        with Path("compile.log").open('w') as f:
            f.write(' '.join([str(k) for k in cmd]))
            f.write("\n\n")
            f.write(v.stdout.decode('utf-8').replace("\r\n","\n"))
        return v.returncode
    
    def load_and_run(self) -> int:
        # Launch GDB server first
        cmd = [self._gdb_server_exe, "-d", "--frequency", "2000", "--apid", "1", "-v", 
               "--port-number", str(self.gdb_port_number), "-cp", self.path_to_cube_programmer.as_posix()]
        # Add serial number arguments for St-link if needed
        if self.st_link_sn is not None:
            idx = cmd.index("--frequency")
            cmd = cmd[:idx]+ ["--serial-number", self.st_link_sn] + cmd[idx:]
        self.logger(logging.DEBUG, f"Starting gdbserver with command: {' '.join([str(k) for k in cmd])}")
        proc = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE, text=True)
        try:
            o,e = proc.communicate(timeout=.01)
        except subprocess.TimeoutExpired:
            # The process is running... waiting for gdb-client connections ... ?
            self.logger(logging.DEBUG, "gdbserver waiting for connections...")
        else:
            # gdb server exited prematurely... report error...
            self.logger(logging.ERROR, "gdbserver exited prematurely: " + (o+e).replace("\r\n","\n"))
            return proc.returncode

        # Then call the debugger
        #cmd =  [self.path_to_compiler_binary.parent / "arm-none-eabi-gdb.exe", "-batch", f"--command={self.path_to_command_out.as_posix()}", (self.path_to_project/"armgcc"/"build"/"Project.elf").as_posix()]
        cmd =  [self._gdb_exe.as_posix(), "-batch",
                f"--command={self.path_to_command_out.as_posix()}",
                (self.path_to_project / "armgcc" / "build" / self.project_config_name / "Project.elf").as_posix()]
        self.logger(logging.DEBUG, f"Debugging with command: {' '.join([str(k) for k in cmd])}")
        v = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        self.logger(logging.DEBUG, v.stdout.decode('utf-8').replace("\r\n","\n"))
        return v.returncode

    def add_memory_file_to_load(self, memory_name: str, memory_path: Path) -> None:
        """
        (the link is written as a windows path with backslashes as iar seems to have issues
        with other formats)"""
        # Duplicate template line
        ss = re.sub(r"^## (.*)$", r"  \1\n## \1", self.macro_text, flags=re.MULTILINE)
        # Compute path to hex file with \ only (gdb seems to prefer this syntax (and does not allows /)
        sys_platform = platform.system()
        if sys_platform == 'Windows': 
            sanitized_path = memory_path.as_posix().replace("/",r"\\")
        else:
            sanitized_path = memory_path.as_posix()
        # Ensure no spaces in paths, because restore does not work with spaces (gdb limitation, tried with quotes and escaping: did not work)
        self.validate_gcc_args(sanitized_path)
        self.validate_gcc_args(memory_name)
        # Proceed with replacements
        ss = re.sub(r"##RAMNAME##", memory_name, ss, count = 1)
        ss = re.sub(r"##RAMFILE##", sanitized_path, ss, count =1 )
        self.macro_text = ss

    def add_breakpoint_to_main_macro(self, lineno: int) -> None:
        """Replaces the ##BREAKLINE## placeholder by a line number (str)"""
        self.macro_text = self.macro_text.replace("##BREAKLINE##", str(lineno))

    def dump_macro_file(self) -> None:
        self.macro_text = re.sub("^##.*$", "",self.macro_text, flags=re.MULTILINE)
        elf_path = (self.path_to_project / "armgcc" / "build"/ self.project_config_name / "Project.elf").as_posix()
        # Ensure project path has no spaces as it may be problematic when executing the macro file
        self.validate_gcc_args(elf_path)
        self.macro_text = self.macro_text.replace("build/Project.elf", elf_path)
        self.macro_text = self.macro_text.replace("127.0.0.1:61234", f"127.0.0.1:{self.gdb_port_number}")
        with self.path_to_command_out.resolve().open('w') as f:
            f.write(self.macro_text)

    def validate_gcc_args(self, s: str):
        if re.search(r"\s", s):
            raise ValueError(f"When using GCC, paths should not contain spaces: {s}\nPlease consider using paths without spaces")



def run_with_timeout(cmd, loggr:logging.Logger, timeout: int):
    """
    Run a command with a timeout
    cmd         The command to run
    logger      Logger to display messages
    timeout     Timeout to stop the process
    """
    loggr(logging.DEBUG, f"Running command: {' '.join([str(k) for k in cmd])} with timeout {timeout}s")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    start_time = time.monotonic()
    elapsed_time = 0
    # While the process is running
    while process.poll() is None:
        elapsed_time = int(time.monotonic() - start_time)
        if elapsed_time > timeout:
            loggr(logging.DEBUG, process.stdout.peek().decode('utf-8').replace("\r\n","\n"))
            process.terminate()
            loggr(logging.ERROR, f"Loading memories too long ({timeout}s)! Probably a crash of FW following an access to the external RAM/flash !")
            loggr(logging.ERROR, "Fix the issue, reboot the board an try again.")
            raise TimeoutError(f"Command {cmd} took more than {timeout} seconds")
        time.sleep(1)  # Wait 1s for CPU

    out, err = process.communicate()
    loggr(logging.DEBUG, out.decode('utf-8').replace("\r\n","\n"))
    # Display elapsed time for a long loading more than 60s
    if elapsed_time > 60:
        loggr(logging.INFO, f"The command took {elapsed_time} seconds")
    return process