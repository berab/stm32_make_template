#!/usr/bin/env python

import argparse
from pathlib import Path
import re
import platform
import shutil
import subprocess
import os

def report_error(process: subprocess.CompletedProcess, verbose: bool):
    """
    Raise an exception if the return code of the process is not 0
    otherwise print the stdout and stderr if the verbose flag is set.
    """
    if process.returncode != 0:
        raise SystemError(
            f"{process.args} RETURN CODE = {process.returncode} -- stdout = {process.stdout} -- stderr = {process.stderr}"
        )
    if verbose is True:
        banner = "*" * 50
        print(
            f"""\n\n{banner}\n{process.args}\nRun process OK\nstdout={process.stdout}\n\nstderr={process.stderr}\n{banner}\n\n"""
        )


def run_external_cmd_and_report_error(cmd: list, cwd: Path, verbose: bool):
    """
    Run an external command with subprocess.run and report errors if any.
    """
    if verbose:
        print("Running command: " + " ".join(cmd))
    rv = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    report_error(rv, verbose)


def get_target_dirname():
    """return the target directory name"""
    linux_platform_references = ("linux", "nix", "nux", "aix")
    macos_platform_references = ("mac", "darwin")
    windows_platform_references = ("windows", "msys", "cygwin")
    current_os = platform.system().lower()
    if any(p in current_os for p in windows_platform_references):
        return "windows"
    if any(p in current_os for p in macos_platform_references):
        if "x86_64" in platform.uname().machine:
            return "mac"
        if "arm" in platform.uname().machine:
            return "macarm"
        raise ValueError("Platform unknown")
    if any(p in current_os for p in linux_platform_references):
        return "linux"
    raise ValueError("Platform unknown")


def initialize_output_dir(srcdir: Path, outputdir: Path, workdir: Path):
    """
    Create output directories and copy the necessary files to inc/lib/workspace directories.
    """
    inc_srcdir = srcdir / "include"
    src_srcdir = srcdir / "src"
    lib_srcdir = srcdir / "lib" / get_target_dirname()
    inc_outputdir = outputdir / "include"
    lib_outputdir = outputdir / "lib"

    inc_outputdir.mkdir(parents=True, exist_ok=True)
    lib_outputdir.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)

    for header in inc_srcdir.glob("*.h"):
        shutil.copy(header, inc_outputdir)

    shutil.copy(lib_srcdir / "libectracer.a", lib_outputdir)

    shutil.copy(src_srcdir / "ll_aton.c", workdir)
    shutil.copy(src_srcdir / "ll_aton_util.c", workdir)
    shutil.copy(src_srcdir / "ll_aton_cipher.c", workdir)


def configure_include_lib(src_conf_file, dest_conf_file, cgating):
    """
    Update the configuration file for libraries compilation
    """
    dest_conf_file.write_text(
        "#define LL_ATON_ENABLE_CLOCK_GATING  "
        + str(cgating)
        + "\n"
        + "\n"
        + src_conf_file.read_text()
    )


def patch_aton_h(input_fname, output_fname):
    """
    Patch ATON.h to support trace
    """
    prog_set = re.compile(
        #r"#define.*?\(uintptr_t\)((?:[A-Za-z]|[0-9]|_)+)(\(UNIT\)).*?(while)"
        r"#define.*?\(uintptr_t\)((?:[A-Za-z]|[0-9]|_)+)_ADDR\((UNIT)\).*?(while) \(0\);"
    )
    prog_get = re.compile(
        #r"#define(.*?_GET)(\(UNIT\))(.*?((?:[A-Za-z]|[0-9]|_)+)(\(UNIT\)).*?)$"
        r"#define (.*?)_GET(\(UNIT\)).*?((?:[A-Za-z]|[0-9]|_)+)(\(UNIT\)).*?$"
    )
    with open(output_fname.as_posix(), "w", encoding="utf-8") as ofile:
        ofile.write("#include <stdint.h>\n")
        ofile.write("extern void ec_trace_write(uintptr_t reg, unsigned int val);\n")
        ofile.write("extern void ec_trace_unsupported(void);\n")
        ofile.write("\n")
        ofile.write("#define ATON_HIDE_REG_MACROS 1\n")
        ofile.write("#define ATON_GET_REG32(ADDR) (ec_trace_unsupported(), 0)\n")
        ofile.write(
            "#define ATON_SET_REG32(ADDR, DATA) ec_trace_write((uintptr_t)(ADDR), DATA)\n"
        )
        ofile.write("\n")
        with open(input_fname.as_posix(), encoding="utf-8") as ifile:
            for line in ifile:
                line = line.rstrip("\n")
                c = prog_set.match(line)
                if c:
                    ofile.write(
                        "#define "
                        + c.group(1)
                        + "_SET("
                        + c.group(2)
                        + ", DATA) do { ATON_SET_REG32("
                        + c.group(1)
                        + "_ADDR("
                        + c.group(2)
                        + "), DATA); } while (0)\n"
                    )
                else:
                    r = prog_get.match(line)
                    if r:
                        ofile.write(
                            "#define "
                            + r.group(1)
                            + "_GET"
                            + r.group(2)
                            + " ATON_GET_REG32("
                            + r.group(1)
                            + "_ADDR(UNIT))\n"
                        )
                    else:
                        ofile.write(line + "\n")

def copy_extra_files(srcdir: Path, outputdir: Path):
    extra_aton_file = srcdir / "ATON-idxs.h"
    if extra_aton_file.exists():
        shutil.copy(extra_aton_file, outputdir / "ATON-idxs.h")

def buildlib(cc: Path, ar: Path, workdir: Path, outputdir: Path, debug: bool, verbose: bool):
    """
    Effective build of the library
    """
    inc_outputdir = outputdir / "include"
    lib_outputdir = outputdir / "lib"
    # Build the ll_aton object
    cmd = [
        str(cc),
        "-I",
        str(inc_outputdir),
        str(workdir / "ll_aton.c"),
        "-c",
        "-o",
        str(workdir / "ll_aton.o"),
    ]
    if debug:
        cmd.append("-g")
    run_external_cmd_and_report_error(cmd, cc.parent, verbose)
    # Build the ll_aton_util object
    cmd = [
        str(cc),
        "-I",
        str(inc_outputdir),
        str(workdir / "ll_aton_util.c"),
        "-c",
        "-o",
        str(workdir / "ll_aton_util.o"),
    ]
    if debug:
        cmd.append("-g")
    run_external_cmd_and_report_error(cmd, cc.parent, verbose)
    # Build the ll_aton_cipher object
    cmd = [
        str(cc),
        "-I",
        str(inc_outputdir),
        str(workdir / "ll_aton_cipher.c"),
        "-c",
        "-o",
        str(workdir / "ll_aton_cipher.o"),
    ]
    if debug:
        cmd.append("-g")
    run_external_cmd_and_report_error(cmd, cc.parent, verbose)
    # Archive both objects into a library
    cmd = [
        str(ar),
        "cr",
        str(lib_outputdir / "ll_aton_trace.a"),
        str(workdir / "ll_aton.o"),
        str(workdir / "ll_aton_util.o"),
        str(workdir / "ll_aton_cipher.o"),
    ]
    run_external_cmd_and_report_error(cmd, ar.parent, verbose)


def main():
    parser = argparse.ArgumentParser(
        description="build ll_aton for epoch controller trace generation"
    )
    parser.add_argument(
        "--srcdir", required=True, help="Source directory of ectracer ll_aton code"
    )
    parser.add_argument("--atonh", required=True, help="path to ATON.h to be used")
    parser.add_argument(
        "--outdir",
        required=True,
        help="path to the directory where to place precompiled ll_aton for tracing",
    )
    parser.add_argument(
        "--no-clockgating",
        required=False,
        action="store_true",
        default=False,
        help="Disable Clock gating",
    )
    parser.add_argument(
        "--debug", required=False, action='store_true', help="compile with -g"
    )
    parser.add_argument(
        "--verbose", required=False, action='store_true', help="verbose"
    )
    if get_target_dirname() in ["msys"]:
        parser.add_argument(
            "--cc",
            required=False,
            type=str,
            default=os.environ.get("CC"),
            help="Specify CC to use",
        )
        parser.add_argument(
            "--ar",
            required=False,
            type=str,
            default=os.environ.get("AR"),
            help="Specify AR to use",
        )
    else:
        parser.add_argument(
            "--cc",
            required=False,
            type=str,
            default=shutil.which("gcc"),
            help="Specify CC to use",
        )
        parser.add_argument(
            "--ar",
            required=False,
            type=str,
            default=shutil.which("ar"),
            help="Specify AR to use",
        )
    parser.add_argument(
        "--work-dir", required=False, type=str, default="./workdir", help="working dir"
    )

    args = parser.parse_args()

    cc = Path(args.cc).absolute()
    ar = Path(args.ar).absolute()
    srcdir = Path(args.srcdir).absolute()
    atonhdir = Path(args.atonh).absolute()
    outputdir = Path(args.outdir).absolute()
    workdir = Path(args.work_dir).absolute()

    assert srcdir.exists(), "ll_aton sources not found"
    assert (atonhdir / "ATON.h").exists(), "ATON.h file doesn't exist!"

    # create output directory
    outputdir.mkdir(parents=True, exist_ok=True)

    # copy ll_aton files in output dir
    initialize_output_dir(srcdir, outputdir, workdir)

    # create configuration
    configure_include_lib(
        srcdir / "include" / "ll_aton_config.h",
        outputdir / "include" / "ll_aton_config.h",
        0 if args.no_clockgating else 1,
    )

    # patch ATON.H and place it output dir
    patch_aton_h(atonhdir / "ATON.h", outputdir / "include" / "ATON.h")
    copy_extra_files(atonhdir, outputdir / "include")

    # create support binary and copy it in output dir
    buildlib(cc, ar, workdir, outputdir, args.debug, args.verbose)


if __name__ == "__main__":
    main()
