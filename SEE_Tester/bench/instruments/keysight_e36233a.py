import pyvisa as visa


class KeysightE36233A:
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
