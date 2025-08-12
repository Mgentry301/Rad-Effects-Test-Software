#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import numpy as np
import matplotlib.pyplot as plt
import pyvisa

VISA_ADDRESS = "USB0::0x2A8D::0x5C18::MY62151444::INSTR"
CENTER_GHZ = 15.0
SPAN_GHZ = 1.0

def main():
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(
        VISA_ADDRESS,
        timeout=10000,
        read_termination=None,  # Binary transfer: no line termination
        write_termination="\n",
    )

    try:
        # Configure instrument
        inst.write(":INST:SEL 'SA'")
        inst.write(":INIT:CONT ON")
        inst.write(f":FREQ:CENT {CENTER_GHZ} GHz")
        inst.write(f":FREQ:SPAN {SPAN_GHZ} GHz")

        # Use fast binary data format
        inst.write(":FORM:DATA REAL,32")

        # Precompute frequency axis
        f_start_hz = float(inst.query(":FREQ:STAR?"))
        f_stop_hz  = float(inst.query(":FREQ:STOP?"))
        trace_len  = int(inst.query(":SWE:POIN?"))
        freq_ghz = np.linspace(f_start_hz, f_stop_hz, trace_len) / 1e9

        # Live plot setup
        plt.ion()
        fig, ax = plt.subplots(figsize=(10, 6))
        line, = ax.plot(freq_ghz, np.zeros(trace_len), lw=1.5, color="royalblue")
        ax.set_xlim(freq_ghz.min(), freq_ghz.max())
        ax.set_ylim(-100, 0)
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("Amplitude (dBm)")
        ax.set_title("FieldFox Live Spectrum (Fast Update)")
        ax.grid(True, linestyle="--", alpha=0.5)
        fig.tight_layout()

        # Logging counters
        total_captures = 0
        window_captures = 0
        last_log = time.monotonic()

        while True:
            try:
                amplitudes = inst.query_binary_values(
                    ":TRAC:DATA?",
                    datatype="f",
                    is_big_endian=False,
                    container=np.array,
                )
                if amplitudes.size != trace_len:
                    continue  # Skip incomplete or mismatched reads

                # Update plot efficiently
                line.set_ydata(amplitudes)
                ax.set_ylim(amplitudes.min() - 2, amplitudes.max() + 2)
                fig.canvas.draw()
                fig.canvas.flush_events()

                # Update counters
                total_captures += 1
                window_captures += 1

                # Log every 10 seconds
                now = time.monotonic()
                if now - last_log >= 10.0:
                    print(f"[{time.strftime('%H:%M:%S')}] Captures in last 10s: {window_captures} | Total: {total_captures}")
                    window_captures = 0
                    last_log = now

            except KeyboardInterrupt:
                print("Stopping capture...")
                break
            except Exception:
                # Ignore transient VISA/transfer issues and continue
                pass

    finally:
        try:
            inst.close()
        except Exception:
            pass
        rm.close()
        plt.ioff()
        plt.show()

if __name__ == "__main__":
    main()