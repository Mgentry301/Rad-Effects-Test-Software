import pyvisa as visa


class Keithley2230:
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
