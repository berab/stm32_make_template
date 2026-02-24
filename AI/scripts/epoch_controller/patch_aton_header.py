#!/usr/bin/env python

import argparse
from pathlib import Path
from prepare_ec_trace import patch_aton_h

def main():
    parser = argparse.ArgumentParser(
        description="build ll_aton for epoch controller trace generation"
    )
    parser.add_argument(
        "--in_file", required=True, help="path to ATON.h to be patched"
    )
    parser.add_argument(
        "--out_file",
        required=True,
        help="path to the file where to place patched header file",
    )

    args = parser.parse_args()

    in_file = Path(args.in_file).absolute()
    out_file = Path(args.out_file).absolute()

    # patch ATON.H and place it output dir
    patch_aton_h(in_file, out_file)

if __name__ == "__main__":
    main()
