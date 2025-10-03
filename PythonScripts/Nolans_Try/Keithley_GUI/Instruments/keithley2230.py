"""
Simple pyvisa wrapper for a Keithley 2230-30-1.

This exposes a minimal API used by the GUI. It uses VISA resource strings
and basic SCPI-like commands. Some SCPI dialects differ between firmware
revisions; if any command fails, the wrapper raises the underlying exception
so you can inspect/adjust the exact command string.

Note: by default the example resource string uses the serial number you
provided; adjust the resource string if your system enumerates differently.
"""
from typing import Optional
import pyvisa


class Keithley2230:
    def __init__(self, resource_string: str, timeout_ms: int = 5000):
        self.resource_string = resource_string
        self.rm = pyvisa.ResourceManager()
        self.res = None
        self.timeout_ms = timeout_ms

    def open(self):
        if self.res is not None:
            return
        self.res = self.rm.open_resource(self.resource_string)
        self.res.timeout = self.timeout_ms
        # Some devices like CR/LF termination
        try:
            self.res.write_termination = "\n"
            self.res.read_termination = "\n"
        except Exception:
            pass

    def close(self):
        if self.res is not None:
            try:
                self.res.close()
            finally:
                self.res = None

    def _select_channel(self, ch: int):
        if ch not in (1, 2, 3):
            raise ValueError("channel must be 1, 2 or 3")
        # Select channel for subsequent commands
        # Many Keithley supplies accept INST:NSEL <n>
        self.res.write(f"INST:NSEL {ch}")

    def set_voltage(self, ch: int, volts: float):
        """Set the source voltage for channel ch."""
        self._select_channel(ch)
        self.res.write(f"SOUR:VOLT {volts}")

    def set_current(self, ch: int, amps: float):
        """Set the current limit for channel ch."""
        self._select_channel(ch)
        self.res.write(f"SOUR:CURR {amps}")

    def set_output(self, ch: int, on: bool):
        """Turn channel ch output on/off."""
        self._select_channel(ch)
        self.res.write("OUTP ON" if on else "OUTP OFF")

    def measure_current(self, ch: int) -> Optional[float]:
        """Measure current on the selected channel and return as float in A.

        Returns None if the response cannot be converted to float.
        """
        self._select_channel(ch)
        # Many instruments support MEAS:CURR?
        resp = self.res.query("MEAS:CURR?")
        try:
            return float(resp.strip())
        except Exception:
            return None

    def get_voltage_setpoint(self, ch: int) -> Optional[float]:
        """Query the configured source voltage for channel ch."""
        self._select_channel(ch)
        try:
            resp = self.res.query("SOUR:VOLT?")
            return float(resp.strip())
        except Exception:
            return None

    def get_current_setpoint(self, ch: int) -> Optional[float]:
        """Query the configured current limit for channel ch."""
        self._select_channel(ch)
        try:
            resp = self.res.query("SOUR:CURR?")
            return float(resp.strip())
        except Exception:
            return None

    def get_output_state(self, ch: int) -> Optional[bool]:
        """Query whether the output for channel ch is ON (True) or OFF (False).

        Returns None if the query fails.
        """
        self._select_channel(ch)
        try:
            resp = self.res.query("OUTP?")
            val = resp.strip()
            # many instruments return 1/0
            if val in ("1", "ON", "On", "on"):
                return True
            if val in ("0", "OFF", "Off", "off"):
                return False
            # try numeric parse
            try:
                return bool(int(val))
            except Exception:
                return None
        except Exception:
            return None

    def get_identification(self) -> str:
        if self.res is None:
            raise RuntimeError("resource not open")
        return self.res.query("*IDN?")
