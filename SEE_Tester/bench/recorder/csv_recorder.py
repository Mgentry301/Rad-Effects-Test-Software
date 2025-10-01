from pathlib import Path
from typing import Dict, Iterable, List
import csv


class CSVRecorder:
    """Simple CSV recorder that writes dict rows with a deterministic header.

    Usage:
        r = CSVRecorder(path)
        r.write_row({"Time": "...", "Reg_0x10": "0x01"})
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._header: List[str] | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write_row(self, row: Dict[str, object]) -> None:
        # Determine header on first write
        if self._header is None:
            self._header = ["Timestamp"] + sorted(row.keys())
            write_header = True
        else:
            write_header = False

        # Compose ordered row
        ordered = [row.get(k, "") for k in self._header if k != "Timestamp"]

        # Write using append mode
        with open(self.path, "a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(self._header)
            writer.writerow([row.get("Timestamp", "")] + ordered)
