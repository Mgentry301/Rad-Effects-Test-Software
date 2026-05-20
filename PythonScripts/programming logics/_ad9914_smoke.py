"""Quick reliability smoke test for the AD9914 Cheetah backend."""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import AD9914 as a

TARGET = 0xDEADBEEF
N = 20

passes = 0
for i in range(N):
    try:
        c = a.open_register_client()
        c.write_register(0x0B, TARGET)
        v = a.read_register(c, 0x0B)
        a.close_register_client(c)
        ok = (v == TARGET)
        passes += int(ok)
        tag = "OK" if ok else "FAIL"
        print(f"{i:2d}: 0x{v:08X}  {tag}")
    except Exception as exc:
        print(f"{i:2d}: EXC {exc}")
    time.sleep(0.3)

print(f"\n{passes}/{N} passed")
