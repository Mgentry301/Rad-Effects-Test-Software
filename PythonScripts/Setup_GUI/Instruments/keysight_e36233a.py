import threading

import pyvisa

class KeysightE36233A:
    def fetch_all_voltages(self):
        """Return list of measured voltages for both channels.

        Uses MEASure (which triggers a fresh reading) with an explicit channel
        list. FETCh/`ALL` is not valid on this supply and returns nothing, so
        recordings would otherwise come back as zeros.
        """
        with self._lock:
            try:
                resp = self.inst.query("MEAS:VOLT? (@1,2)")
                return [float(x) for x in resp.strip().split(",") if x.strip() != ""]
            except Exception:
                return [self.measure_voltage(1), self.measure_voltage(2)]

    def fetch_all_currents(self):
        """Return list of measured currents for both channels."""
        with self._lock:
            try:
                resp = self.inst.query("MEAS:CURR? (@1,2)")
                return [float(x) for x in resp.strip().split(",") if x.strip() != ""]
            except Exception:
                return [self.measure_current(1), self.measure_current(2)]
    def __init__(self, visa_address):
        self.visa_address = visa_address
        self.rm = None
        self.inst = None
        # Serialize all VISA I/O: the GUI thread issues control commands while a
        # background recorder thread reads measurements. pyvisa resources are
        # not thread-safe, so concurrent access can corrupt commands (e.g. an
        # OUTP ON write interleaving with a MEAS query is silently dropped).
        self._lock = threading.RLock()

    def open(self):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(self.visa_address, timeout=5000)
        with self._lock:
            self.inst.write("*RST")
            self.inst.write("OUTP:ALL OFF")

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

    def set_voltage(self, channel, voltage):
        with self._lock:
            self.inst.write(f"VOLT {voltage}, (@{channel})")

    def set_current(self, channel, current):
        with self._lock:
            self.inst.write(f"CURR {current}, (@{channel})")

    def output_on(self, channel):
        with self._lock:
            self.inst.write(f"OUTP ON, (@{channel})")

    def output_off(self, channel):
        with self._lock:
            self.inst.write(f"OUTP OFF, (@{channel})")

    def measure_voltage(self, channel):
        with self._lock:
            return float(self.inst.query(f"MEAS:VOLT? (@{channel})"))

    def measure_current(self, channel):
        with self._lock:
            return float(self.inst.query(f"MEAS:CURR? (@{channel})"))

    # No changes needed for 'Read All' button; wrapper already supports measure_voltage and measure_current for both channels.
