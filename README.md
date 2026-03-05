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

- ~~Break up `setup_gui.py` into smaller modules to improve readability, shorten file lengths, and make future implementations easier.~~ *(done – see table below)*
- Simplify register export to Excel by writing decimal values directly instead of storing hex strings, improving readability and plotting.

### `setup_gui.py` module breakdown

The original monolithic `setup_gui.py` has been split into focused mixin modules.
`MainWindow` in `setup_gui.py` inherits from every mixin so all behaviour is unchanged.

| File | Responsibility |
|---|---|
| `setup_gui.py` | Main window class, UI layout (`__init__`), logging helpers, `closeEvent`, app entry point |
| `excel_manager.py` | Excel workbook open / save / sheet management, bench-info writes |
| `recording_manager.py` | Prime & record controls, supply / spectrum / register recording threads |
| `config_manager.py` | Save / load instrument configs, disconnect all instruments |
| `alias_manager.py` | Bench-alias profiles, Settings tab UI, startup alias prompt |
| `notes_manager.py` | Notes tab UI, save / load / auto-populate notes |
| `power_manager.py` | Power on / off / toggle, sequencing, hard reset |
| `programming_manager.py` | Configure Part logic, logic-file browsing, soft reset |
| `instrument_manager.py` | VISA scan, add / close instrument panels, tab management |

- Have dewesoft and setup GUI communicate with eachother to sync data reccording
-     - communication should be able to handle the trigger of reccording data
-     - garage workaround would be communicate via a voltage truned on with the setup gui and monitored with the dewesoft
- ~~Getting setup notes integrated into the GUI~~ *(done – see Notes tab)*


