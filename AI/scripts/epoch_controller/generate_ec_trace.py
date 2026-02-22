#!/usr/bin/env python

import os
import argparse
from pathlib import Path
import shutil
import subprocess
from prepare_ec_trace import run_external_cmd_and_report_error, get_target_dirname


def buildtracetool(
        cc: Path, cxx: Path, cfile: Path, etracedir: Path, workdir: Path, toolname: str, nostatic: bool, debug: bool, verbose: bool
):
    """
    Create a trace tool from a C file that contains a trace blob, linked with the tracing lib.
    """
    ofile = workdir / "trace_blob.o"
    include_etracedir = etracedir / "include"
    lib_etracedir = etracedir / "lib"
    etrace_lib1 = lib_etracedir / "libectracer.a"
    etrace_lib2 = lib_etracedir / "ll_aton_trace.a"
    trace_program = workdir / toolname
    # Create object file for the trace blob
    cmd =  [
        str(cc),
        "-I",
        str(include_etracedir),
        str(cfile),
        "-c",
        "-o",
        str(ofile),
    ]
    if debug:
        cmd.append("-g")
    run_external_cmd_and_report_error(cmd, cc.parent, verbose)

    # Link the trace blob with the tracing library to create a trace program
    cmd = [
        str(cxx),
        str(ofile),
        str(etrace_lib2),
        str(etrace_lib1),
        str(etrace_lib2),
        "-o",
        str(trace_program),
    ]
    if debug:
        cmd.append("-g")
    if nostatic is False:
        if get_target_dirname() in ["mac", "macarm"]:
            # Do not do a static build on Mac-OS (will not work unless all libs are static, which is not the case)
            pass
        else:
            # Do static builds on other platforms to prevent possible issues upon execution (esp. for windows)
            cmd.append("-static")
    run_external_cmd_and_report_error(cmd, cc.parent, verbose)


def generate_trace(trace_program: str, workdir: Path):
    """
    Create a trace by running the trace program and gathering outputs.
    The trace file is written to the specified output file.
    """
    pname = workdir / trace_program
    subprocess.run([pname], text=True, check=True, cwd=workdir.absolute())


def main():
    parser = argparse.ArgumentParser(
        description="Generate execution trace for epoch controller configuration"
    )
    parser.add_argument(
        "--ectrace",
        required=True,
        help="path to the directory that contains precompiled ll_aton for tracing",
    )
    parser.add_argument(
        "--inputfile", required=True, help="Input file: file with code to be traced"
    )
    parser.add_argument(
        "--workdir", required=False, type=str, default="./workdir", help="working dir"
    )
    parser.add_argument(
        "--debug", required=False, action='store_true', help="compile with -g"
    )
    parser.add_argument(
        "--no-static", required=False, action='store_true', help="avoid static linking"
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
            "--cxx",
            required=False,
            type=str,
            default=os.environ.get("CXX"),
            help="Specify CXX to use",
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
            "--cxx",
            required=False,
            type=str,
            default=shutil.which("g++"),
            help="Specify CXX to use",
        )

    args = parser.parse_args()

    cc = Path(args.cc).absolute()
    cxx = Path(args.cxx).absolute()
    etracedir = Path(args.ectrace).absolute()
    ifile = Path(args.inputfile).absolute()
    workdir = Path(args.workdir).absolute()

    workdir.mkdir(parents=True, exist_ok=True)

    if not etracedir.exists():
        print("Tracing library path `", str(etracedir) + "`", "does not exists!")
        raise AssertionError("Not existing tracing library path.")

    if not ifile.exists():
        print("Input file `", ifile.name + "`", "does not exists!")
        raise AssertionError("Not existing input file.")

    trace_program = "trace_prog"

    buildtracetool(cc, cxx, ifile, etracedir, workdir, trace_program, args.no_static, args.debug, args.verbose)

    generate_trace(trace_program, workdir)


if __name__ == "__main__":
    main()
