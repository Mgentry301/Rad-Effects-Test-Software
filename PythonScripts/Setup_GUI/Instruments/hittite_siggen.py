import pyvisa
import logging

class HittiteSigGen:
    def set_output(self, on: bool):
        """Turn output on or off."""
        if self.dev is None:
            raise RuntimeError("Device not open")
        cmd = 'OUTP ON' if on else 'OUTP OFF'
        self.logger.debug(f"Set output: {cmd}")
        self.dev.write(cmd)
    """PyVISA wrapper for Hittite Signal Generator (USB)."""
    def __init__(self, resource):
        self.resource = resource
        self.rm = None
        self.dev = None
        self.logger = logging.getLogger("HittiteSigGen")
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

    def set_frequency(self, freq_hz: float):
        cmd = f"FREQ {freq_hz}"
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def set_power(self, power_db: float):
        cmd = f"POW {power_db}"
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def get_frequency(self):
        cmd = "FREQ?"
        self.logger.debug(f"Query: {cmd}")
        resp = self.dev.query(cmd)
        self.logger.debug(f"Response: {resp}")
        return float(resp)

    def get_power(self):
        cmd = "POW?"
        self.logger.debug(f"Query: {cmd}")
        resp = self.dev.query(cmd)
        self.logger.debug(f"Response: {resp}")
        return float(resp)
