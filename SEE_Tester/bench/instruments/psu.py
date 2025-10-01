from pathlib import Path
from typing import Any, Dict, Optional

# Wrap existing implementation from local instrument driver
from .keithley2230 import Keithley2230


class PSUAdapter:
    """Minimal adapter for a programmable power supply."""

    def __init__(self, address: str, channel: str = "CH1"):
        self.address = address
        self.channel = channel
        self._inst: Optional[Keithley2230] = None

    def open(self) -> None:
        self._inst = Keithley2230(self.address)

    def close(self) -> None:
        if self._inst:
            self._inst.close()
            self._inst = None

    def identify(self) -> str:
        # Keithley2230 wrapper doesn't expose *IDN? in radbench.py; return address
        return f"Keithley2230 @ {self.address}"

    def set(self, voltage: float, current: float) -> None:
        if not self._inst:
            self.open()
        # The radbench API expects a channel string
        self._inst.set_volt_and_curr(self.channel, voltage, current)

    def get(self) -> Dict[str, Any]:
        if not self._inst:
            self.open()
        v = self._inst.meas_volt(self.channel)
        i = self._inst.meas_curr(self.channel)
        return {"voltage": v, "current": i}
