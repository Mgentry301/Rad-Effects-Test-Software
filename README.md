Bench scaffolding for Rad-Effects-Test-Software

Run the example using the canonical package under `SEE_Tester`:

    python -m SEE_Tester.scripts.run_bench SEE_Tester/bench/examples/bench_config.json

The `SEE_Tester/bench` package contains adapters, standalone instrument
drivers, a CSV recorder, and an example runner. Extend the runner and
device logic to wire your product-specific register reads.

Dependencies
------------
Install runtime dependencies before connecting to real instruments:

    python -m pip install -r requirements.txt


Getting started (Windows)
-------------------------

A small helper script is provided to install the Python dependencies and create a Desktop shortcut to the Setup GUI launcher. You can run this by copying and pasting the powershell line into the terminal on VS code. If you do not see a terminal: click terminal (toolbar at the top) -> New Terminal to open the terminal.

Run from PowerShell (from the repo root):

    powershell -ExecutionPolicy Bypass -File .\setup_repo.ps1

This will:
- Install packages from `requirements.txt` using the `python` or `py` command available in PATH.
- Create a Desktop shortcut named "Rad Effects Setup GUI.lnk" that points to `PythonScripts/Setup_GUI/launch_setup_gui.pyw`.


