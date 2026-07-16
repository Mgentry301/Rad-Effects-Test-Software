# Raspberry Pi register readback — design & rationale

In-depth reference for the planned Raspberry Pi bringup + in-situ register-monitoring
backend. The README "Future improvements" section is the short version; this is the
full design so it can be picked up later.

## Goal

For parts that are programmed from a Raspberry Pi (over its SPI bus) instead of ACE,
make the Pi the backend for **both**:

1. **Bringup / configuration** of the DUT (one-time write sequence), and
2. **In-situ register monitoring** during irradiation — repeatedly reading a chosen
   register set to catch and timestamp single-event upsets/functional interrupts
   (SEU/SEFI) as bit flips.

Critically, the Pi register data must land in the **same single Excel workbook** as the
supply reads and spectrum reads — reusing the existing recording pipeline, not a new one.

## Current state (already in the GUI)

- **`ssh_manager.py` (`SshMixin`)** — Programming tab "Raspberry Pi (SSH)" panel:
  connect/disconnect with timeout + watchdog; list/run Pi scripts; bind a bringup
  command to a config via a `pi_script` block; passworded `sudo -S` (password never
  logged); per-run API log to `pi_run_logs/AD9082 Run X reg log.txt`; fetch of the
  device's own register log (e.g. `nco_test.log`) into a companion `… - registers.txt`.
- **Config `pi_script` schema** (in a config JSON, e.g. `configs/AD9082 TID.json`):
  ```json
  "pi_script": {
    "label": "AD9082 NCO test",
    "dir": "~/AD9082_API-Rel1.7.0/src/ad9082_app/platform/raspi",
    "build": "make all",
    "cmd": "./build/nco_test",
    "args": "0 100000000",
    "sudo": true,
    "reg_log": "nco_test.log"
  }
  ```
- Local/per-machine files (`ssh_settings.json`, `pi_run_logs/`) are git-ignored.

## The existing single-Excel recording pipeline

Three data streams already funnel into one workbook via `ExcelMixin` (one sheet per
type), each with its own non-blocking writer queue:

| Stream         | Queue                          | Sheet             |
|----------------|--------------------------------|-------------------|
| Supply reads   | `global_recorder._write_q`     | supply sheet      |
| Spectrum reads | `_spectrum_write_q`            | spectrum sheet    |
| Register reads | `_register_write_q`            | `register reads`  |

The register recorder (`recording_manager.py::_start_register_recording`) also provides,
for free:

- an **EXPECTED baseline row** (row 2) captured from the first successful read;
- **conditional formatting** that red-highlights any data cell differing from the
  baseline — this is the SEU/SEFI catcher;
- a live **`RegisterMonitorDialog`** (`register_monitor.py`) that shows latest vs expected
  with `MISMATCH (Δ=…)` using `_register_latest_values` / `_register_baseline`.

### The pluggable backend hook (this is the integration point)

`_start_register_recording` is already backend-agnostic. It calls
`_load_custom_register_backend(program_logic_path)`; if the config's
`program_logic_path` module defines these two functions, they are used instead of ACE:

```python
def open_register_client():          # open the Pi/SPI session once per recording run
    ...                              # return any handle (SSH client, socket, etc.)
    return client

def read_register(client, addr):     # return the register value at addr as an int
    ...
```

Providing those routes Pi register data into the same `register reads` sheet with the
same baseline/highlight/monitor — **no changes to the Excel or recording layers.**

The register set to monitor comes from the config's `register_read_array` (currently
empty for `AD9082 TID.json`; populate it with the addresses to watch).

## Per-part tool: one codebase, two actions

Each part gets a single Pi-side binary (e.g. `<part>_tool`) with sub-commands, **not**
two separate scripts:

- `config` — write the init/bringup sequence (one-time).
- `readback` — pure, **non-destructive** SPI reads producing a timestamped register
  dump.

Why separate actions matter for rad testing: **readback must never write.** If a
readback pass re-ran the config, it would rewrite radiation-flipped bits and mask the
exact SEU you are trying to detect. So: configure once at bringup, then read back many
times without touching the write path. This is a mode/argument, not a copy-pasted
script. The GUI already supports it (config's `pi_script` drives bringup; the same
binary can be pointed at `readback`).

## Performance: why the Pi beats ACE for large, fast dumps

The current loop reads **one register at a time** and sleeps between sweeps, regardless
of backend:

```python
for addr in reg_list:            # N sequential reads
    val = read_register(client, addr)
time.sleep(0.05)
```

Full-sweep time ≈ N × (per-read latency) + sleep. Per-read latency dominates:

| Path                                  | Per-register cost                                   | 500-reg sweep | Sweep rate |
|---------------------------------------|-----------------------------------------------------|---------------|------------|
| **ACE (now)**                         | .NET remoting → USB → SPI round trip ≈ 2–5 ms       | ~1–2.5 s      | ~0.4–1 Hz  |
| **Pi, one-reg-per-SSH-call** (naive)  | process spawn / SSH RTT ≈ 5–30 ms                   | worse         | worse      |
| **Pi, one-reg-per-call to a daemon**  | Ethernet RTT ≈ 0.3–1 ms + µs of SPI                 | ~150–500 ms   | ~2–6 Hz    |
| **Pi, whole dump in one C sweep**     | N local SPI reads + **1** transfer back             | single-digit ms | 100+ Hz  |

(Latencies are engineering estimates; ratios are the point. Measure on the bench for
real numbers.)

Hard floor is SPI: at 10 MHz, a 24-bit read (16-bit addr + 8-bit data) is ~2.4 µs of
clock, ~5–10 µs realistic through Linux `spidev` (ioctl + CS overhead). 500 regs ≈
2.5–5 ms of pure SPI per sweep → on-device ceiling ~200–400 Hz for 500 regs (higher for
fewer regs or a faster SPI clock; many parts read at 20–50 MHz). ACE can't approach this
because every register pays a USB + remoting round trip.

**Key idea:** turn "N round trips" into "1 round trip + N local SPI reads." The Pi reads
all N back-to-back on local hardware SPI, then ships one snapshot; the slow link and the
per-transaction latency are amortized over the whole dump instead of paid N times.

## Three implementation tiers (increasing performance)

1. **Per-register over a persistent Pi daemon** — fits the current
   `read_register(client, addr)` contract unchanged; ~2–6 Hz on 500 regs. Beats ACE,
   still RTT-bound.
2. **Bulk dump per sweep (recommended for large N)** — the daemon reads all N in one C
   loop and returns the array; the Python side caches it and serves the sweep. Needs a
   small optional batch hook, `read_registers(client, addrs) -> {addr: val}`, called once
   per sweep in `_start_register_recording` instead of N times. Single-digit-ms sweeps →
   100+ Hz.
3. **On-device diff / event-only (fastest, best for SEU)** — the daemon reads all N at
   high rate (kHz), compares against a stored baseline **on the Pi**, and returns only the
   *changes* (addr, old, new, timestamp). The link and Excel then see sparse SEU events,
   not N values every sweep. Highest acquisition rate, lowest PC load — still lands in the
   same `register reads` sheet (append change rows).

## Where the bottleneck moves once reads are batched

- **Link transfer size** — N values/sweep over link-local Ethernet. 500 × 100 Hz = 50k
  values/s ≈ a few hundred KB/s — fine for Ethernet, but real.
- **Excel writer** — `writer_loop` batches (flush every ~150 rows / ~8 s), so it buffers,
  but sustained 50k cells/s bloats the workbook and stresses memory over a long run.

Mitigation: **decouple acquisition rate from Excel write rate.** For rad testing you
usually don't need 100 Hz of full dumps in the sheet — you need a fast on-device sweep to
timestamp the SEU precisely, and the sheet only needs the event (tier 3) or a periodic
full snapshot. That yields kHz-class detection with a manageable file.

## Relationship to the existing `nco_test.log` fetch

Two different jobs — keep both:

- **`register_read_array` + Pi backend → Excel** = the time-series, SEU-highlighting
  monitor during irradiation (this design).
- **`nco_test.log` full-map dump → `.txt`** = a one-shot bringup snapshot. Fine to keep as
  a config-time artifact, or drop later.

## Concrete next steps

1. Add the optional `read_registers(client, addrs)` batch path to
   `_start_register_recording` (fall back to per-register `read_register` when a backend
   doesn't provide it).
2. Write the first part's `program_logic_path` module implementing
   `open_register_client()` + `read_register()` (and ideally `read_registers()`).
3. Build a small persistent Pi-side SPI daemon (bulk read; optional on-device baseline
   diff) and have `open_register_client()` connect to it.
4. Populate that part's config `register_read_array` with the addresses to monitor; keep
   `pi_script` for bringup.
5. Bench-measure real per-register and full-sweep latencies to replace the estimates
   above.

## Key files

- `PythonScripts/Setup_GUI/ssh_manager.py` — SSH panel, run scripts, sudo, per-run logs,
  reg-log fetch.
- `PythonScripts/Setup_GUI/recording_manager.py` — `_start_register_recording`,
  `_load_custom_register_backend`, `_resolve_program_logic_path`.
- `PythonScripts/Setup_GUI/register_monitor.py` — live SEU monitor dialog.
- `PythonScripts/Setup_GUI/excel_manager.py` — single-workbook `ExcelMixin`.
- `PythonScripts/Setup_GUI/configs/*.json` — `pi_script`, `reg_log`, `program_logic_path`,
  `register_read_array`.
