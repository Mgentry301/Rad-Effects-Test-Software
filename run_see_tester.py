"""Top-level launcher that runs the canonical SEE Tester bench runner.

This script adds the `SEE Tester` folder to sys.path so we can import the
bench runner even though the folder name contains a space. It then forwards
the provided config path to the runner's `main()` function.

Usage:
    python run_see_tester.py SEE_Tester/bench/examples/bench_config.json
"""
import sys
import os
from pathlib import Path


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python run_see_tester.py <path-to-bench-config.json>")
        return 2

    config_path = argv[0]

    repo_root = Path(__file__).resolve().parent
    see_tester_dir = repo_root / "SEE Tester"
    if not see_tester_dir.exists():
        print(f"Cannot find SEE Tester directory at {see_tester_dir}")
        return 3

    # Insert the SEE Tester folder onto sys.path so we can import the bench package
    sys.path.insert(0, str(see_tester_dir))

    try:
        # Import the runner module inside SEE Tester
        from bench import runner
    except Exception as e:
        print("Failed to import SEE Tester bench.runner:", e)
        print("Make sure required packages are installed (see requirements.txt).")
        print("Try: python -m pip install -r requirements.txt")
        return 4

    return runner.main(config_path)


if __name__ == "__main__":
    raise SystemExit(main())
