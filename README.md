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


Raspberry Pi (SSH) control
--------------------------

Some parts are brought up and programmed from a Raspberry Pi (over its SPI bus) instead of through ACE. The Setup GUI's Programming tab includes a **Raspberry Pi (SSH)** panel that lets you drive the Pi directly from the bench PC:

- **Connect / disconnect** over SSH with a configurable connection timeout and a watchdog.
- **Run a Pi script** — list the scripts in a chosen directory on the Pi, or bind a specific bringup/config command to the active config via a `pi_script` block in the config JSON (directory, build step, command, arguments, and a `sudo` flag).
- **Passworded sudo** — when the part's program must run as root, the password from the connection field is piped to `sudo -S` at runtime; it is never written to the run logs.
- **Per-run logging** — each run is streamed live into the Run Log and saved to `pi_run_logs/AD9082 Run X reg log.txt`. The device's own detailed register read/write log (e.g. `nco_test.log`) is also fetched back from the Pi and saved as a companion `… - registers.txt` file.

Local/per-machine files (`ssh_settings.json`, `pi_run_logs/`) are git-ignored.


Future improvements
-------------------

The Pi path is intended to grow into the primary bringup **and** in-situ register-monitoring backend for parts that don't use ACE. Planned work:

### Per-part bringup + readback (one codebase, two actions)

- Each part gets a single Pi-side tool (e.g. `<part>_tool`) with sub-commands rather than separate scripts:
  - `config` — write the init/bringup sequence (one-time).
  - `readback` — pure, **non-destructive** SPI reads that produce a timestamped register dump. Kept separate so a readback pass never re-writes (and thus masks) radiation-flipped bits.
- The GUI already supports this: the config's `pi_script` drives bringup, and the same binary can be pointed at `readback` for monitoring.

### Register readback into the existing single Excel file

The goal is for **register reads, supply reads, and spectrum reads to all land in one workbook**, exactly like the current ACE flow. The register recorder is already backend-pluggable — a part's `program_logic_path` module can define:

```python
def open_register_client():          # open the Pi/SPI session once per run
    ...
def read_register(client, addr):     # return the register value as an int
    ...
```

Providing those two functions routes the Pi register data into the same `register reads` sheet, with the same EXPECTED baseline row, red-highlight-on-mismatch (SEU/SEFI catcher), and live Register Monitor as ACE — no new logging structure.

### Higher-throughput readback than ACE

For large register sets at high sweep rates, the key is to **batch the read on the Pi** instead of doing one round-trip per register:

- **Persistent Pi SPI daemon** — keep `/dev/spidev` open and answer read requests over a socket, so repeated reads are microsecond-class instead of paying a process-spawn/SSH cost each time.
- **Bulk dump per sweep** — the Pi reads the whole register set in one on-device C loop and ships the snapshot back once; a small `read_registers(client, addrs)` batch hook in the recorder lets the GUI do one call per sweep instead of N. This turns "N round trips" into "1 round trip + N local SPI reads" and is where the large speed-up over ACE comes from.
- **On-device baseline diff (SEU events only)** — the daemon can compare each sweep against a stored baseline on the Pi and send back only the *changes* (address, old, new, timestamp), enabling very high-rate on-device detection while keeping the link and Excel file light.

Net effect: the Pi can dump a large register map at a higher frequency than ACE — decisively so once the reads are batched on-device — which is what makes it attractive for catching and timestamping single-event upsets during irradiation.


