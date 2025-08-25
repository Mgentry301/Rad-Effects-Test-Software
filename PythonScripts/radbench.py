import pyvisa as visa

class Keithley2230():
    def __init__(self, addr):
        self.addr = addr 
        self.rm = visa.ResourceManager()
        self.instr = self.rm.open_resource(self.addr) # opens communication with Keithley2230

    def on(self):
        # Turns on Keithley2230
        command = "OUTP 1"
        self.instr.write(command)

    def off(self):
        # Turns off Keithley2230
        command = "OUTP 0"
        try:
            self.instr.write(command)
        except Exception as e:
            self.instr.close()

    def meas_volt(self, channel):
        try:
            command_complete = int(self.instr.query("*OPC?"))
            command = "FETC:VOLT? " + channel
            volt = self.instr.query(command)
            if (channel == "ALL"):
                volt = volt.strip('\n').split(',')
                volt_arr = []
                for i in volt:
                    volt_arr.append(float(i))
                return volt_arr
            else:
                return float(volt)
        except Exception as e:
            if channel == "ALL":
                return [None, None, None]
            else:
                return None

    def meas_curr(self, channel):
        try:
            command_complete = int(self.instr.query("*OPC?"))
            command = "FETC:CURR? " + channel
            curr = self.instr.query(command)
            if (channel == "ALL"):
                curr = curr.strip('\n').split(',')
                curr_arr = []
                for i in curr:
                    curr_arr.append(float(i))
                return curr_arr
            else:
                return float(curr)
        except Exception as e:
            if channel == "ALL":
                return [None, None, None]
            else:
                return None

    def set_volt_and_curr(self, channel, voltage, current):
        # channel must be "CH1", "CH2", "CH3", or "ALL"
        # voltage must be a float from 0 to 30
        # current must be a float from 0 to 6
        command = "APPL " + channel + ", " + str(voltage) + ", " + str(current)
        self.instr.write(command)

    def close(self):
        try:
            self.instr.close()
        except Exception:
            pass
        try:
            self.rm.close()
        except Exception:
            pass

class KeysightE36233A():
    def __init__(self, addr):
        self.addr = addr 
        self.rm = visa.ResourceManager()
        self.instr = self.rm.open_resource(self.addr) # opens communication with Keysight

    def meas_curr(self, channel):
        curr = []
        curr.append(self.instr.query("MEAS:CURR? CH1")) 
        curr.append(self.instr.query("MEAS:CURR? CH2")) 
        return curr

    def meas_volt(self, channel):
        volt = []
        volt.append(self.instr.query("MEAS:VOLT? CH1")) 
        volt.append(self.instr.query("MEAS:VOLT? CH2"))
        return volt

class RohdeSchwarzSMA():
    def __init__(self, addr):
        self.addr = addr
        self.rm = visa.ResourceManager()
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
