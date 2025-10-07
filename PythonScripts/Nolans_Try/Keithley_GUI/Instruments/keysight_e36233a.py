import pyvisa

class KeysightE36233A:
    def __init__(self, visa_address):
        self.visa_address = visa_address
        self.rm = None
        self.inst = None

    def open(self):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(self.visa_address, timeout=5000)
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
        self.inst.write(f"VOLT {voltage}, (@{channel})")

    def set_current(self, channel, current):
        self.inst.write(f"CURR {current}, (@{channel})")

    def output_on(self, channel):
        self.inst.write(f"OUTP ON, (@{channel})")

    def output_off(self, channel):
        self.inst.write(f"OUTP OFF, (@{channel})")

    def measure_voltage(self, channel):
        return float(self.inst.query(f"MEAS:VOLT? (@{channel})"))

    def measure_current(self, channel):
        return float(self.inst.query(f"MEAS:CURR? (@{channel})"))

    # No changes needed for 'Read All' button; wrapper already supports measure_voltage and measure_current for both channels.
