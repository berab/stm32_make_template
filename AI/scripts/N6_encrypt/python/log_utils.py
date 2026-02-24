import logging
from pathlib import Path

class EncryptionLogger():
    def __init__(self):
        raise RuntimeError("Use get_logger() to get the logger instance")

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """
        Get the logger for the encrypt_neural_art module
        """
        logger = logging.getLogger("encrypt_logger")
        # Setup the logger if it is not configured already
        if len(logger.handlers) == 0:
            cls._init_logger(logger)
        return logger

    @classmethod
    def set_verbosity(cls, level: int) -> None:
        """
        Set the verbosity level of the logger for the encrypt_neural_art module
        """
        lg = cls.get_logger()
        for handler in lg.handlers:
            # only change verbosity of the stream handlers (insinstance does not seem to work here)
            if handler.stream.name in ["<stdout>", "<stderr>"]:
                handler.setLevel(level)

    @classmethod
    def get_console_level(cls) -> int:
        """
        Get the current console level of the logger for the encrypt_neural_art module
        """
        lg = cls.get_logger()
        for handler in lg.handlers:
            # Get the first streamhandler level
            if isinstance(handler, logging.StreamHandler):
                return handler.level

    @classmethod
    def _init_logger(cls, lg:logging.Logger) -> None:
        """
        Initialize the logger for the encrypt_neural_art module
        """   
        lg.setLevel(logging.DEBUG)
        log_ch = logging.StreamHandler()
        log_ch.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
                fmt="%(asctime)s.%(msecs)03d :: %(filename)s :: %(levelname)-8s :: %(message)s",
                datefmt="%H:%M:%S"
                )
        log_ch.setFormatter(fmt)
        lg.addHandler(log_ch)
        file_handler = logging.FileHandler(Path(__file__).parent / 'encryption.log', mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        lg.addHandler(file_handler)

