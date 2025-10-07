import pyvisa
import numpy as np

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
        self.inst.write(":INST:SEL 'SA'")
        self.inst.write(":INIT:CONT ON")
        self.inst.write(":FORM:DATA REAL,32")

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
        amplitudes = self.inst.query_binary_values(
            ":TRAC:DATA?",
            datatype="f",
            is_big_endian=False,
            container=np.array,
        )
        return amplitudes
