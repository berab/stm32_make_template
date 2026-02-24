import datetime as dt
from shutil import copyfile
from pathlib import Path
import logging
import subprocess
import time
import os

PORTNO = 61234
logging.basicConfig(level=logging.INFO)

logfile_p = Path(__file__).parent / "log.log"

def copy(src, dst):
    logging.info(f"Copying {src} to {dst}")
    try:
        copyfile(src, dst)
    except Exception as e:
        logging.error(f"Error copying {src} to {dst}: {e}")


def run_cmd(cmd, popen=False, env=None, logfile=None):
    print (" ".join(cmd))
    if logfile is None:
        logfile = logfile_p
    else:
        logfile.open('w').close()
    if popen:
        v = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT, universal_newlines=True)
        output = "--NO OUTPUT--"
    else:
        v = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, env=env)
        output = v.stdout.decode('utf-8', errors="replace").replace("\r\n","\n")
    with logfile.open('a', encoding="utf-8") as f:
        f.write("\n-----\nLAUNCHING " + " ".join(cmd) + "\n-----\n")
        f.write(output) 
    return v.returncode

#stm32cubeidec.exe compiler
cubeide_dir = Path("C:/Users/roustanb/TOOLS/STM32CubeIDE_1.17.0/STM32CubeIDE/")
gdbserver_prog = cubeide_dir / "plugins" / "com.st.stm32cube.ide.mcu.externaltools.stlink-gdb-server.win32_2.2.0.202409170845" / "tools" / "bin"/ "ST-LINK_gdbserver.exe"
gdb_prog = cubeide_dir / "plugins" / "com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.12.3.rel1.win32_1.1.0.202410251130" / "tools" / "bin" / "arm-none-eabi-gdb.exe"
iar_dir = Path("C:/Users/roustanb/TOOLS/IAR/IAR9.30.1/common/bin/")
cp_dir = Path("C:/Users/roustanb/TOOLS/STM32CubeIDE_1.17.0/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.0.202409170845/tools/bin")
cube_prog = cp_dir / "STM32_Programmer_CLI.exe"
sign_prog = cp_dir / "STM32_SigningTool_CLI.exe"
extload = cp_dir / "ExternalLoader/MX66UW1G45G_STM32N6570-DK.stldr"
original_proj_dir = Path("C:/Users/roustanb/CODE/stm32ai_N6_validation_project/Projects/NPU_Validation")
new_proj_dir = Path(__file__).parent
fsbl_dir = new_proj_dir / "FSBL" 
fsbl_dbg_elf = fsbl_dir / "Debug" / "Weights_encryption_FSBL.elf"


with logfile_p.open('w') as f:
    f.write(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
results_dir = Path(__file__).parent / "results"
results_dir.mkdir(exist_ok=True) 


# Compile fsbl
cmd = [str(cubeide_dir / "stm32cubeide.exe"), "--launcher.suppressErrors", "-nosplash", "-application", "org.eclipse.cdt.managedbuilder.core.headlessbuild", "Weights_encryption_FSBL"]
v = run_cmd(cmd)

# gdbserver
logging.info(f"Killing gdbserver")
os.system("taskkill /f /im  ST-LINK_gdbserver.exe")
logging.info(f"Launching gdbserver")
cmd = [str(gdbserver_prog), "-d", "--frequency", "2000", "--apid", "1", "-v", "--port-number", str(PORTNO), "-cp", str(cube_prog.parent)]
v = run_cmd(cmd, popen=True)
# gdb
logging.info(f"Launching gdb")
#cmd = " ".join(['"'+str(gdb_prog.as_posix())+'"', '"'+str(fsbl_dbg_elf.as_posix())+'"']).replace("C:", "/c")
#print(cmd)
cmd = [str(gdb_prog), "-batch", "--command="+str(fsbl_dir/"launch.gdb"), str(fsbl_dbg_elf)]
v = run_cmd(cmd)

logging.info(f"Done")