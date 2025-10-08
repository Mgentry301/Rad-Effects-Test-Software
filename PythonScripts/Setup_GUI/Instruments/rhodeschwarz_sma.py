import pyvisa

class RhodeSchwarzSMA:
    def get_frequency(self):
        """Query the current output frequency in Hz."""
        try:
            resp = self.instr.query("FREQ?")
            return float(resp)
        except Exception as e:
            print(f"Error querying frequency: {e}")
            return None

    def get_power(self):
        """Query the current output power in dBm."""
        try:
            resp = self.instr.query("POW?")
            return float(resp)
        except Exception as e:
            print(f"Error querying power: {e}")
            return None
    def set_output(self, on: bool):
        """Turn output on or off, with auto-reconnect if session is invalid."""
        try:
            # Try to send command
            if on:
                self.on()
            else:
                self.off()
        except Exception as e:
            # If session is invalid, try to reconnect and retry
            if 'Invalid session' in str(e) or 'closed' in str(e):
                try:
                    self.rm = pyvisa.ResourceManager()
                    self.instr = self.rm.open_resource(self.addr)
                    self.instr.timeout = 5000
                    self.instr.write_termination = '\n'
                    self.instr.read_termination = '\n'
                    if on:
                        self.on()
                    else:
                        self.off()
                except Exception as e2:
                    print(f"SMA reconnect failed: {e2}")
                    raise e2
            else:
                raise e
    """
    Wrapper for Rhode & Schwarz SMA Signal Generator (USB connection).
    Provides methods to set frequency, power, and toggle RF output.
    """
    def __init__(self, addr):
        self.addr = addr
        self.rm = pyvisa.ResourceManager()
        self.instr = self.rm.open_resource(self.addr)
        self.instr.timeout = 5000
        self.instr.write_termination = '\n'
        self.instr.read_termination = '\n'

    def open(self):
        # For GUI compatibility; does nothing if already open
        return True

    def get_identification(self):
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

    def open(self):
        """Dummy open method for GUI compatibility."""
        return True
