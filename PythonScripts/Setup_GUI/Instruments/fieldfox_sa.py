import pyvisa
import numpy as np
import time

class FieldFoxSA:
    def __init__(self, visa_address):
        self.visa_address = visa_address
        self.rm = None
        self.inst = None

    def open(self):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(
            self.visa_address,
            timeout=10000,
            read_termination=None,
            write_termination="\n",
        )
        # Basic initialization with small waits to let mode settle
        try:
            self.inst.write(":INST:SEL 'SA'")
            self.inst.write(":INIT:CONT ON")
            self.inst.write(":FORM:DATA REAL,32")  # binary little-endian float
            # Ensure trace points known
            _ = self.inst.query(":SWE:POIN?")
        except Exception:
            pass

    def close(self):
        if self.inst:
            try:
                self.inst.close()
            except Exception:
                pass
        if self.rm:
            try:
                self.rm.close()
            except Exception:
                pass

    def set_center(self, center, unit="GHz"):
        self.inst.write(f":FREQ:CENT {center} {unit}")

    def set_span(self, span, unit="GHz"):
        self.inst.write(f":FREQ:SPAN {span} {unit}")

    def set_start(self, start, unit="GHz"):
        self.inst.write(f":FREQ:STAR {start} {unit}")

    def set_stop(self, stop, unit="GHz"):
        self.inst.write(f":FREQ:STOP {stop} {unit}")

    def get_freq_axis(self, unit="GHz"):
        f_start_hz = float(self.inst.query(":FREQ:STAR?"))
        f_stop_hz = float(self.inst.query(":FREQ:STOP?"))
        trace_len = int(self.inst.query(":SWE:POIN?"))
        factor = 1e9 if unit == "GHz" else 1e6 if unit == "MHz" else 1.0
        freq = np.linspace(f_start_hz, f_stop_hz, trace_len) / factor
        return freq

    def capture_spectrum(self):
        if self.inst is None:
            raise RuntimeError("Instrument not open")
        last_exc = None
        # Try binary up to 3 times
        for _ in range(3):
            try:
                return self.inst.query_binary_values(
                    ":TRAC:DATA?",
                    datatype="f",
                    is_big_endian=False,
                    container=np.array,
                )
            except pyvisa.VisaIOError as e:
                last_exc = e
                time.sleep(0.05)
            except Exception as e:  # malformed block, fallback
                last_exc = e
                break
        # Fallback to ASCII if binary failed
        try:
            txt = self.inst.query(":TRAC:DATA?")
            parts = [p for p in txt.replace("\n"," ").split(',') if p.strip()]
            return np.array([float(p) for p in parts])
        except Exception:
            if last_exc:
                raise last_exc
            raise
