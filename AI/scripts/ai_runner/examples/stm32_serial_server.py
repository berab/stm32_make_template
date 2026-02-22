###################################################################################
#   Copyright (c) 2021 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Example of STM32 server program v0.1

Open a serial COM port and relay the msg to/from the board and the client.
Data exchanged with device and the client are saved in the stm32_serial_log.txt file
"""
import argparse
import signal
import socket
import time as t

from serial import serial_for_url
import serial.tools.list_ports
from serial.serialutil import SerialException
import serial.threaded

# https://realpython.com/python-sockets/
# https://github.com/pyserial/pyserial/blob/master/examples/tcp_serial_redirect.py


HOST = 'localhost'
PORT = 10000

def _open_serial_com(device, baudrate, timeout):
    """Open the serial COM port"""

    print('-> opening the serial COM port: {} {}.'.format(device, baudrate))

    try:
        # hdl = Serial(device, baudrate=baudrate, timeout=timeout)
        # hdl = serial_for_url('spy://' + device + '?file=test.txt&all=True', baudrate)
        hdl = serial_for_url('spy://' + device + '?file=stm32_serial_log.txt', do_not_open=True)
        hdl.baudrate = baudrate
        hdl.timeout = timeout
        hdl.open()
    except SerialException as _e:
        raise IOError('{}'.format(_e))
    return hdl


def _close_serial_com(hdl):
    """Close the serial COM port"""
    print('-> closing the serial COM port')
    if hdl:
        hdl.close()


def ctrlc(sig, frame):
    raise KeyboardInterrupt("CTRL-C!")


class SerialToNet(serial.threaded.Protocol):
    """serial->socket"""

    def __init__(self, debug):
        self.socket = None
        self._debug = debug

    def __call__(self):
        return self

    def data_received(self, data):
        if self._debug:
            print('RX -> host: "{}" {}'.format(bytearray(data).hex(),
                                               len(data)), flush=True)
        if self.socket is not None:
            self.socket.sendall(data)


def relay_loop(ser_hdl, client_socket, debug=False):
    
    ser_to_net = SerialToNet(debug)
    serial_worker = serial.threaded.ReaderThread(ser_hdl, ser_to_net)
    serial_worker.start()

    print('-> starting the relay...', flush=True)
    start_time = t.perf_counter()

    ser_to_net.socket = client_socket

    ser_hdl.reset_input_buffer()
    ser_hdl.reset_output_buffer()

    try:
        with client_socket:
            client_socket.settimeout(0.5)
            while True:
                try:
                    data = client_socket.recv(1024)
                    if data and debug:
                        print('host -> TX: "{}" {}'.format(bytearray(data).hex(),
                                                           len(data)), flush=True)
                    if not data:
                        break
                    else:
                        ser_hdl.write(data)
                except socket.timeout:
                    pass
                except socket.error as msg:
                    print('ERROR: {}'.format(msg))
                    break
    except KeyboardInterrupt:
        raise
    except socket.error as msg:
        print('ERROR: {}'.format(msg))
    finally:
        print('-> closing the relay ({:.03f}s)'.format((t.perf_counter() - start_time)), flush=True)
        serial_worker.stop()


def serial_server(args):
    """."""
    signal.signal(signal.SIGINT, ctrlc)
    signal.signal(signal.SIGTERM, ctrlc)

    ser_hdl = _open_serial_com(args.device, args.baudrate, None)

    # create an INET, STREAMing socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # bind the socket to the port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        timeout=args.timeout
        sock.settimeout(0.1)
        server_address = (HOST, PORT)
        sock.bind(server_address)
        msg = '-> waiting on "{}" port {} ({}s to open a socket)..'.format(server_address[0],
                                                                           server_address[1],
                                                                           timeout)
        print(msg, flush=True)
        sock.listen(1)
        while True:
            try:
                to = 0
                while to < timeout:
                    try:  # listen for incoming connections
                        conn, addr = sock.accept()
                        print('-> connected by', addr, flush=True)
                        relay_loop(ser_hdl, conn, args.debug)
                        print(msg, flush=True)
                        to = 0
                    except socket.timeout:
                        to += 0.1
                if to > timeout:
                    print('-> timeout occurs, server is closed')
                    break         
            except KeyboardInterrupt as exec_:
                print('-> keyboardInterrupt occurs, server is closed: %s' % str(exec_))
                break

    _close_serial_com(ser_hdl)
    ser_hdl = None


if __name__ == "__main__":
    # Get script arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=60, help="timeout to accept a connection")
    parser.add_argument('--device', '-d', type=str, default='COM6', help="serial COM port")
    parser.add_argument('--baudrate', '-b', type=int, default=115200, help="baudrate")
    parser.add_argument('--debug', action='store_true', help="debug")
    args = parser.parse_args()
    serial_server(args)
