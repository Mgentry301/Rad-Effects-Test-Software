import time
from typing import Dict, Any, Iterable
from pathlib import Path

from .config import load_config
from .recorder.csv_recorder import CSVRecorder
from .instruments.psu import PSUAdapter
from .instruments.siggen import SigGenAdapter


ADAPTER_TYPE_MAP = {
    "psu": PSUAdapter,
    "siggen": SigGenAdapter,
}


def instantiate_instrument(spec: Dict[str, Any]):
    t = spec.get('type')
    addr = spec.get('address') or spec.get('addr')
    adapter_cls = ADAPTER_TYPE_MAP.get(t)
    if adapter_cls is None:
        raise ValueError(f"Unknown instrument type: {t}")
    return adapter_cls(addr)


def run_bench(config_path: str):
    cfg = load_config(config_path)

    # instantiate instruments
    instruments = {}
    for name, spec in cfg.get('instruments', {}).items():
        instruments[name] = instantiate_instrument(spec)

    # open and apply settings
    for name, inst in instruments.items():
        print(f"Opening {name}")
        inst.open()
        settings = cfg['instruments'][name].get('settings') or {}
        # small mapping for psu and siggen
        if hasattr(inst, 'set'):
            if 'voltage' in settings or 'current' in settings:
                inst.set(settings.get('voltage', 0), settings.get('current', 0))
            else:
                inst.set(settings.get('freq'), settings.get('power'))

    # device logic optional (not implemented here) - placeholder
    device_cfg = cfg.get('device') or {}
    product_config = device_cfg.get('product_config')
    if product_config:
        print(f"Device product config at {product_config} - loading and delegating to device logic if available")

    # recorder
    rec_path = cfg.get('recording', {}).get('path', 'run_output.csv')
    rec = CSVRecorder(rec_path)

    registers = cfg.get('recording', {}).get('registers', [])
    interval = cfg.get('recording', {}).get('interval_seconds', 0.1)
    duration = cfg.get('recording', {}).get('duration_seconds', 180)

    print(f"Starting recording: {len(registers)} registers, interval={interval}s, duration={duration}s")
    start = time.time()
    try:
        while (time.time() - start) < duration:
            ts = time.time()
            # For now, read registers by calling a method on a hypothetical device client
            # Users should implement `device_client.read_registers(registers)` and pass in config
            # Here we mock with placeholders or read from a specific instrument if needed
            row = {r: 'N/A' for r in registers}
            row['Timestamp'] = ts
            rec.write_row(row)
            time.sleep(interval)
    finally:
        for inst in instruments.values():
            try:
                inst.close()
            except Exception:
                pass


def main(config_path: str):
    """Alias for running from CLI modules."""
    return run_bench(config_path)
