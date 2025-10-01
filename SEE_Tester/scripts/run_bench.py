"""CLI wrapper inside SEE_Tester/scripts to run the bench runner.

This is equivalent to the previous scripts/run_bench.py but lives under
the canonical SEE_Tester package.
"""
import sys


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python -m SEE_Tester.scripts.run_bench <bench-config.json>")
        return 2

    try:
        # Import lazily so we can print a friendly hint if dependencies are missing
        from ..bench import runner
    except Exception as e:
        print("Failed to import bench.runner:", e)
        print("Install dependencies: python -m pip install -r requirements.txt")
        return 3

    return runner.run_bench(argv[0])


if __name__ == "__main__":
    raise SystemExit(main())
