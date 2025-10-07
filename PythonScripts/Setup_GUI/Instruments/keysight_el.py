import pyvisa
import logging

class KeysightEL:
    """PyVISA wrapper for Keysight EL34243A Dual Input DC Electronic Load (with correct mode/value SCPI)."""
    def __init__(self, resource):
        self.resource = resource
        self.rm = None
        self.dev = None
        self.logger = logging.getLogger("KeysightEL")
        if not self.logger.hasHandlers():
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

    def open(self):
        self.rm = pyvisa.ResourceManager()
        self.dev = self.rm.open_resource(self.resource, timeout=2000)
        try:
            self.dev.write_termination = '\n'
            self.dev.read_termination = '\n'
        except Exception:
            pass
        self.logger.info(f"Opened resource {self.resource}")

    def close(self):
        try:
            if self.dev is not None:
                self.dev.close()
            if self.rm is not None:
                self.rm.close()
        finally:
            self.dev = None
            self.rm = None
        self.logger.info("Closed resource")

    def get_identification(self):
        self.logger.debug("Query: *IDN?")
        resp = self.dev.query("*IDN?")
        self.logger.debug(f"Response: {resp}")
        return resp

    def select_channel(self, channel: int):
        cmd = f":INSTrument:NSELect {channel}"
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def set_input(self, channel: int, on: bool):
        self.select_channel(channel)
        cmd = f":INPut:STATe {'ON' if on else 'OFF'}"
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def set_mode(self, channel: int, mode: str):
        self.select_channel(channel)
        mapping = {'CC': 'CURR', 'CV': 'VOLT', 'CR': 'RES', 'CP': 'POW'}
        scpi_mode = mapping.get(mode.upper(), mode)
        cmd = f"MODE {scpi_mode}"
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def set_parameter(self, channel: int, mode: str, value: float):
        self.select_channel(channel)
        if mode.upper() == 'CC':
            cmd = f":CURRent:LEVel {value}"
        elif mode.upper() == 'CV':
            cmd = f":SOURce:VOLTage:LEVel {value}"
        elif mode.upper() == 'CR':
            cmd = f":SOURce:RESistance:LEVel {value}"
        else:
            raise ValueError("Unknown mode")
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def measure_current(self, channel: int):
        self.select_channel(channel)
        cmd = ":MEASure:CURRent?"
        self.logger.debug(f"Query: {cmd}")
        resp = self.dev.query(cmd)
        self.logger.debug(f"Response: {resp}")
        return float(resp)

    def measure_voltage(self, channel: int):
        self.select_channel(channel)
        cmd = ":MEASure:VOLTage?"
        self.logger.debug(f"Query: {cmd}")
        resp = self.dev.query(cmd)
        self.logger.debug(f"Response: {resp}")
        return float(resp)

    def get_input_state(self, channel: int):
        self.select_channel(channel)
        cmd = ":INPut:STATe?"
        self.logger.debug(f"Query: {cmd}")
        resp = self.dev.query(cmd).strip().upper()
        self.logger.debug(f"Response: {resp}")
        return resp in ('1', 'ON')
