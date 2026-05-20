"""AD9914 register-read backend via Linduino DC2026 over USB-serial.

This is the Setup_GUI recording-manager backend that talks to an Arduino
sketch (AD9914_Linduino/AD9914_Linduino.ino) over a USB-serial COM port.
The sketch handles SPI plus the MASTER_RESET / EXT_PWR_DWN / IO_UPDATE
GPIOs, so we get a clean firmware-driven boot sequence on every open
instead of having to pull jumpers/wires by hand.

Wiring (Linduino DC2026 -> AD9914 EVB P101C, 3.3 V buffered side):
    D13 SCK   ->  P101C 39  (SCLK)
    D11 MOSI  ->  P101C 38  (SDIO)
    D12 MISO  <-  P101C 37  (SDO)
    D10 CS    ->  P101C 40  (CSB)
    D7        ->  MASTER_RESET (P102 pin 3)
    D8        ->  EXT_PWR_DWN  (P102 pin 1)
    D9        ->  IO_UPDATE    (locate on EVB)
    D6        ->  SYNC_IO      (resets SPI engine; preserves regs)
    GND       ->  EVB GND

Linduino JP3 = 3.3 V. EVB P203/P204/P205 = Disable; P202 = Enable;
IOCFG = 1000.

Serial protocol is line-based ASCII at 115200 baud:
    "ID"           -> "AD9914-LINDUINO v1"
    "INIT"         -> firmware drives full boot, returns "OK"/"ERR ..."
    "RESET"        -> pulse MASTER_RESET
    "IOU"          -> pulse IO_UPDATE
    "SYNCIO"       -> pulse SYNC_IO (reset SPI engine, preserve regs)
    "PWRDN 0|1"    -> set EXT_PWR_DWN
    "W AA DDDDDDDD"-> write 32-bit hex value to addr AA
    "R AA"         -> read 32-bit value at addr AA, returns hex

Recording-manager hooks (auto-discovered by recording_manager.py):
    open_register_client()                  -> LinduinoClient
    read_register(client, addr) -> int      -> 32-bit register value
    close_register_client(client) -> None

Environment overrides:
    AD9914_LINDUINO_PORT     serial COM port  (default COM4)
    AD9914_LINDUINO_BAUD     serial baud rate (default 115200)
    AD9914_LINDUINO_NOINIT   "1" skips the INIT command (default sends it)
    AD9914_LINDUINO_BOOT_S   seconds to wait for Arduino auto-reset to
                             finish before talking to the sketch (default 2)
"""

from __future__ import annotations

import os
import sys
import time
from typing import List, Optional

try:
    import serial  # pyserial
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pyserial is required for the AD9914 Linduino backend. "
        "Install with: pip install pyserial"
    ) from exc


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_PORT = "COM6"
DEFAULT_BAUD = 115200
DEFAULT_BOOT_DELAY_S = 2.0
ADDR_MASK = 0x7F
REGISTER_WIDTH = 4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _env_str(name: str, default: str) -> str:
    v = os.environ.get(name, "").strip()
    return v if v else default


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name, "").strip()
    if not v:
        return default
    try:
        return int(v, 0)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name, "").strip()
    if not v:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Serial client
# ---------------------------------------------------------------------------
class LinduinoClient:
    """Thin pyserial wrapper that speaks the AD9914_Linduino sketch protocol."""

    def __init__(self,
                 port: Optional[str] = None,
                 baud: Optional[int] = None,
                 init: bool = True,
                 boot_delay_s: Optional[float] = None,
                 timeout: float = 2.0,
                 suppress_arduino_reset: bool = False):
        port = port or _env_str("AD9914_LINDUINO_PORT", DEFAULT_PORT)
        baud = baud or _env_int("AD9914_LINDUINO_BAUD", DEFAULT_BAUD)
        if boot_delay_s is None:
            boot_delay_s = _env_float("AD9914_LINDUINO_BOOT_S",
                                      DEFAULT_BOOT_DELAY_S)

        if suppress_arduino_reset:
            # Open without toggling DTR so the Linduino keeps running its
            # current sketch state. Critical for the recording path: an
            # Arduino reboot puts D7 (MASTER_RESET) into high-Z, which can
            # float high and wipe the AD9914 configuration we just
            # programmed.
            self._ser = serial.Serial()
            self._ser.port = port
            self._ser.baudrate = baud
            self._ser.timeout = timeout
            try:
                self._ser.dtr = False
                self._ser.rts = False
            except Exception:
                pass
            self._ser.open()
            # No bootloader delay needed -- sketch is already running.
            time.sleep(0.05)
        else:
            self._ser = serial.Serial(port, baud, timeout=timeout)
            # Arduino Unos auto-reset when the serial port is opened; the
            # bootloader takes ~1.5 s before the sketch starts running.
            time.sleep(boot_delay_s)
        try:
            self._ser.reset_input_buffer()
        except Exception:
            pass

        ident = self._cmd("ID", timeout=2.0)
        if not ident.startswith("AD9914-LINDUINO") and suppress_arduino_reset:
            # The Linduino may have reset anyway (some Windows USB-serial
            # drivers pulse DTR briefly before our dtr=False takes hold).
            # Wait the full bootloader delay and try again before giving
            # up.
            print(f"[AD9914] First ID returned {ident!r}; waiting for "
                  f"bootloader and retrying.", file=sys.stderr)
            time.sleep(boot_delay_s)
            try:
                self._ser.reset_input_buffer()
            except Exception:
                pass
            ident = self._cmd("ID", timeout=2.0)
        if not ident.startswith("AD9914-LINDUINO"):
            self.close()
            raise IOError(
                f"Unexpected identifier from {port}: {ident!r}. "
                "Is the AD9914_Linduino sketch loaded?"
            )
        print(f"[AD9914] Linduino {port} @ {baud} : {ident}", file=sys.stderr)

        if init:
            resp = self._cmd("INIT", timeout=3.0)
            if resp != "OK":
                # Don't raise -- caller may still want to use the client to
                # debug. Just log loudly so the operator sees it.
                print(f"[AD9914] INIT response: {resp}", file=sys.stderr)
            else:
                print("[AD9914] Linduino INIT OK (4-wire verified).",
                      file=sys.stderr)

    # -- low level ---------------------------------------------------------
    def _cmd(self, line: str, timeout: Optional[float] = None) -> str:
        """Send one command line and return the single-line response."""
        if timeout is not None:
            self._ser.timeout = timeout
        payload = (line + "\n").encode("ascii")
        self._ser.write(payload)
        self._ser.flush()
        resp = self._ser.readline().decode("ascii", errors="replace").strip()
        return resp

    # -- public API --------------------------------------------------------
    def write_register(self, addr: int, value: int,
                       width: int = REGISTER_WIDTH) -> None:
        addr &= ADDR_MASK
        value &= 0xFFFFFFFF
        resp = self._cmd(f"W {addr:02X} {value:08X}")
        if resp != "OK":
            raise IOError(f"write 0x{addr:02X} failed: {resp}")

    def read_register(self, addr: int,
                      width: int = REGISTER_WIDTH) -> int:
        addr &= ADDR_MASK
        resp = self._cmd(f"R {addr:02X}")
        if resp.startswith("ERR") or not resp:
            raise IOError(f"read 0x{addr:02X} failed: {resp!r}")
        try:
            return int(resp, 16)
        except ValueError as exc:
            raise IOError(
                f"read 0x{addr:02X}: unexpected response {resp!r}"
            ) from exc

    def master_reset(self) -> None:
        resp = self._cmd("RESET", timeout=2.0)
        if resp != "OK":
            raise IOError(f"RESET failed: {resp}")

    def io_update(self) -> None:
        resp = self._cmd("IOU")
        if resp != "OK":
            raise IOError(f"IOU failed: {resp}")

    def sync_io(self) -> None:
        """Pulse SYNC_IO to reset the AD9914 SPI engine.

        Resets the serial port state machine without clearing register
        contents. Use this if a transaction returns garbage to recover
        the SPI link without losing the chip's current configuration.
        """
        resp = self._cmd("SYNCIO")
        if resp != "OK":
            raise IOError(f"SYNCIO failed: {resp}")

    def set_pwrdn(self, on: bool) -> None:
        resp = self._cmd(f"PWRDN {1 if on else 0}")
        if resp != "OK":
            raise IOError(f"PWRDN failed: {resp}")

    def set_bitrate_hz(self, hz: int) -> None:
        resp = self._cmd(f"BITRATE {int(hz)}")
        if resp != "OK":
            raise IOError(f"BITRATE failed: {resp}")

    def reinit(self) -> bool:
        """Run the full firmware INIT sequence again. Returns True on OK."""
        resp = self._cmd("INIT", timeout=3.0)
        return resp == "OK"

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Recording-manager hooks
# ---------------------------------------------------------------------------
# Module-level cached client: programming opens it (with INIT) and we
# keep it open so the recording path can reuse the same serial
# connection. This avoids close/reopen cycles, which on some Windows
# USB-serial drivers briefly pulse DTR -> Linduino reboot -> D7
# (MASTER_RESET) tristates -> AD9914 master-resets and tone dies.
_CACHED_CLIENT: Optional["LinduinoClient"] = None


def _client_alive(c: Optional["LinduinoClient"]) -> bool:
    if c is None:
        return False
    try:
        return bool(c._ser and c._ser.is_open)
    except Exception:
        return False


def open_register_client() -> "LinduinoClient":
    """Return a Linduino client for the recording (register-read) path.

    If a cached client from execute_macro() is still open, reuse it --
    this is the path that keeps the AD9914 alive across the
    programming->recording handoff. Otherwise open a fresh connection
    with DTR held low (suppress_arduino_reset=True) to minimise the
    chance of an auto-reset.

    INIT is skipped by default because INIT pulses MASTER_RESET on the
    AD9914 and would wipe a tone that was just programmed. Set env var
    AD9914_LINDUINO_INIT=1 to opt back into INIT here for a fresh
    bring-up.
    """
    global _CACHED_CLIENT
    if _client_alive(_CACHED_CLIENT):
        print("[AD9914] open_register_client: reusing cached client.",
              file=sys.stderr)
        return _CACHED_CLIENT  # type: ignore[return-value]

    do_init = _env_bool("AD9914_LINDUINO_INIT", False)
    _CACHED_CLIENT = LinduinoClient(init=do_init,
                                    suppress_arduino_reset=True)
    return _CACHED_CLIENT


def read_register(client: LinduinoClient, addr: int) -> int:
    return client.read_register(int(addr) & ADDR_MASK, width=REGISTER_WIDTH)


def close_register_client(client: LinduinoClient) -> None:
    """Close the recording client.

    No-op if the client is the module-level cached one -- we keep that
    open so a subsequent recording session (or another programming
    pass) can reuse it without forcing an Arduino reboot.
    """
    global _CACHED_CLIENT
    if client is _CACHED_CLIENT:
        return
    client.close()


# ---------------------------------------------------------------------------
# Setup_GUI "Configure Part" entry point
# ---------------------------------------------------------------------------
# This backend talks to the chip via Linduino over USB-serial, not via ACE.
# The Setup_GUI's programming_manager checks for SKIP_ACE before opening
# the ACE COM client, so setting this flag lets us run without ACE.
SKIP_ACE = True

# Edit these to change what the GUI's "Program Device / Configure Part"
# button programs. The GUI always passes an ACE client first; we ignore
# it and open our own Linduino serial connection.

EXECUTE_MACRO_FREQ_HZ    = 100e6
# When PLL_BYPASS is True, the AD9914's on-chip PLL is disabled and
# SYSCLK = REF_CLK directly. This is the most deterministic mode --
# Bench-verified 2026-05-20: with PLL enabled, the chip's VCO landed in
# different ranges between resets (SYSCLK=2.6 GHz vs 5.25 GHz from the
# same CFR3 write), giving a non-deterministic output frequency. Driving
# REF_CLK directly avoids all PLL VCO calibration ambiguity at the cost
# of needing a higher-frequency Hittite source.
#
# When PLL_BYPASS=True:
#   - Set Hittite (REF_CLK input at J104) to EXECUTE_MACRO_REF_CLK_HZ.
#   - SYSCLK = EXECUTE_MACRO_REF_CLK_HZ. Use 1-3 GHz for clean output.
#   - PLL_N and CFR3 are ignored.
# When PLL_BYPASS=False (legacy):
#   - SYSCLK = REF_CLK * PLL_N via on-chip PLL (bistable, see above).
EXECUTE_MACRO_PLL_BYPASS = True
EXECUTE_MACRO_REF_CLK_HZ = 2.0e9   # Hittite output in PLL-bypass mode
EXECUTE_MACRO_PLL_N      = 1
EXECUTE_MACRO_CFR3       = None    # None -> auto from PLL_N (PLL mode only)
# Empirical override: if set, FTW math uses this as the actual SYSCLK
# regardless of mode. Use this when the measured tone doesn't match the
# expected REF*N -- e.g. CFR3=0 doesn't fully bypass and the chip is
# running 3.4 GHz instead of 2 GHz: set to 3.4e9 here.
EXECUTE_MACRO_SYSCLK_HZ  = 3.4e9

def execute_macro(client) -> None:
    """GUI hook: program the AD9914 for a single tone.

    ``client`` is the ACE COM client supplied by the Setup_GUI; this
    backend doesn't use ACE so the argument is ignored. We open our own
    Linduino serial connection for the duration of the macro.

    Customize the EXECUTE_MACRO_* constants at the top of this module
    to change the programmed frequency / clock plan.
    """
    # In PLL bypass mode SYSCLK = REF_CLK directly; force PLL_N=1 and
    # tell program_tone to skip CFR3 PLL config (CFR3 = 0 disables PLL).
    eff_ref = EXECUTE_MACRO_REF_CLK_HZ
    eff_n   = EXECUTE_MACRO_PLL_N
    eff_cfr3 = EXECUTE_MACRO_CFR3
    if EXECUTE_MACRO_PLL_BYPASS:
        eff_n = 1
        eff_cfr3 = 0x00000000  # PLL disabled, REF_CLK passes through to SYSCLK
    elif EXECUTE_MACRO_SYSCLK_HZ is not None:
        # Back-solve an effective ref_clk for FTW math while leaving CFR3
        # alone (used when chip's actual PLL multiplier doesn't match).
        eff_ref = float(EXECUTE_MACRO_SYSCLK_HZ) / float(EXECUTE_MACRO_PLL_N)

    # Empirical SYSCLK override (works in any mode): if set, force the
    # FTW math to use this as the real SYSCLK. Lets you trim out an
    # unexpected on-chip multiplier without touching CFR3.
    if EXECUTE_MACRO_SYSCLK_HZ is not None:
        eff_ref = float(EXECUTE_MACRO_SYSCLK_HZ) / float(eff_n)

    sysclk = eff_ref * eff_n
    mode = 'PLL bypass' if EXECUTE_MACRO_PLL_BYPASS else 'PLL ON'
    print(f"AD9914_Linduino.execute_macro: target tone "
          f"{EXECUTE_MACRO_FREQ_HZ/1e6:.6f} MHz "
          f"({mode}, REF_CLK={eff_ref/1e6:.3f} MHz, "
          f"SYSCLK={sysclk/1e9:.3f} GHz)")
    if EXECUTE_MACRO_PLL_BYPASS:
        print(f"  >> Confirm Hittite REF_CLK is set to "
              f"{eff_ref/1e6:.3f} MHz at the J104 input.")
    # Open with INIT=True so the firmware does master_reset + 4-wire
    # SPI setup before we start writing registers, and CACHE the client
    # so the subsequent recording path reuses the same serial
    # connection. Closing+reopening the port can pulse DTR -> Arduino
    # reboot -> AD9914 master-reset -> tone dies.
    global _CACHED_CLIENT
    if _client_alive(_CACHED_CLIENT):
        try:
            _CACHED_CLIENT.close()  # type: ignore[union-attr]
        except Exception:
            pass
        _CACHED_CLIENT = None
    lin = LinduinoClient(init=True)
    _CACHED_CLIENT = lin
    try:
        program_tone(
            lin,
            freq_hz=EXECUTE_MACRO_FREQ_HZ,
            ref_clk_hz=eff_ref,
            pll_n=eff_n,
            cfr3=eff_cfr3,
        )
        print(f"AD9914 programmed: {EXECUTE_MACRO_FREQ_HZ/1e6:.6f} MHz tone "
              f"on Profile 0.")
    except Exception:
        # Programming failed -- drop the cached client so a retry opens
        # a fresh one.
        try:
            lin.close()
        finally:
            _CACHED_CLIENT = None
        raise
    # On success: leave the client open and cached for the recorder.


# ---------------------------------------------------------------------------
# Stand-alone CLI for bench validation
# ---------------------------------------------------------------------------
_REG_NAMES = {
    0x00: "CFR1", 0x01: "CFR2", 0x02: "CFR3", 0x03: "CFR4",
    0x04: "Lower Freq Sweep Limit",
    0x05: "Upper Freq Sweep Limit",
    0x06: "Rising Sweep Ramp Rate",
    0x07: "Falling Sweep Ramp Rate",
    0x08: "Linear Sweep Ramp Rate",
    0x09: "Lower Programmable Modulus",
    0x0A: "Upper Programmable Modulus",
    0x0B: "Profile 0 FTW", 0x0C: "Profile 0 Phase",
    0x0D: "Profile 1 FTW", 0x0E: "Profile 1 Phase",
    0x0F: "Profile 2 FTW", 0x10: "Profile 2 Phase",
    0x11: "Profile 3 FTW", 0x12: "Profile 3 Phase",
    0x13: "Profile 4 FTW", 0x14: "Profile 4 Phase",
    0x15: "Profile 5 FTW", 0x16: "Profile 5 Phase",
    0x17: "Profile 6 FTW", 0x18: "Profile 6 Phase",
    0x19: "Profile 7 FTW", 0x1A: "Profile 7 Phase",
    0x1B: "USR 0",
}


# ---------------------------------------------------------------------------
# Tone programming
# ---------------------------------------------------------------------------
# AD9914 register addresses used by program_tone()
_ADDR_CFR1 = 0x00
_ADDR_CFR2 = 0x01
_ADDR_CFR3 = 0x02
_ADDR_PROFILE0_FTW = 0x0B

# Default CFR3 enabling on-chip PLL with REF_CLK input divider bypass.
# Bit field summary (per AD9914 datasheet, verify if you change clocking):
#   [23:16] N divider = 100 (0x64)            -> 25 MHz x 100 = 2.5 GHz SYSCLK
#   [15]    REFCLK divider ResetB = 1 (normal)
#   [14]    REFCLK divider bypass = 1 (skip on-chip /2 prescaler)
#   [11:8]  Charge pump current = 0xD (large, helps PLL lock)
#   [7:0]   PLL enable + reserved defaults (0xD2)
# Yields 0x0064C8D2. Override via --cfr3 if your bench wants a different
# multiplier or charge-pump current.
DEFAULT_CFR3_PLL_X100 = 0x0064C8D2

# CFR2 defaults to single-tone mode after master reset; we rewrite it so
# the chip is in a known state and the parallel-port profile select uses
# Profile 0 (which is hardwired by IOCFG = 1000).
DEFAULT_CFR2 = 0x00800900

DEFAULT_REF_CLK_HZ = 25_000_000.0
DEFAULT_PLL_N = 100
DEFAULT_PLL_LOCK_DELAY_S = 0.005  # PLL locks in <1 ms typ; be generous.


def program_tone(client: LinduinoClient,
                 freq_hz: float,
                 ref_clk_hz: float = DEFAULT_REF_CLK_HZ,
                 pll_n: int = DEFAULT_PLL_N,
                 cfr3: Optional[int] = None,
                 cfr2: int = DEFAULT_CFR2,
                 verify: bool = True) -> int:
    """Program AD9914 to output a single tone at ``freq_hz``.

    Sequence:
      1. Master reset (clears all registers to defaults).
      2. SYNC_IO pulse (clean SPI engine).
      3. CFR1 <- 4-wire SPI mode (so subsequent reads work).
      4. CFR2 <- single-tone, parallel-port profile select.
      5. CFR3 <- PLL enable with N = ``pll_n``.
      6. IO_UPDATE; wait ``DEFAULT_PLL_LOCK_DELAY_S`` for PLL lock.
      7. Profile 0 FTW <- computed FTW for ``freq_hz`` at SYSCLK = ref_clk * pll_n.
      8. IO_UPDATE.

    Returns the FTW that was written, so the caller can log it.
    """
    sysclk = float(ref_clk_hz) * float(pll_n)
    if sysclk < 1e9:
        print(f"[AD9914] WARNING: SYSCLK={sysclk/1e9:.3f} GHz is below the"
              " AD9914 minimum (~1 GHz). PLL may not lock.", file=sys.stderr)
    if freq_hz >= sysclk / 2:
        raise ValueError(
            f"freq_hz {freq_hz/1e6:.3f} MHz exceeds Nyquist for SYSCLK "
            f"{sysclk/1e9:.3f} GHz. Pick a lower tone or higher SYSCLK."
        )

    if cfr3 is None:
        # Build CFR3 from pll_n on top of the default flags.
        cfr3 = (DEFAULT_CFR3_PLL_X100 & 0xFF00FFFF) | ((int(pll_n) & 0xFF) << 16)

    ftw = int(round((float(freq_hz) / sysclk) * (1 << 32))) & 0xFFFFFFFF

    print(f"[AD9914] program_tone: f={freq_hz/1e6:.6f} MHz, "
          f"REF_CLK={ref_clk_hz/1e6:.3f} MHz, N={pll_n}, "
          f"SYSCLK={sysclk/1e9:.3f} GHz, FTW=0x{ftw:08X}, CFR3=0x{cfr3:08X}",
          file=sys.stderr)

    client.master_reset()
    client.sync_io()
    client.write_register(_ADDR_CFR1, 0x00000002)  # 4-wire mode
    client.io_update()
    time.sleep(0.001)
    client.write_register(_ADDR_CFR2, cfr2)
    client.write_register(_ADDR_CFR3, cfr3)
    client.io_update()
    time.sleep(DEFAULT_PLL_LOCK_DELAY_S)  # let PLL acquire lock
    client.write_register(_ADDR_PROFILE0_FTW, ftw)
    client.io_update()

    if verify:
        try:
            got_ftw = client.read_register(_ADDR_PROFILE0_FTW)
            got_cfr3 = client.read_register(_ADDR_CFR3)
            print(f"[AD9914] read-back FTW=0x{got_ftw:08X}, "
                  f"CFR3=0x{got_cfr3:08X}", file=sys.stderr)
            if got_ftw != ftw:
                print("[AD9914] WARNING: FTW read-back mismatch!",
                      file=sys.stderr)
        except Exception as exc:
            print(f"[AD9914] verify read failed: {exc}", file=sys.stderr)

    return ftw


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Dump AD9914 registers via Linduino DC2026 SPI."
    )
    parser.add_argument("--port", help="Serial COM port (default: env or COM4).")
    parser.add_argument("--baud", type=int,
                        help="Baud rate (default: env or 115200).")
    parser.add_argument("--no-init", action="store_true",
                        help="Skip the firmware INIT (reset + 4-wire setup).")
    parser.add_argument("--reset-only", action="store_true",
                        help="Just send a master reset and exit.")
    parser.add_argument("--program-tone", type=float, default=None,
                        metavar="FREQ_HZ",
                        help="Program AD9914 to output a single tone at the"
                             " given frequency in Hz.")
    parser.add_argument("--ref-clk", type=float, default=DEFAULT_REF_CLK_HZ,
                        help="REF_CLK frequency in Hz "
                             f"(default {DEFAULT_REF_CLK_HZ/1e6:.0f} MHz).")
    parser.add_argument("--pll-n", type=int, default=DEFAULT_PLL_N,
                        help=f"PLL feedback divider "
                             f"(default {DEFAULT_PLL_N}).")
    parser.add_argument("--cfr3", type=lambda x: int(x, 0), default=None,
                        help="Override CFR3 with explicit value (hex ok).")
    parser.add_argument("--addrs", nargs="*", type=lambda x: int(x, 0),
                        help="Addresses to read (default: all 0x00..0x1B).")
    args = parser.parse_args(argv)

    if args.port:
        os.environ["AD9914_LINDUINO_PORT"] = args.port
    if args.baud:
        os.environ["AD9914_LINDUINO_BAUD"] = str(args.baud)
    if args.no_init:
        os.environ["AD9914_LINDUINO_NOINIT"] = "1"

    client = LinduinoClient(init=not args.no_init)
    try:
        if args.reset_only:
            client.master_reset()
            print("Master reset pulse sent.")
            return 0

        if args.program_tone is not None:
            program_tone(
                client,
                freq_hz=args.program_tone,
                ref_clk_hz=args.ref_clk,
                pll_n=args.pll_n,
                cfr3=args.cfr3,
            )
            print(f"Tone programmed at {args.program_tone/1e6:.6f} MHz.")
            return 0

        addrs = args.addrs if args.addrs else list(range(0x00, 0x1C))
        print(f'{"Addr":>5} {"Hex":>10}  Name')
        print("-" * 60)
        for a in addrs:
            try:
                v = client.read_register(a)
                print(f"  0x{a:02X} 0x{v:08X}  {_REG_NAMES.get(a, '')}")
            except Exception as exc:
                print(f"  0x{a:02X} ERR        {exc}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
