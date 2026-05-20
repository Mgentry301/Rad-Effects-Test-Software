"""AD9914 register-read backend for the Setup_GUI recording worker.

Talks to the AD9914 evaluation board via a Total Phase Cheetah SPI Host
Adapter wired to the EVB's external control header ``P101C`` (which is
already 3.3 V on-board level-shifted to the 1.8 V AD9914 pins).

Cheetah pin -> P101C pin (verified from EVB schematic):
    5  MISO  ->  P101C 37  (SDO)
    7  SCLK  ->  P101C 39  (SCLK)
    8  MOSI  ->  P101C 38  (SDIO)
    9  SS1   ->  P101C 40  (CSB)
    2,10 GND ->  any P101A pin
    4,6 NC/+5V -> leave open

EVB jumpers P203/P204/P205 must be set to *Disable* to release the on-board
Cypress SPI master before driving from the Cheetah.

The AD9914 boots in 3-wire SPI mode (SDIO bidirectional, SDO unused). With
the wiring above we use 4-wire mode (separate SDIO input + SDO output), so
``open_register_client`` does a blind write to CFR1 at startup to set the
"SDIO input only" bit before the first read.

Recording-manager hooks (auto-discovered by recording_manager.py):

    open_register_client() -> client
    read_register(client, addr) -> int   # returns 32-bit register value
    close_register_client(client) -> None

Environment overrides
---------------------
    AD9914_CHEETAH_PORT     Cheetah port index            (default 0)
    AD9914_BITRATE_KHZ      SPI clock rate in kHz         (default 1000)
    AD9914_AUTO_4WIRE       "1" to force 4-wire at open   (default "1")
"""

from __future__ import annotations

import os
import sys
import time
from array import array
from typing import List, Optional

try:
    import cheetah_py as ch  # Total Phase Cheetah Python API
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "cheetah_py is required for the AD9914 Cheetah backend. "
        "Install Total Phase software and copy cheetah_py.py + "
        "cheetah.dll (Windows) into this folder or onto PYTHONPATH."
    ) from exc


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_PORT = 0
DEFAULT_BITRATE_KHZ = 1000  # 1 MHz; AD9914 supports up to 70 MHz
SPI_BITS = 8

# AD9914 instruction byte: bit 7 = R/!W, bits 6:0 = register address
READ_BIT = 0x80
ADDR_MASK = 0x7F

# All AD9914 user registers (0x00..0x1B) are 4 bytes wide.
REGISTER_WIDTH = 4

# CFR1 (addr 0x00) bit 1 = "SDIO input only" (enables 4-wire SPI).
CFR1_ADDR = 0x00
CFR1_SDIO_INPUT_ONLY = 0x00000002

# Defensive read settings. The AD9914 EVB share-bus topology occasionally
# returns "link dead" patterns (all 0xFF or all 0x00) when the on-board
# Cypress contests the bus or a wire is intermittent. We retry the read,
# and on systematic failure surface the raw value so the GUI can flag it.
READ_RETRIES = 3
READ_SETTLE_S = 0.001


# ---------------------------------------------------------------------------
# Cheetah SPI client
# ---------------------------------------------------------------------------
class CheetahSpiClient:
    """Thin wrapper around a Cheetah handle for AD9914 SPI access."""

    def __init__(self, port: int = DEFAULT_PORT,
                 bitrate_khz: int = DEFAULT_BITRATE_KHZ):
        self.port = port
        handle = ch.ch_open(port)
        if handle <= 0:
            raise IOError(
                f"Cheetah open failed on port {port}: {ch.ch_status_string(handle)}. "
                "Check USB cable and Total Phase drivers."
            )
        self._h = handle

        # AD9914 datasheet says CPOL=0/CPHA=0, but in case Cheetah's edge
        # interpretation differs, allow mode override via env var.
        mode = int(os.environ.get("AD9914_SPI_MODE", "0"))
        pol = ch.CH_SPI_POL_RISING_FALLING if (mode & 0x2) == 0 else ch.CH_SPI_POL_FALLING_RISING
        phase = ch.CH_SPI_PHASE_SAMPLE_SETUP if (mode & 0x1) == 0 else ch.CH_SPI_PHASE_SETUP_SAMPLE
        ch.ch_spi_configure(
            handle,
            pol,
            phase,
            ch.CH_SPI_BITORDER_MSB,
            0x0,  # SS polarity: active low on SS1
        )
        print(f"[AD9914] SPI mode {mode}  bitrate {bitrate_khz} kHz", file=sys.stderr)
        ch.ch_spi_bitrate(handle, int(bitrate_khz))
        # Brief settle so the EVB sees stable idle levels.
        time.sleep(0.01)

    # -- low level ---------------------------------------------------------
    def _transact(self, tx: bytes) -> bytes:
        """Clock ``tx`` out with SS asserted; return MISO bytes captured."""
        h = self._h
        ch.ch_spi_queue_clear(h)
        ch.ch_spi_queue_oe(h, 1)
        ch.ch_spi_queue_ss(h, 0x01)  # assert SS1
        ch.ch_spi_queue_array(h, array('B', tx))
        ch.ch_spi_queue_ss(h, 0x00)  # deassert
        count, rx = ch.ch_spi_batch_shift(h, len(tx))
        if count != len(tx):
            raise IOError(
                f"Cheetah SPI shift returned {count} bytes, expected {len(tx)}"
            )
        return bytes(bytearray(rx))

    # -- public API --------------------------------------------------------
    def write_register(self, addr: int, value: int,
                       width: int = REGISTER_WIDTH) -> None:
        """Write ``value`` (MSB first, ``width`` bytes) to ``addr``."""
        instr = (addr & ADDR_MASK) & ~READ_BIT
        payload = bytes((value >> (8 * (width - 1 - i))) & 0xFF
                        for i in range(width))
        self._transact(bytes([instr]) + payload)

    def read_register(self, addr: int,
                      width: int = REGISTER_WIDTH) -> int:
        """Read ``width`` bytes from ``addr`` and return as unsigned int.

        Retries up to ``READ_RETRIES`` times on the "all-0xFF" / "all-0x00"
        link-dead patterns so that an intermittent connection still yields
        useful samples when the line briefly comes back.
        """
        instr = READ_BIT | (addr & ADDR_MASK)
        dead_all_ff = (1 << (8 * width)) - 1  # 0xFFFFFFFF for width=4
        last_val = 0
        for attempt in range(READ_RETRIES):
            rx = self._transact(bytes([instr]) + bytes(width))
            data = rx[1:]  # first byte shifted out while we drove instr
            val = 0
            for b in data:
                val = (val << 8) | (b & 0xFF)
            last_val = val
            if val != dead_all_ff and val != 0:
                return val
            time.sleep(READ_SETTLE_S)
        return last_val

    def write_register_verified(self, addr: int, value: int,
                                width: int = REGISTER_WIDTH,
                                attempts: int = 3) -> bool:
        """Write then read back; retry up to ``attempts`` if mismatch.

        Returns True on verified success. Some AD9914 registers are
        write-only or have reserved bits that read differently from what
        was written; callers that don't care about verification should use
        :meth:`write_register` instead.
        """
        mask = (1 << (8 * width)) - 1
        target = value & mask
        for _ in range(attempts):
            self.write_register(addr, value, width=width)
            time.sleep(READ_SETTLE_S)
            got = self.read_register(addr, width=width) & mask
            if got == target:
                return True
        return False

    def close(self) -> None:
        try:
            ch.ch_close(self._h)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    try:
        return int(raw, 0)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def _enable_4wire(client: CheetahSpiClient,
                  max_attempts: int = 100) -> bool:
    """Write CFR1 with SDIO-input-only set, then verify it took.

    The AD9914 boots in 3-wire mode (SDIO bidirectional, SDO idle). Until
    bit 1 of CFR1 is set, MISO reads are unreliable on a freshly-powered
    EVB. Bench experience shows the chip's SPI input often takes 10-20
    transactions to start latching writes correctly after cold boot
    (likely receiver/PLL settling). Once locked it stays locked across
    Cheetah open/close cycles until power-cycle.

    Strategy: write CFR1, read it back, loop until the read matches the
    expected value or we exceed ``max_attempts``. Logs the lock-in count
    to stderr so operators can see how flaky a given board is today.

    Returns True if 4-wire mode was verified, False otherwise. Callers
    that want hard-failure semantics should check the return value.
    """
    target = CFR1_SDIO_INPUT_ONLY
    for attempt in range(1, max_attempts + 1):
        client.write_register(CFR1_ADDR, target, width=REGISTER_WIDTH)
        time.sleep(0.005)
        try:
            got = client.read_register(CFR1_ADDR, width=REGISTER_WIDTH)
        except Exception:
            continue
        # Only the low byte of CFR1 contains SDIO_INPUT_ONLY; other bits
        # may be set by the chip's reset defaults, so mask to bit 1.
        if got != 0xFFFFFFFF and got != 0 and (got & target) == target:
            print(f"[AD9914] 4-wire locked after {attempt} attempt(s) "
                  f"(CFR1=0x{got:08X})", file=sys.stderr)
            return True
    print(f"[AD9914] 4-wire NOT verified after {max_attempts} attempts; "
          "register reads may be unreliable.", file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# Recording-manager hooks
# ---------------------------------------------------------------------------
def open_register_client() -> CheetahSpiClient:
    """Open the Cheetah and put the AD9914 into 4-wire SPI mode."""
    port = _env_int('AD9914_CHEETAH_PORT', DEFAULT_PORT)
    bitrate = _env_int('AD9914_BITRATE_KHZ', DEFAULT_BITRATE_KHZ)
    client = CheetahSpiClient(port=port, bitrate_khz=bitrate)
    if _env_bool('AD9914_AUTO_4WIRE', True):
        try:
            _enable_4wire(client)
        except Exception:
            client.close()
            raise
    return client


def read_register(client: CheetahSpiClient, addr: int) -> int:
    """Read one AD9914 register (4 bytes) at ``addr``."""
    return client.read_register(int(addr) & ADDR_MASK, width=REGISTER_WIDTH)


def close_register_client(client: CheetahSpiClient) -> None:
    client.close()


# ---------------------------------------------------------------------------
# Stand-alone CLI for bench validation
# ---------------------------------------------------------------------------
_REG_NAMES = {
    0x00: 'CFR1', 0x01: 'CFR2', 0x02: 'CFR3', 0x03: 'CFR4',
    0x04: 'Linear Sweep Parameter Word 0',
    0x05: 'Linear Sweep Parameter Word 1',
    0x06: 'Rising Delta Sweep Parameter Word',
    0x07: 'Falling Delta Sweep Parameter Word',
    0x08: 'Linear Sweep Ramp Rate',
    0x09: 'Frequency Skip Register 1',
    0x0A: 'Frequency Skip Register 2',
    0x0B: 'Profile 0 FTW', 0x0C: 'Profile 0 Ph/Amp',
    0x0D: 'Profile 1 FTW', 0x0E: 'Profile 1 Ph/Amp',
    0x0F: 'Profile 2 FTW', 0x10: 'Profile 2 Ph/Amp',
    0x11: 'Profile 3 FTW', 0x12: 'Profile 3 Ph/Amp',
    0x13: 'Profile 4 FTW', 0x14: 'Profile 4 Ph/Amp',
    0x15: 'Profile 5 FTW', 0x16: 'Profile 5 Ph/Amp',
    0x17: 'Profile 6 FTW', 0x18: 'Profile 6 Ph/Amp',
    0x19: 'Profile 7 FTW', 0x1A: 'Profile 7 Ph/Amp',
    0x1B: 'USR 0',
}


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description='Dump AD9914 registers via Cheetah SPI.')
    parser.add_argument('--port', type=int, default=None,
                        help='Cheetah port index (default: env or 0).')
    parser.add_argument('--bitrate', type=int, default=None,
                        help='SPI bitrate in kHz (default: env or 1000).')
    parser.add_argument('--no-4wire', action='store_true',
                        help='Skip the CFR1 4-wire enable write.')
    parser.add_argument('--addrs', nargs='*', type=lambda x: int(x, 0),
                        help='Specific register addresses to read (default: all 0x00..0x1B).')
    args = parser.parse_args(argv)

    if args.port is not None:
        os.environ['AD9914_CHEETAH_PORT'] = str(args.port)
    if args.bitrate is not None:
        os.environ['AD9914_BITRATE_KHZ'] = str(args.bitrate)
    if args.no_4wire:
        os.environ['AD9914_AUTO_4WIRE'] = '0'

    addrs = args.addrs if args.addrs else list(range(0x00, 0x1C))

    client = open_register_client()
    try:
        print(f'{"Addr":>5} {"Hex":>10}  Name')
        print('-' * 60)
        for a in addrs:
            try:
                v = read_register(client, a)
                print(f'  0x{a:02X} 0x{v:08X}  {_REG_NAMES.get(a, "")}')
            except Exception as exc:
                print(f'  0x{a:02X} ERR        {exc}')
    finally:
        close_register_client(client)
    return 0


if __name__ == '__main__':
    sys.exit(main())
