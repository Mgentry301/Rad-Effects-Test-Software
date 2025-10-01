import pyvisa


class RohdeSchwarzSMA:
    def __init__(self, addr):
        self.addr = addr
        self.rm = pyvisa.ResourceManager()
        self.instr = self.rm.open_resource(self.addr)  # opens communication with SMA100A/B
        self.instr.timeout = 5000  # optional: increase timeout for long commands

    def identify(self):
        # Returns instrument identification string
        return self.instr.query("*IDN?")

    def set_frequency(self, freq_hz):
        # Sets frequency in Hz (e.g., 1e9 for 1 GHz)
        try:
            self.instr.write(f"FREQ {freq_hz}")
        except Exception as e:
            print(f"Error setting frequency: {e}")

    def set_power(self, power_dbm):
        # Sets output power in dBm
        try:
            self.instr.write(f"POW {power_dbm}")
        except Exception as e:
            print(f"Error setting power: {e}")

    def on(self):
        # Enables RF output
        try:
            self.instr.write("OUTP ON")
        except Exception as e:
            print(f"Error turning output ON: {e}")

    def off(self):
        # Disables RF output
        try:
            self.instr.write("OUTP OFF")
        except Exception as e:
            print(f"Error turning output OFF: {e}")

    def close(self):
        # Closes VISA session
        try:
            self.instr.close()
        except Exception:
            pass
        try:
            self.rm.close()
        except Exception:
            pass
