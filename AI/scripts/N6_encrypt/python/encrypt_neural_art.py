import argparse
from pb_outputs import message_pb2 as pbproto
import json
import logging
import time
from pathlib import Path
import struct
import threading
from tqdm import tqdm
from typing import Tuple

import log_utils
logger = log_utils.EncryptionLogger.get_logger()

import serial_utils as su

RAW_DATA_MAX_SIZE = 4096
BAUDRATE = 921600 * 2

_UART_TX_OK = threading.Event()  # Event to signal that the UART can transmit data. It is set by the UART RX thread when it has received an ACK
_UART_RX_DONE = threading.Event()  # Help the rx thread to finish gracefully


class CInfoReader:
    def __init__(self, c_info: Path, mem_init: Path):
        if mem_init.suffix != ".raw":
            logger.warning("Expected memory initializer file should be a .raw file... Continuing anyway")
        self.file = c_info
        self.mem_initializer_path = mem_init  # Path to memory initializer file
        self.mem_initializer_base = None  # Base address of the memory initializer contents
        self.data = json.loads(self.file.read_text())
        self.mem_initializer_encryption_offset = None  # Offset of the part of the initializer to be encrypted
        self.mem_initializer_encryption_len = None  # Length of the encrypted part
        self.output_file = None  # Path to the output file
        self.parse_data()

    def parse_data(self):
        """Read the json, extract meaningful info for encryption / raise exceptions if not implemented"""
        for k in self.data["memory_pools"]:
            if (encr := k["attributes"].get("encryption")) is not None:
                addr = k["address"]
                if addr == "":
                    # This memory pool is configured in "relative" mode, use the offset as the base address
                    addr = int(k["offset_start"])
                else:
                    # Standard memory pool (absolute mode): use the address field as base address
                    addr = int(addr)

                self.mem_initializer_base = addr
                if addr >= 0x7000_0000 and (addr + k["used_size_bytes"]) < 0x7800_0000:
                    # This can be handled by the script
                    self.mem_initializer_encryption_offset = 0
                    self.mem_initializer_encryption_len = k["used_size_bytes"]
                    self.mem_initializer_encryption_offset = encr["offset"]
                    self.mem_initializer_encryption_len = encr["size"]
                    self.output_file = Path(self.mem_initializer_path).with_name(self.mem_initializer_path.stem + "_encrypted.raw")
                    # Raise an error if the encrypted part has an address that is not 8bytes aligned (maybe: could be fixed later on) @TODO
                    if (encr_addr:=self.mem_initializer_base + self.mem_initializer_encryption_offset) % 8 != 0:
                        raise ValueError(f"Encrypted part of the memory initializer is not 8 bytes aligned (address = {encr_addr:#X})")
                    # Show warning if the size of the raw file is strange vs what's in the json:
                    if self.mem_initializer_path.stat().st_size != k["used_size_bytes"]:
                        logger.warning(
                            f"Warning: size of the raw file ({self.mem_initializer_path.stat().st_size:,d} bytes) is different "
                            f"from what expected by the json ({self.mem_initializer_encryption_len:,d} bytes). This might result in useless file !"
                        )
                    logger.info(f"Memory pool to encrypt found at address: {self.mem_initializer_base:#10x} -- {self.mem_initializer_encryption_len / 1024:.3f} kBytes to encrypt at offset {self.mem_initializer_encryption_offset}")
                    logger.debug(f"Output file will be {self.output_file}")
                    break
                else:
                    raise NotImplementedError("Memory pool not handled by the script (out of DK-external-Flash range)")

    def get_bytes_to_encrypt(self) -> Tuple[bytes, int]:
        """Returns the bytes to encrypt and the final address where they will be stored """
        if self.mem_initializer_encryption_offset is None:
            raise ValueError("No bytes to encrypt found")
        b = self.mem_initializer_path.read_bytes()
        return b[
            self.mem_initializer_encryption_offset: self.mem_initializer_encryption_offset
            + self.mem_initializer_encryption_len
        ], self.mem_initializer_base + self.mem_initializer_encryption_offset

    def inject_encrypted_bytes(self, b: bytes):
        if self.mem_initializer_encryption_offset is None:
            raise ValueError("No bytes to encrypt found")
        c = bytearray(self.mem_initializer_path.read_bytes())
        c[self.mem_initializer_encryption_offset : self.mem_initializer_encryption_offset + self.mem_initializer_encryption_len] = bytearray(b)
        self.output_file.write_bytes(c)
        logger.info(f"Encrypted data injected into {self.output_file.name}")


class EncryptionProgressBar(tqdm):
    # print only if the logger is in error mode
    def __init__(self, verb: bool = True, **kwargs):
        self.verbose = verb
        bar_format = "{desc}... {percentage:3.0f}%|{bar:80}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
        kwargs["total"] = round(kwargs.get("total", 100) / 1024, ndigits=3)
        super(EncryptionProgressBar, self).__init__(
            **kwargs,
            disable=not self.verbose,
            unit="Kbytes",
            desc="Encrypting...",
            smoothing=0.8,
            bar_format=bar_format,
            leave=False,
        )

    def update(self, n=1):
        if self.verbose:
            super(EncryptionProgressBar, self).update(round(n / 1024, ndigits=3))


def raw_data_worker_tx(s, data: bytes, final_address:int):
    msg = pbproto.MyMessage()
    command = pbproto.RawData()

    splits = [data[i : i + RAW_DATA_MAX_SIZE] for i in range(0, len(data), RAW_DATA_MAX_SIZE)]
    addresses = [final_address + i * RAW_DATA_MAX_SIZE for i in range(len(splits))]

    durations = []
    received_data = bytes()

    pbar = EncryptionProgressBar(
        verb=(log_utils.EncryptionLogger.get_console_level != logging.DEBUG), total=len(data)
    )
    for i, split in enumerate(splits):
        cur_timings = []
        cur_timings.append(round(time.time() * 1000))
        logger.debug(f"{round(time.time() * 1000)} - sending chunk {i + 1} / {len(splits)}")
        command.stat = pbproto.RawData.STATUS_FIRST_CHUNK if i == 0 else pbproto.RawData.STATUS_MIDDLE_CHUNK
        if i == len(splits) - 1:
            command.stat = pbproto.RawData.STATUS_LAST_CHUNK
        command.chunk_no = i
        command.base_address = addresses[i]
        command.data = split
        msg.raw_data.CopyFrom(command)
        output = msg.SerializeToString()
        _UART_TX_OK.clear()
        logger.debug(
            f"WRITE (chunk {i + 1}/{len(splits)} -- address: {addresses[i]:#10X})"
        )
        pbar.update(len(split))
        send_packeted_msg(s, wrap_pb_msg(output))
        _UART_TX_OK.wait()
        cur_timings.append(round(time.time() * 1000))
        durations.append(
            {
                "size_bytes": len(split),
                "size_packets": len(wrap_pb_msg(output)),
                "times": cur_timings[1] - cur_timings[0],
            }
        )
    _UART_RX_DONE.set()
    pbar.close()
    total_size = sum([v["size_bytes"] for v in durations])
    total_time = sum([v["times"] for v in durations])
    total_packet_sizes = sum([v["size_packets"] for v in durations])
    dr = (total_size / total_time) / (1024) * 1000  # B/ms --> kB/s
    logger.debug(
        f"Sent {total_size / 1024:,.3f}kB ({total_packet_sizes / 1024:,.3f}kB over uart - overhead {(total_packet_sizes / total_size - 1) * 100:.3f}%) in {total_time / 1000:.3f} seconds --> DataRate: {dr:.4f} kB/s"
    )


def raw_data_worker_rx(s, result_b: list):
    out_data = bytes()
    while not _UART_RX_DONE.is_set():
        msg_len = int.from_bytes(s.read(4), "little")
        msg = s.read(msg_len)
        parsed = pbproto.MyMessage()
        parsed.ParseFromString(msg)
        payload_type = parsed.WhichOneof("payload")
        payload_data = getattr(parsed, payload_type)
        if payload_type == "raw_data":
            logger.debug(f"DATA received (chunk {payload_data.chunk_no} / addr = {payload_data.base_address:#10X})")
            out_data = out_data + payload_data.data
        if payload_type == "ack":
            logger.debug(f"ACK received")
            _UART_TX_OK.set()
    logger.debug(f"RX thread finished")
    result_b.append(out_data)


def show_parsed(msg):
    parsed = pbproto.MyMessage()
    parsed.ParseFromString(msg)
    print(f"{parsed.status=}")
    payload_type = parsed.WhichOneof("payload")
    payload_data = getattr(parsed, payload_type)
    print(f"{payload_type=} {payload_data=}")


def wrap_pb_msg(m: bytes):
    # Add header to the pb message (4 bytes = length of the pb message)
    l = len(m)
    logger.log(logging.DEBUG - 1, f"Wrapping message of length {l}")
    return bytes(l.to_bytes(4, "little")) + m


def generate_Encryption_params_msg(keys: list[int], nb_rounds: int):
    msg = pbproto.MyMessage()
    msg.status = 10
    command = pbproto.EncryptionParams()
    if len(keys) != 4:
        raise ValueError("Keys must be a list of 4 (32b)integers")
    # Reinterpret values as "signed" integers (otherwise protobuf may complain about values out of range)
    int_keys = [struct.unpack("<i", struct.pack("<I", k))[0] for k in keys]
    command.keys.extend(int_keys)
    command.nb_rounds = nb_rounds
    msg.encryption_params.CopyFrom(command)
    output = msg.SerializeToString()
    logger.debug("Encryption params to send generated")
    return wrap_pb_msg(output)


def send_encryption_params(s, key_LSB: int, key_MSB: int, nb_rounds: int):
    logger.info(f"Sending encryption params: keys = (MSB:{key_MSB:#016x})(LSB:{key_LSB:#016x}) -- nb_rounds = {nb_rounds}")
    keys = [
        key_LSB & 0xFFFF_FFFF,
        (key_LSB >> 32) & 0xFFFF_FFFF,
        key_MSB & 0xFFFF_FFFF,
        (key_MSB >> 32) & 0xFFFF_FFFF,
    ]
    send_packeted_msg(s, generate_Encryption_params_msg(keys, nb_rounds))


def wait_for_ack(s, timeout: int = 10):
    s.timeout = timeout
    msg_len = int.from_bytes(s.read(4), "little")
    msg = s.read(msg_len)
    parsed = pbproto.MyMessage()
    parsed.ParseFromString(msg)
    payload_type = parsed.WhichOneof("payload")
    if payload_type == "ack":
        logger.debug(f"{round(time.time() * 1000)} - ACK received")
        pass
    else:
        raise ValueError(f"Received a strange ack {payload_type}")


def wait_for_raw_data(s, timeout: int = 10):
    s.timeout = timeout
    msg_len = int.from_bytes(s.read(4), "little")
    msg = s.read(msg_len)
    parsed = pbproto.MyMessage()
    parsed.ParseFromString(msg)
    payload_type = parsed.WhichOneof("payload")
    payload_data = getattr(parsed, payload_type)
    if payload_type == "raw_data":
        logger.debug(
            f"Raw data received (chunk_nb = {payload_data.chunk_no} / size= {msg_len}) -- {payload_data.data[:20]}"
        )
        pass
    else:
        raise ValueError(f"Received a strange raw data {payload_type}")
    return payload_data.data


def send_packeted_msg(s, msg: bytes):
    s.write(msg[:4])  # send size
    time.sleep(0.002)  # wait a bit for the other side to be ready
    s.write(msg[4:])  # send the rest of the message


def send_binary_file(s, f: Path):
    b = f.read_bytes()
    out_file = f.with_stem(f.stem + "_out")
    send_binary_data(s, b, out_file)


def send_binary_data(s, b: bytes, out_file: Path = None, final_address: int = 0x7000_0000):
    start_t = round(time.time() * 1000)
    out_b = []  # gather output from the rx thread in a mutable object passed as argument
    tx_th = threading.Thread(target=raw_data_worker_tx, args=(s, b, final_address))
    rx_th = threading.Thread(target=raw_data_worker_rx, args=(s, out_b))
    _UART_TX_OK.set()
    _UART_RX_DONE.clear()
    rx_th.start()
    tx_th.start()
    tx_th.join()
    rx_th.join()
    end_t = round(time.time() * 1000)
    rx_bytes = out_b[0]
    if out_file is not None:
        out_file.write_bytes(rx_bytes)
        logger.info(f"Received encrypted data written to file {out_file}")
    logger.info(f"Data transfer finished -- Took {(end_t - start_t) / 1000:.3f} seconds -- size = {len(b) / 1024:,.3f}kB -- Encryption rate: {len(b) / (end_t - start_t) * 1000 / 1024:.3f}kB/s")
    logger.debug(f"Theoretical max rate = {s.baudrate / 10 / 1024} kB/s")  # baudrate in bits/s + one byte takes ~10 bits to be sent (start/stop bits)

    return rx_bytes


def main_test():
    check_pb = False
    check_uart = False
    check_out = False
    check_json = False
    logger.info("Starting encryption")
    if check_pb is True:
        output = generate_serialized_msg()
        print("-" * 120)
        print(f"{output=}")
        print("-" * 120)
        show_parsed(output)
        print("-" * 120)
    if check_uart is True:
        # s = su.connect("COM21", 921600)
        s = su.autoconnect_STLink(921600 * 2)
        s.reset_input_buffer()
        s.reset_output_buffer()
        # Set encryption params
        send_encryption_params(
            s, key_LSB=0x1C80000007B, key_MSB=0x18AF800000315, nb_rounds=12
        )
        wait_for_ack(s)
        # Send data & receive data
        send_binary_file(s, Path(__file__).parent / "rnd.txt")
        send_binary_file(s, Path(__file__).parent / "rnd_out.txt")
        pass
    if check_out is True:
        b = (Path(__file__).parent / "rnd.txt").read_bytes()
        bb = (Path(__file__).parent / "rnd_out.txt").read_bytes()
        bbb = (Path(__file__).parent / "rnd_out_out.txt").read_bytes()
        diffs = [k == kk for k, kk in zip(b, bbb)]
        diff_bbb = [i for i, x in enumerate(diffs) if x is False]
        logger.info(f"Indices where init != out_out: {diff_bbb}")
        d = [k == kk for k, kk in zip(b, bb)]
        [i for i, x in enumerate(d) if x is True]
    if check_json is True:
        cinfo = CInfoReader(Path("C:/Users/xxx/CODE/stm.ai/st_ai_ws/model2_c_info.json"))
    logger.info("Done")


def main(args):
    """Main thread taking inputs from the CLI"""
    if args.verbose is True:
        log_utils.EncryptionLogger.set_verbosity(logging.DEBUG)
    c_info = args.c_info
    raw_file = args.raw_file
    keys = args.keys
    comport = args.comport
    nb_rounds = args.nbrounds
    logger.info("Parsing c_info file")
    cinfo = CInfoReader(c_info=c_info, mem_init=raw_file)
    if comport == "auto":
        s = su.autoconnect_STLink(BAUDRATE)
    else:
        s = su.connect(comport, BAUDRATE)
    logger.info("Starting encryption")
    # Ensure buffers are clean ...
    s.reset_input_buffer()
    s.reset_output_buffer()

    # Set encryption params
    send_encryption_params(s, key_LSB=keys[1], key_MSB=keys[0], nb_rounds=nb_rounds)
    wait_for_ack(s)
    # Send data
    b, final_addr = cinfo.get_bytes_to_encrypt()
    rcv = send_binary_data(s, b, final_address=final_addr)
    cinfo.inject_encrypted_bytes(rcv)

    logger.info("Done")
    return raw_file, cinfo.output_file, cinfo.mem_initializer_base


class DeprecatedAction(argparse.Action):
    def __init__(self, *args, **kwargs):
        super(DeprecatedAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string):
        logger.warning(f"Option {option_string} is provisionned but no useable for now: it will be available be in a future version")
        if option_string == "--nbrounds":
            logger.warning(f"{option_string}={values} will be ignored, number of rounds is set to 12")
            setattr(namespace, self.dest, 12)


class ConvertToHexListAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string):
        # Convert the input strings to a list of integer values
        hex_values = [int(v, 16) for v in values]
        setattr(namespace, self.dest, hex_values)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the script"""
    parser_ = argparse.ArgumentParser(
        description="Simple python script to encrypt data (To be used with a running encryption firmware connected by an STLink)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity (debug)")
    parser_.add_argument( "-k", "--keys", default=[0xAABBCCDDAABBCCDD, 0xAABBCCDDAABBCCDD], action=ConvertToHexListAction, nargs=2, help="Keys to use (MSB LSB)", )
    parser_.add_argument( "-r", "--nbrounds", default=12, action=DeprecatedAction, help="Number of rounds (ignored for now)", )
    parser_.add_argument( "-p", "--comport", default="auto", help='COM-port name to be used for transmitting data to STLink. auto tries to connect to the first "STLink" found.', )
    parser_.add_argument("c_info", type=lambda x: Path(x), help="json file output of the compilation")
    parser_.add_argument( "raw_file", type=lambda x: Path(x), help="memory-initializer file output of the compilation (.raw)", )
    return parser_


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    main(args)
