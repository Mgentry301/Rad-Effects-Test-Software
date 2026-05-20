"""
ADP5055 PMBus Programming Logic — Linduino (Arduino) backend
============================================================

The ADP5055 has no ACE plugin. Instead of using the ADI USB-SDP-CABLEZ
(which is gated by a license key inside ``sdpApi1.dll``), we drive the
chip's PMBus I2C interface from a Linduino (Arduino Uno-compatible)
running the bridge sketch in
``Linduino/adp5055_bridge/adp5055_bridge.ino``.

Wiring (Linduino → ADP5055-EVALZ):
    A4 (SDA)  ->  ADP5055 SDA test point
    A5 (SCL)  ->  ADP5055 SCL test point
    GND       ->  ADP5055 GND
    (Do NOT connect VCC.)

This module exposes the callables the Setup_GUI recording manager
auto-discovers in place of the ACE client::

    open_register_client()                 # opens the serial port to Linduino
    read_register(client, addr) -> int     # returns PMBus byte register

Environment overrides
---------------------
    ADP5055_LINDUINO_PORT   COM port, e.g. ``COM7``      (default: auto-detect)
    ADP5055_I2C_ADDR        7-bit slave address          (default 0x70)
    ADP5055_SERIAL_BAUD     baud rate                    (default 115200)
"""

from __future__ import annotations

import csv
import datetime
import os
import sys
import time
from typing import List, Optional

try:
    import serial  # pyserial
    from serial.tools import list_ports
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pyserial is required for the ADP5055 Linduino backend. "
        "Install with: pip install pyserial"
    ) from exc

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_I2C_ADDR = 0x70
DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 1.0
HANDSHAKE = b'ADP5055-LINDUINO'

# Register map: (addr, name) — keep in sync with ADP5055.json register_read_array.
_REG_NAMES = [
    (0x19, 'CAPABILITY'),
    (0x7E, 'STATUS_CML'),
    (0xD0, 'MODEL_ID'),
    (0xD1, 'CTRL123'),
    (0xD2, 'VID_GO'),
    (0xD3, 'CTRL_MODE1'),
    (0xD4, 'CTRL_MODE2'),
    (0xD5, 'DLY1'),
    (0xD6, 'DLY2'),
    (0xD7, 'DLY3'),
    (0xD8, 'VID1'),
    (0xD9, 'VID2'),
    (0xDA, 'VID3'),
    (0xDB, 'DVS_CFG'),
    (0xDC, 'DVS_LIM1'),
    (0xDD, 'DVS_LIM2'),
    (0xDE, 'DVS_LIM3'),
    (0xDF, 'FT_CFG'),
    (0xE0, 'PG_CFG'),
    (0xE1, 'PG_READ'),
    (0xE2, 'STATUS_LCH'),
]


# ---------------------------------------------------------------------------
# Linduino serial client
# ---------------------------------------------------------------------------
class LinduinoI2cClient:
    """Thin wrapper around a serial connection to the ADP5055 bridge sketch."""

    def __init__(self, port: str, baud: int = DEFAULT_BAUD,
                 timeout: float = DEFAULT_TIMEOUT, addr: int = DEFAULT_I2C_ADDR):
        self.port_name = port
        self._ser = serial.Serial(port, baudrate=baud, timeout=timeout)
        # Arduino auto-resets when the port is opened; allow it to boot.
        time.sleep(2.0)
        self._ser.reset_input_buffer()
        self._send('P')
        banner = self._readline()
        if HANDSHAKE not in banner.encode('ascii', errors='ignore'):
            self.close()
            raise IOError(
                f"Linduino on {port} returned unexpected banner: {banner!r}. "
                "Is the adp5055_bridge sketch loaded?"
            )
        self.set_address(addr)

    # -- low-level ---------------------------------------------------------
    def _send(self, line: str) -> None:
        self._ser.write((line + '\n').encode('ascii'))
        self._ser.flush()

    def _readline(self) -> str:
        raw = self._ser.readline()
        if not raw:
            raise IOError(f"Linduino on {self.port_name} timed out")
        return raw.decode('ascii', errors='replace').strip()

    def _command(self, line: str) -> str:
        self._send(line)
        return self._readline()

    # -- public ------------------------------------------------------------
    def set_address(self, addr: int) -> None:
        resp = self._command(f'A {addr:02X}')
        if resp != 'OK':
            raise IOError(f"Linduino refused address 0x{addr:02X}: {resp}")
        self.addr = addr & 0x7F

    def read_byte(self, cmd: int) -> int:
        resp = self._command(f'R {cmd:02X}')
        if resp.startswith('ERR'):
            raise IOError(f"PMBus read 0x{cmd:02X} failed: {resp}")
        try:
            return int(resp, 16) & 0xFF
        except ValueError as exc:
            raise IOError(f"Bad response to R 0x{cmd:02X}: {resp!r}") from exc

    def write_byte(self, cmd: int, val: int) -> None:
        resp = self._command(f'W {cmd:02X} {val & 0xFF:02X}')
        if resp != 'OK':
            raise IOError(f"PMBus write 0x{cmd:02X}=0x{val:02X} failed: {resp}")

    def scan(self) -> List[int]:
        resp = self._command('S')
        return [int(tok, 16) for tok in resp.split() if tok]

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Port discovery
# ---------------------------------------------------------------------------
# Linduino is a Cypress-CY7C-based Uno clone; vanilla Linduino DC2026
# uses an FTDI FT232R. Match VID/PIDs of common Arduino-like adapters.
_LINDUINO_VID_PIDS = [
    (0x0403, 0x6001),  # FTDI FT232R (DC2026 Linduino)
    (0x0403, 0x6015),  # FTDI FT231X
    (0x2341, None),    # Arduino LLC (any PID)
    (0x2A03, None),    # Arduino SRL  (any PID)
    (0x1A86, 0x7523),  # CH340 clones
    (0x10C4, 0xEA60),  # SiLabs CP210x
]


def _auto_detect_port() -> Optional[str]:
    forced = os.environ.get('ADP5055_LINDUINO_PORT', '').strip()
    if forced:
        return forced
    ports = list(list_ports.comports())
    # Prefer VID/PID matches.
    for p in ports:
        vid = getattr(p, 'vid', None) or 0
        pid = getattr(p, 'pid', None) or 0
        for v, expected_pid in _LINDUINO_VID_PIDS:
            if vid == v and (expected_pid is None or pid == expected_pid):
                return p.device
    # Fallback: first port whose description hints at Arduino/USB-Serial.
    for p in ports:
        desc = (p.description or '').lower()
        if any(k in desc for k in ('arduino', 'linduino', 'usb serial', 'ch340', 'cp210', 'ft232')):
            return p.device
    return None


def _resolve_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    try:
        return int(raw, 0)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Recording-manager hooks (auto-discovered by recording_manager.py)
# ---------------------------------------------------------------------------
def open_register_client() -> LinduinoI2cClient:
    """Open the Linduino serial bridge. Raises IOError on failure."""
    port = _auto_detect_port()
    if not port:
        raise IOError(
            "No Linduino COM port detected. Plug in the Linduino USB cable, "
            "or set the ADP5055_LINDUINO_PORT environment variable."
        )
    addr = _resolve_int_env('ADP5055_I2C_ADDR', DEFAULT_I2C_ADDR)
    baud = _resolve_int_env('ADP5055_SERIAL_BAUD', DEFAULT_BAUD)
    client = LinduinoI2cClient(port, baud=baud, addr=addr)
    return client


def read_register(client: LinduinoI2cClient, addr: int) -> int:
    """Read one PMBus byte register at ``addr``."""
    return client.read_byte(int(addr) & 0xFF)


def close_register_client(client: LinduinoI2cClient) -> None:
    client.close()


# ---------------------------------------------------------------------------
# Stand-alone CLI for bench validation
# ---------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Read ADP5055 PMBus registers via Linduino.')
    parser.add_argument('--port', help='Force a specific COM port (overrides auto-detect).')
    parser.add_argument('--addr', type=lambda x: int(x, 0), default=DEFAULT_I2C_ADDR,
                        help='I2C slave address (default 0x70).')
    parser.add_argument('--out', help='Optional CSV output path.')
    parser.add_argument('--scan', action='store_true', help='Just scan the I2C bus and exit.')
    args = parser.parse_args(argv)

    if args.port:
        os.environ['ADP5055_LINDUINO_PORT'] = args.port
    os.environ['ADP5055_I2C_ADDR'] = f'0x{args.addr:02X}'

    client = open_register_client()
    try:
        print(f"Connected to Linduino on {client.port_name}, I2C addr 0x{client.addr:02X}")
        if args.scan:
            responders = client.scan()
            if not responders:
                print("No I2C devices responded.")
            else:
                print("I2C responders: " + ' '.join(f'0x{a:02X}' for a in responders))
            return 0

        rows = []
        for cmd, name in _REG_NAMES:
            try:
                val = client.read_byte(cmd)
                print(f"  0x{cmd:02X} {name:<11} = 0x{val:02X}")
                rows.append((f"0x{cmd:02X}", name, f"0x{val:02X}"))
            except IOError as e:
                print(f"  0x{cmd:02X} {name:<11} = ERR ({e})")
                rows.append((f"0x{cmd:02X}", name, 'ERR'))

        if args.out:
            with open(args.out, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['address', 'name', 'value'])
                w.writerows(rows)
            print(f"Wrote {args.out}")
        return 0
    finally:
        client.close()


if __name__ == '__main__':
    sys.exit(main())
