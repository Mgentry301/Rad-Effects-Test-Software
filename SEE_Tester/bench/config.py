from pathlib import Path
import json
from typing import Dict, Any


def load_config(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    with p.open('r') as f:
        return json.load(f)
