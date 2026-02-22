"""
Basic wrapper around pyserial to handle UART connections

- use  select_serial_port() to select a port (manual selection or by providing a serial number as argument)
- get its name (e.g COM1, /dev/ttyUSB0) by using port.name
- connect to the port by using connect(port.name, baudrat

"""

import serial
import serial.tools.list_ports


def show_comports(
    l: list[serial.tools.list_ports_common.ListPortInfo],
) -> None:
    """Pretty-print the list of ports

    Parameters
    ----------
    l : list[serial.tools.list_ports_common.ListPortInfo]
        List of ports
    """
    hdr = f"""{"PORT ID":8s} | {"Port name":20s} | {"Manufacturer":20s} | {"Serial Number":^30s} | {"Description":s}"""
    print(hdr)
    print("-" * len(hdr))
    for i, k in enumerate(l):
        sn = k.serial_number if k.serial_number is not None else "N/A"
        print(
            f"{i:^8d} | {k.name:20s} | {k.manufacturer:20s} | {sn:30s} | {k.description}"
        )


def select_serial_port(sn: str = None) -> str:
    """Enumerate ports, and requests the user to select one of them

    Parameters
    ----------
    sn : str
        Serial number of an peripheral connected to serial ports

    Returns
    -------
    str
        Name of the UART port

    Raises
    ------
    ValueError
        if the chosen port is not in the list
    """
    # enumerate ports and show them
    comports_lst = serial.tools.list_ports.comports()
    output = None
    if sn is None:
        show_comports(comports_lst)
        try:
            user_choice = int(input("Select port ID number: "))
        except ValueError:
            user_choice = -1

        if user_choice < 0 or user_choice > len(comports_lst) - 1:
            raise ValueError("Enter a valid port id (integer value on the left)")
        output = comports_lst[user_choice]
    else:
        # Match S/N with the current list
        filtered_ports = [x for x in comports_lst if x.serial_number == sn]
        if len(filtered_ports) == 0:
            raise ValueError(f"Serial number {sn} not found")
        output = filtered_ports.pop()
    return output

def autoconnect_STLink(baudrate:int=921600*2) -> serial.Serial:
    comports_lst = serial.tools.list_ports.comports()
    stlink_ports = [x for x in comports_lst if  x.description.startswith("STMicroelectronics STLink") and x.manufacturer == "STMicroelectronics"]
    if len(stlink_ports) == 0:
        raise ValueError("STLink not found")
    if len(stlink_ports) > 1:
        raise ValueError("Multiple STLinks found, select one manually")
    return serial.Serial(stlink_ports[0].name, baudrate=baudrate)

def connect(s: str, baudrate: int) -> serial.Serial:
    """Connects to UART by its name

    Parameters
    ----------
    s : str
        Name of the UART port
    baudrate : int
        Baudrate to use

    Returns
    -------
    serial.Serial
        An UART instance, connected.
    """
    ser = serial.Serial(s, baudrate=baudrate)
    return ser


def capture_data(ser: serial.Serial, eof_char: str = "\n") -> str:
    """Capture trace from the UART connection (just a template to show the usage)

    Parameters
    ----------
    eof_char: str
        Character to stop capturing data
    ser : serial.Serial
        UART connection instance
    Returns
    -------
    str
        data, stops capturing when eof_char is found
    """
    output = []
    ser.flushInput()
    ser.flushOutput()
    while True:
        line = ser.readline().decode()
        if eof_char in line:
            break
        output.append(line)
    return "".join(output)


if __name__ == "__main__":
    # Show comport when calling the script
    comports_l = serial.tools.list_ports.comports()
    show_comports(comports_l)

    # Example usage
    # port = select_serial_port()   # Manual selection
    # port = select_serial_port(sn="0035001F3331511934333834")  # Selection by S/N
    # serial_connection = connect(port.name, 115200)            # Connect to the port (use name property of the port)
    # print(capture_data(serial_connection))
    # serial_connection.close()                                 # Close the connection
