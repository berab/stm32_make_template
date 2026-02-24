import logging
import os
from pathlib import Path
import time

import encrypt_neural_art as encr
from cubeIDE_toolbox import CubeIDEToolBox
import log_utils

logger = log_utils.EncryptionLogger.get_logger()
embedded_tool_elf_p = Path(__file__).parent.parent / "c" /  "Weights_encryption" / "FSBL" / "Debug" / "Weights_encryption_FSBL.elf"

def main(args):

    toolbox = CubeIDEToolBox(args.cubeide)
    # 1 - Load the ELF file to the board, and run it through debug session
    if args.skip_debug is False:
        # Reset the board
        toolbox.reset_board()
        toolbox.launch_elf(embedded_tool_elf_p)
        logger.info("Waiting for the firmware to initialize")
        time.sleep(1)
    # 2 - Launch the encrypt neural-art script
    logger.info("Starting encryption script")
    w_init_file, w_encrypted_file, w_addr = encr.main(args)
    # 3 - Postprocess the files to use them with the n6_loader script
    if args.postprocess:
        logger.info("Postprocessing the files")
        initial_weights_mtime = w_init_file.stat().st_mtime
        logger.info(f'Backup of original unencrypted weights: {w_init_file.name} -> {w_init_file.with_suffix(".unencrypted").name}')
        logger.info(f'Replacing original file with encrypted weights: {w_encrypted_file.name} -> {w_init_file.name}')
        initial_suffix = w_init_file.suffix
        w_encrypted_file = w_encrypted_file.replace(w_init_file.with_suffix(".encrypted"))
        w_init_file = w_init_file.replace(w_init_file.with_suffix(".unencrypted"))
        w_encrypted_file = w_encrypted_file.replace(w_encrypted_file.with_suffix(initial_suffix))
        # Get all the files that looks like they are related to the init file (generated ~ the same time)
        files_to_process = []
        for f in w_init_file.parent.glob("*"):
            if f.is_file() and abs(f.stat().st_mtime - initial_weights_mtime) < 10:
                files_to_process.append(f)
        files_to_process.append(w_encrypted_file)
        logger.debug("Modifying modification time of the files")
        for f in files_to_process:
            logger.debug("\t" + f.name)
            # Change the access time/modif time to the one of the init file
            os.utime(f, (w_init_file.stat().st_atime, w_init_file.stat().st_mtime))
        if args.flash:
            logger.info("Flashing the encrypted weights to the board")
            toolbox.flash_board(w_encrypted_file, w_addr)
            # Reset the board, so the user has not to do it manually :P
            toolbox.reset_board()
    logger.info("Done")

if __name__ == "__main__":
    parser = encr.create_parser()
    parser.description = "End-To-End encryption tool for weights using Neural Art"
    parser.add_argument("--cubeide", type=lambda x: Path(x), required=True, help="Path to cubeIDE install dir")
    parser.add_argument("--skip_debug", action="store_true", default=False, help="Skip loading the encryption tool elf file to the board")
    parser.add_argument("--postprocess", action="store_true", default=False, help="Postprocess the files to use them with the n6_loader script")
    parser.add_argument("--flash", action="store_true", default=False, help="After postprocessing, flash the encrypted weights to the board")
    args = parser.parse_args()
    if args.verbose is True:
        log_utils.EncryptionLogger.set_verbosity(logging.DEBUG)
    else:
        log_utils.EncryptionLogger.set_verbosity(logging.INFO)
    
    main(args)

