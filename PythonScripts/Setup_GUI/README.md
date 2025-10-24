# Rad Effects Setup GUI

This GUI controls multiple bench instruments and records data. Use this guide to install dependencies and create a Desktop icon that launches without a console window.

## Prerequisites
- Windows with Python 3.10+ (Python 3.13 supported).
- VISA runtime/driver (NI-VISA or Keysight IO Libraries) so instruments enumerate.
- Optional: Analog Devices ACE for register recording features.

## Install dependencies
From the repo root:

```powershell
pip install -r requirements.txt
```

If you use a virtual environment, activate it first.

## Create the Desktop icon (no console window)
Use the provided PowerShell script to create a Desktop shortcut that targets pythonw.exe directly.

Run from repo root:

```powershell
powershell -ExecutionPolicy Bypass -File "PythonScripts/Setup_GUI/Support_Scrips/create_desktop_shortcut.ps1"
```

This creates "Rad Effects Setup GUI.lnk" on your Desktop. Double‑click it to launch the GUI without a terminal window.

### Notes
- If Python is installed in a non-default location, the script attempts to find `pythonw.exe` on PATH; otherwise edit `$pythonw` inside the script.
- If you move/rename the repo, re-run the script to update the shortcut paths.
- If you had an older pinned shortcut, unpin it to avoid launching via the deprecated .bat.

## Manual shortcut (optional)
- Target: `C:\Path\To\Python\pythonw.exe`
- Arguments: `"C:\Git\Rad-Effects-Test-Software\PythonScripts\Setup_GUI\setup_gui.py"`
- Start in: `C:\Git\Rad-Effects-Test-Software`
- Icon: `C:\Path\To\Python\pythonw.exe`

## Troubleshooting
- Register recording requires ACE remoting to be available.
- If VISA scan shows no devices, verify your VISA runtime and connections.
- Long recordings: the app uses a background Excel writer to avoid timing gaps.
