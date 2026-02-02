Bench scaffolding for Rad-Effects-Test-Software

Getting started (Windows)
-------------------------

A small helper script is provided to install the Python dependencies and create a Desktop shortcut to the Setup GUI launcher. You can run this by copying and pasting the powershell line into the terminal on VS code. If you do not see a terminal: click terminal (toolbar at the top) -> New Terminal to open the terminal.

Run from PowerShell (from the repo root):

    powershell -ExecutionPolicy Bypass -File .\setup_repo.ps1

This will:
- Install packages from `requirements.txt` using the `python` or `py` command available in PATH.
- Create a Desktop shortcut named "Rad Effects Setup GUI.lnk" that points to `PythonScripts/Setup_GUI/launch_setup_gui.pyw`.


Future updates/improvements
---------------------------

- Break up `setup_gui.py` into smaller modules to improve readability, shorten file lengths, and make future implementations easier.
- Simplify register export to Excel by writing decimal values directly instead of storing hex strings, improving readability and plotting.


