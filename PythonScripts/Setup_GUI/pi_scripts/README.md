# Raspberry Pi Programming Scripts

Staging folder for scripts that run **on the Raspberry Pi** to program the part
it is connected to. Each part will have its own script (and, later, its own
config file).

## How it works

1. Put a script here (e.g. `ad9082_program.py` or `program_part.sh`).
2. Copy it onto the Pi into the directory the GUI points at (default
   `~/pi_scripts`), for example:

   ```powershell
   scp "ad9082_program.py" "pi@[fe80::394c:9eb6:eb65:350f%6]:~/pi_scripts/"
   ```

3. In the Setup GUI **Programming** tab, under **Raspberry Pi (SSH)**:
   - Connect to the Pi.
   - Set **Script dir** to the folder on the Pi (default `~/pi_scripts`).
   - Click **Refresh**, pick the script, and click **Run Script**.

## Script conventions

- `*.py`  -> run with `python3 -u`
- `*.sh`  -> run with `bash`
- other   -> executed directly (must have the executable bit set)
- Tick the **sudo** checkbox to run with `sudo -n` (passwordless sudo) when the
  script needs root access (e.g. SPI / GPIO).
- Script output is streamed live into the Programming tab's Run Log.

> Config files per part will be added later.
