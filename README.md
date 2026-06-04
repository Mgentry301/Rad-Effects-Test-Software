Bench scaffolding for Rad-Effects-Test-Software

Getting started (Windows)
-------------------------

A small helper script is provided to install the Python dependencies and create a Desktop shortcut to the Setup GUI launcher. You can run this by copying and pasting the powershell line into the terminal on VS code. If you do not see a terminal: click terminal (toolbar at the top) -> New Terminal to open the terminal.

Run from PowerShell (from the repo root):

    powershell -ExecutionPolicy Bypass -File .\setup_repo.ps1

This will:
- Install python 3.13 if not already installed
- Install packages from `requirements.txt` using the `python` or `py` command available in PATH.
- Create a Desktop shortcut named "Rad Effects Setup GUI.lnk" that points to `PythonScripts/Setup_GUI/launch_setup_gui.pyw`.


Instrument communication setup (VISA / GPIB)
--------------------------------------------

The Python packages alone are not enough to talk to bench instruments. PyVISA needs a VISA backend (and, for GPIB, a separate controller driver). Follow these steps on a fresh Windows bench PC.

### 1. Verify the current PyVISA backend

Run this from the repo root:

    python -c "import pyvisa; rm = pyvisa.ResourceManager(); print(rm); print(rm.list_resources())"

- If it prints `Resource Manager of Visa Library at py` and `()`, you are on the pure-Python fallback (`pyvisa-py`) and have no real VISA backend installed. Continue with step 2.
- If it prints `Resource Manager of Visa Library at C:\windows\system32\visa32.dll` (or similar), NI-VISA / Keysight VISA is already installed. Skip to step 4.

### 2. Install NI-VISA

NI-VISA is not reliably available on `winget` (`winget install -e --id NI.NIVISA` typically returns "No package found"). Use the direct download:

- https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html

During install, make sure these are selected:
- **NI-VISA** (runtime)
- **NI Measurement & Automation Explorer (NI MAX)**

A free NI user account is required to download. **Reboot when finished.**

(Keysight IO Libraries Suite — https://www.keysight.com/find/iolib — is an equivalent alternative. Install one or the other, not both.)

After reboot, re-run the verification command from step 1. The backend should now be `visa32.dll` and any USB / serial / LAN instruments that NI MAX sees should appear in `list_resources()`.

### 3. Install NI-488.2 (only if you use GPIB)

NI-VISA does **not** include the GPIB controller driver. If you have an NI GPIB-USB-HS (or similar) and NI MAX shows the dongle with the warning *"Windows does not have a driver associated with your device"*, you need NI-488.2:

- https://www.ni.com/en/support/downloads/drivers/download.ni-488-2.html

Install, **reboot**, then unplug and replug the GPIB-USB-HS. NI MAX should now show a `GPIB0` interface under *Devices and Interfaces* (no warning).

### 4. Scan the GPIB bus

In NI MAX:
1. Expand *Devices and Interfaces*.
2. Right-click the `GPIB0` controller and choose **Scan for Instruments** (or press F5).
3. Each powered-on, uniquely-addressed instrument on the daisy chain should appear underneath.

If the scan finds nothing, check:
- All instruments on the chain are powered on.
- GPIB cables are fully seated and screwed down.
- Each instrument has a unique primary GPIB address (0–30; 0 is reserved for the controller).
- The controller's *System Controller* checkbox is enabled in NI MAX.

### 5. Confirm from Python

    python -c "import pyvisa; rm = pyvisa.ResourceManager(); print(rm.list_resources())"

Expected output (example):

    ('ASRL1::INSTR', 'ASRL3::INSTR', 'GPIB0::1::INSTR', 'GPIB0::4::INSTR', 'GPIB0::27::INSTR')

Quick `*IDN?` sanity check on every detected instrument:

    python -c "import pyvisa; rm=pyvisa.ResourceManager(); [print(a, '->', rm.open_resource(a).query('*IDN?').strip()) for a in rm.list_resources()]"

### Notes on other interfaces

- **USB-TMC instruments**: install the vendor's USB driver so Windows enumerates the device as a Test & Measurement device. If Device Manager shows a yellow warning on a USB-TMC device, install the vendor driver before expecting PyVISA to see it.
- **LAN / TCPIP instruments**: usually not auto-discovered. Add them in NI MAX (*Network Devices → Create New → VISA TCP/IP Resource*) or open them directly in code, e.g. `rm.open_resource('TCPIP0::192.168.1.50::INSTR')`.
- **Serial (ASRL)**: works out of the box once the USB-to-serial driver (FTDI / CP210x / etc.) is installed.


