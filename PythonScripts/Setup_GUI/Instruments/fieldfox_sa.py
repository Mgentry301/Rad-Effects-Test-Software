import pyvisa
import numpy as np
import time
import threading
from typing import Optional

class FieldFoxSA:
    def __init__(self, visa_address):
        self.visa_address = visa_address
        self.rm = None
        self.inst = None
        self._io_lock = threading.RLock()
        self._last_io_ts = 0.0
        self._min_io_interval = 0.05  # 50 ms pacing between IO ops
        self._ready = False
        # Guard to avoid recursion during recovery/sync flows
        self._in_recover = False

    def open(self):
        self.rm = pyvisa.ResourceManager()
        # Use message-based termination for SCPI; binary reads ignore termination
        self.inst = self.rm.open_resource(
            self.visa_address,
            timeout=8000,
            read_termination="\n",
            write_termination="\n",
        )
        # Increase chunk size to handle larger binary blocks more reliably
        try:
            self.inst.chunk_size = max(getattr(self.inst, 'chunk_size', 20480), 1024 * 1024)
        except Exception:
            pass
        # Robust initialization handshake
        try:
            self._session_prepare()
            # Select SA mode and wait completion
            self._safe_write(":INST:SEL 'SA'")
            self._opc_wait(timeout_ms=2000)
            # Continuous sweep ON
            self._safe_write(":INIT:CONT ON")
            self._opc_wait(timeout_ms=1000)
            # Set binary little-endian data format
            self._safe_write(":FORM:DATA REAL,32")
            # Probe points with a short timeout; ignore if not ready yet
            try:
                _ = self._safe_query(":SWE:POIN?", retries=2, timeout_ms=1000)
            except Exception:
                pass
            self._ready = True
        except Exception:
            # Non-fatal; mark not ready (panel can still try later)
            self._ready = False

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
        # Use fully qualified SENSE domain to avoid parser ambiguities
        self._safe_write(f":SENS:FREQ:CENT {center} {unit}")

    def set_span(self, span, unit="GHz"):
        self._safe_write(f":SENS:FREQ:SPAN {span} {unit}")

    def set_start(self, start, unit="GHz"):
        self._safe_write(f":SENS:FREQ:STAR {start} {unit}")

    def set_stop(self, stop, unit="GHz"):
        self._safe_write(f":SENS:FREQ:STOP {stop} {unit}")

    def get_freq_axis(self, unit="GHz"):
        # Query using SENSE domain; fewer -110 header errors on some FW revs
        f_start_hz = float(self._safe_query(":SENS:FREQ:STAR?", timeout_ms=1200))
        f_stop_hz = float(self._safe_query(":SENS:FREQ:STOP?", timeout_ms=1200))
        trace_len = int(self._safe_query(":SENS:SWE:POIN?", timeout_ms=1200))
        factor = 1e9 if unit == "GHz" else 1e6 if unit == "MHz" else 1.0
        freq = np.linspace(f_start_hz, f_stop_hz, trace_len) / factor
        return freq

    def capture_spectrum(self):
        if self.inst is None:
            raise RuntimeError("Instrument not open")
        last_exc = None
        # Try binary up to 3 times
        for _ in range(3):
            try:
                with self._io_lock:
                    self._io_throttle()
                    return self.inst.query_binary_values(
                    ":TRAC:DATA?",
                    datatype="f",
                    is_big_endian=False,
                    container=np.array,
                    )
            except pyvisa.VisaIOError as e:
                last_exc = e
                self._recover(backoff=0.08)
            except Exception as e:  # malformed block, fallback
                last_exc = e
                break
        # Fallback to ASCII if binary failed
        try:
            txt = self._safe_query(":TRAC:DATA?", timeout_ms=1500)
            parts = [p for p in txt.replace("\n"," ").split(',') if p.strip()]
            return np.array([float(p) for p in parts])
        except Exception:
            if last_exc:
                raise last_exc
            raise

    # --- Robust helpers ---
    # Low-level raw IO helpers: no retries, no recovery calls
    def _write_raw(self, cmd: str):
        try:
            with self._io_lock:
                self._io_throttle()
                self.inst.write(cmd)
        except Exception:
            # Swallow to avoid recursion during recovery
            pass

    def _query_raw(self, cmd: str, timeout_ms: Optional[int] = None) -> Optional[str]:
        old_timeout = None
        try:
            with self._io_lock:
                self._io_throttle()
                if timeout_ms is not None:
                    try:
                        old_timeout = self.inst.timeout
                        self.inst.timeout = timeout_ms
                    except Exception:
                        old_timeout = None
                return self.inst.query(cmd)
        except Exception:
            return None
        finally:
            if timeout_ms is not None and old_timeout is not None:
                try:
                    with self._io_lock:
                        self.inst.timeout = old_timeout
                except Exception:
                    pass

    def _sync(self, backoff: float = 0.02):
        # Use raw ops to avoid recover recursion
        try:
            if hasattr(self.inst, 'clear'):
                with self._io_lock:
                    self.inst.clear()
        except Exception:
            pass
        for _ in range(2):
            self._write_raw("*CLS")
            ok = self._query_raw("*OPC?", timeout_ms=800)
            if ok:
                break
            time.sleep(backoff)

    # Public sync for callers (e.g., GUI load flows)
    def sync(self, backoff: float = 0.02):
        self._sync(backoff=backoff)

    def _safe_write(self, cmd: str, retries: int = 3):
        for i in range(retries):
            try:
                with self._io_lock:
                    self._io_throttle()
                    self.inst.write(cmd)
                return
            except Exception as e:
                # Handle common transient errors
                if i < retries - 1 and not self._in_recover:
                    self._recover(backoff=0.06)
                    continue
                raise e

    def _safe_query(self, cmd: str, retries: int = 3, timeout_ms: Optional[int] = None):
        last = None
        for i in range(retries):
            old_timeout = None
            try:
                with self._io_lock:
                    self._io_throttle()
                    if timeout_ms is not None:
                        try:
                            old_timeout = self.inst.timeout
                            self.inst.timeout = timeout_ms
                        except Exception:
                            old_timeout = None
                    return self.inst.query(cmd)
            except Exception as e:
                last = e
                if i < retries - 1 and not self._in_recover:
                    self._recover(backoff=0.06)
                    continue
            finally:
                if timeout_ms is not None and old_timeout is not None:
                    try:
                        with self._io_lock:
                            self.inst.timeout = old_timeout
                    except Exception:
                        pass
        raise last

    # Pace IO to avoid flooding instrument
    def _io_throttle(self):
        now = time.monotonic()
        delta = now - self._last_io_ts
        if delta < self._min_io_interval:
            time.sleep(self._min_io_interval - delta)
        self._last_io_ts = time.monotonic()

    # Drain system errors and resync
    def _drain_errors(self):
        try:
            for _ in range(4):
                err = self._query_raw("SYST:ERR?", timeout_ms=500)
                if not err:
                    break
                if err.strip().startswith('0'):
                    break
        except Exception:
            pass

    def _opc_wait(self, timeout_ms: int = 1000):
        _ = self._safe_query("*OPC?", timeout_ms=timeout_ms)

    def _recover(self, backoff: float = 0.05):
        if self._in_recover:
            return
        self._in_recover = True
        try:
            self._sync(backoff=backoff)
            self._drain_errors()
        except Exception:
            pass
        finally:
            self._in_recover = False

    def _session_prepare(self):
        # Clear IO, status, verify comms, drain errors (raw to avoid recursion on startup)
        try:
            with self._io_lock:
                if hasattr(self.inst, 'clear'):
                    self.inst.clear()
        except Exception:
            pass
        self._write_raw("*CLS")
        _ = self._query_raw("*OPC?", timeout_ms=800)
        _ = self._query_raw("*IDN?", timeout_ms=1200)
        self._drain_errors()

    @property
    def ready(self) -> bool:
        return bool(self._ready)
