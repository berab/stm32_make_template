###################################################################################
#   Copyright (c) 2024, 2025 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Module implementing logging facilities
"""

import logging
import sys
from typing import Union, Optional, Any

from colorama import init, Fore, Style, deinit


def print_table(header, rows, pr_fn, colalign=None,
                title: Optional[str] = None, sep: bool = False,
                tablefmt="pretty"):
    """."""

    from tabulate import tabulate

    res = tabulate(rows, headers=header, tablefmt=tablefmt,
                   colalign=colalign, disable_numparse=True)

    nline = ''
    if sep:
        pr_fn('')
    lines_ = res.splitlines()
    if tablefmt == 'simple':
        nline = lines_[1]
    if nline:
        pr_fn(nline)
    for line in lines_:
        pr_fn(line)
    if nline:
        pr_fn(nline)
    if title:
        pr_fn(' Table: ' + title)
    if sep:
        pr_fn('')


class IndentFormatter(logging.Formatter):
    """Default Log Formatter"""

    indent = 0
    inc = 0

    def __init__(self, format_str="%(levelname)s%(message)s"):
        super(IndentFormatter, self).__init__(fmt=format_str)

    def enable_inc(self, enable: bool = True):
        """."""
        self.inc = 3 if enable else 0

    def indent_msg(self, msg):
        """."""
        inc = 0
        if msg.startswith('->'):
            inc = self.inc
        if msg.startswith('<-'):
            self.indent -= self.inc
            self.indent = 0 if self.indent < 0 else self.indent
        if self.indent > 0:
            msg = ' ' * self.indent + msg
        self.indent += inc
        return msg


class ColorFormatter(IndentFormatter):
    """Color Formatter"""

    COLORS = {
        "WARNING": (Fore.LIGHTYELLOW_EX, 'W'),
        "ERROR": (Fore.RED + Style.BRIGHT, 'E'),
        "DEBUG": (Fore.CYAN, 'D'),
        "INFO": (Fore.GREEN, 'I'),
        "CRITICAL": (Fore.RED + Style.BRIGHT, 'C')
    }

    def format(self, record):
        """Format the specified record as text"""

        record.msg = self.indent_msg(str(record.msg))
        record.name = ''
        color, lname = self.COLORS.get(record.levelname, ('', ''))
        if color:
            deinit()
            init()  # work-around to avoid to lost the color (Windows-git-bash env)
            if record.levelname != "INFO":
                record.levelname = color + '[' + lname + ']' + Style.RESET_ALL
                record.msg = color + ' ' + record.msg + Style.RESET_ALL
            else:
                record.levelname = ''
        return logging.Formatter.format(self, record)


class DefaultFormatter(IndentFormatter):
    """Default Formatter"""

    def format(self, record):
        """Format the specified record as text"""

        record.msg = self.indent_msg(str(record.msg))
        record.name = ''
        if record.levelname != "INFO":
            record.levelname = '[' + record.levelname[0] + ']'
        else:
            record.levelname = ''
        record.msg = ' ' + record.msg
        return logging.Formatter.format(self, record)


class FileFormatter(IndentFormatter):
    """File Formatter"""

    def format(self, record):
        """Format the specified record as text"""

        record.msg = self.indent_msg(str(record.msg))
        # return logging.Formatter.format(self, record)
        return super(FileFormatter, self).format(record)


class DefaultStrHandler(logging.StreamHandler):
    """Default handler"""

    def __init__(self, stream=None):
        """."""
        stream = sys.stdout if stream is None else stream
        super(DefaultStrHandler, self).__init__(stream)


def get_logger(name=None, level=logging.WARNING, color=False, filename=None):
    """Utility function to create a logger object"""

    logger = logging.getLogger(name)

    if logger.handlers and len(logger.handlers) == 2 and isinstance(logger.handlers[1], DefaultStrHandler):
        # w/ log file
        return logger
    elif logger.handlers and len(logger.handlers) == 1 and isinstance(logger.handlers[0], DefaultStrHandler):
        # wo/ log file
        return logger

    if color:
        init()

    logger.setLevel(logging.NOTSET)

    if filename:
        fh = logging.FileHandler(filename, mode='w', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh_formatter = FileFormatter(format_str="[%(levelname).1s] %(message)s")
        fh_formatter.enable_inc()
        fh.setFormatter(fh_formatter)
        logger.addHandler(fh)

    console = DefaultStrHandler()
    console.setLevel(level)
    if color:
        formatter = ColorFormatter()
    else:
        formatter = DefaultFormatter()
    formatter.enable_inc(filename is None)
    console.setFormatter(formatter)

    logger.addHandler(console)

    return logger


def get_print_fcts(cur_logger: logging.Logger,
                   logger: Optional[Union[str, logging.Logger, Any]] = None,
                   full: bool = False):
    """."""

    if isinstance(logger, str):
        logger_ = logging.getLogger(logger)
        print_fn = logger_.info
        print_deb_fn = cur_logger.debug
    elif logger is None:
        print_fn = cur_logger.info
        print_deb_fn = cur_logger.debug
    elif isinstance(logger, logging.Logger):
        print_fn = logger.info
        print_deb_fn = logger.debug
    elif callable(logger):
        print_fn = logger
        print_deb_fn = None if not full else logger

    if full:
        print_deb_fn = print_fn

    return print_fn, print_deb_fn
