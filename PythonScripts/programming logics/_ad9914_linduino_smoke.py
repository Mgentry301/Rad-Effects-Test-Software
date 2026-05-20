"""Reliability smoke test for the AD9914 Linduino backend.

Opens the Linduino serial port once, writes 0xDEADBEEF to Profile 0 FTW
(register 0x0B), reads it back, and reports pass/fail. Repeats N times so
we can spot intermittent transactions.

Run after flashing AD9914_Linduino/AD9914_Linduino.ino to the Linduino:

    python ".\PythonScripts\programming logics\_ad9914_linduino_smoke.py"

Override the COM port with the AD9914_LINDUINO_PORT env var:

    $env:AD9914_LINDUINO_PORT = "COM7"
    python ".\PythonScripts\programming logics\_ad9914_linduino_smoke.py"
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import AD9914_Linduino as a

TARGET = 0xDEADBEEF
N = 20

# Open once -- unlike the Cheetah smoke, we do NOT want to re-init on
# every iteration, because the Linduino INIT pulses MASTER_RESET which
# wipes our just-written value.
client = a.open_register_client()
try:
    passes = 0
    for i in range(N):
        try:
            client.write_register(0x0B, TARGET)
            v = a.read_register(client, 0x0B)
            ok = (v == TARGET)
            passes += int(ok)
            tag = "OK" if ok else "FAIL"
            print(f"{i:2d}: 0x{v:08X}  {tag}")
        except Exception as exc:
            print(f"{i:2d}: EXC {exc}")
        time.sleep(0.1)
    print(f"\n{passes}/{N} passed")
finally:
    a.close_register_client(client)
