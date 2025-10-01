from typing import Any, Dict, Optional

from .rohde_schwarz_sma import RohdeSchwarzSMA


class SigGenAdapter:
    def __init__(self, address: str):
        self.address = address
        self._inst: Optional[RohdeSchwarzSMA] = None

    def open(self) -> None:
        self._inst = RohdeSchwarzSMA(self.address)

    def close(self) -> None:
        if self._inst:
            self._inst.close()
            self._inst = None

    def identify(self) -> str:
        if not self._inst:
            self.open()
        try:
            return self._inst.identify()
        except Exception:
            return f"SigGen @ {self.address}"

    def set(self, frequency: float = None, power_dbm: float = None) -> None:
        if not self._inst:
            self.open()
        if frequency is not None:
            self._inst.set_frequency(frequency)
        if power_dbm is not None:
            self._inst.set_power(power_dbm)

    def get(self) -> Dict[str, Any]:
        # Basic identify-only info for now
        return {"id": self.identify()}
