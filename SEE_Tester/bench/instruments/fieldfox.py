import time
import numpy as np
import pyvisa
from typing import Optional, Any


class FieldFoxCapture:
    def __init__(self, visa_address: str, center: float = 4.0, span: float = 8.0, mag: str = 'GHz'):
        self.visa_address = visa_address
        self.center = center
        self.span = span
        self.mag = mag
        self.rm = None
        self.inst = None

    def open(self, timeout: int = 10000):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(self.visa_address, timeout=timeout, read_termination=None, write_termination='\n')

    def close(self):
        try:
            if self.inst:
                self.inst.close()
        except Exception:
            pass
        try:
            if self.rm:
                self.rm.close()
        except Exception:
            pass

    def capture_once(self) -> Optional[np.ndarray]:
        if self.inst is None:
            self.open()

        try:
            self.inst.write(":INST:SEL 'SA'")
            self.inst.write(":INIT:CONT ON")
            self.inst.write(f":FREQ:CENT {self.center} {self.mag}")
            self.inst.write(f":FREQ:SPAN {self.span} {self.mag}")
            self.inst.write(":FORM:DATA REAL,32")

            f_start_hz = float(self.inst.query(":FREQ:STAR?"))
            f_stop_hz = float(self.inst.query(":FREQ:STOP?"))
            trace_len = int(self.inst.query(":SWE:POIN?"))

            amplitudes = self.inst.query_binary_values(":TRAC:DATA?", datatype='f', is_big_endian=False, container=np.array)
            if amplitudes.size != trace_len:
                return None
            return amplitudes
        except Exception:
            return None
