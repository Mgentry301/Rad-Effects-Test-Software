import time
import numpy as np
import pyvisa

VISA_ADDRESS = "USB0::0x2A8D::0x5C18::MY62151444::INSTR"
CENTER = 4.0
SPAN = 8.0
MAG = 'GHz'

def capture_spectrum_worker(
    data_queue,
    stop_event,
    visa_address=VISA_ADDRESS,
    center=CENTER,
    span=SPAN,
    mag=MAG,
    max_captures=None,
    freq_queue=None  # <-- add this
):
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(
        visa_address,
        timeout=10000,
        read_termination=None,
        write_termination="\n",
    )

    try:
        # Configure instrument
        inst.write(":INST:SEL 'SA'")
        inst.write(":INIT:CONT ON")
        inst.write(f":FREQ:CENT {center} {mag}")
        inst.write(f":FREQ:SPAN {span} {mag}")
        inst.write(":FORM:DATA REAL,32")

        # Precompute frequency axis
        f_start_hz = float(inst.query(":FREQ:STAR?"))
        f_stop_hz  = float(inst.query(":FREQ:STOP?"))
        trace_len  = int(inst.query(":SWE:POIN?"))
        if mag == 'GHz':
            factor = 1e9
        elif mag == 'MHz':
            factor = 1e6    
        freq_ghz = np.linspace(f_start_hz, f_stop_hz, trace_len) / factor

        # Send frequency axis to main thread ONCE
        if freq_queue is not None:
            freq_queue.put(freq_ghz.tolist())

        total_captures = 0

        while not stop_event.is_set():
            try:
                amplitudes = inst.query_binary_values(
                    ":TRAC:DATA?",
                    datatype="f",
                    is_big_endian=False,
                    container=np.array,
                )
                if amplitudes.size != trace_len:
                    continue  # Skip incomplete or mismatched reads

                # Put the amplitudes array into the queue
                data_queue.put(amplitudes)

                total_captures += 1
                if max_captures is not None and total_captures >= max_captures:
                    break

            except Exception:
                pass

    finally:
        try:
            inst.close()
        except Exception:
            pass
        rm.close()

# Standalone mode for live plotting
if __name__ == "__main__":
    import threading
    import queue
    import matplotlib.pyplot as plt

    data_queue = queue.Queue()
    stop_event = threading.Event()
    freq_queue = queue.Queue()

    def plotter(data_queue, stop_event, freq_queue):
        freq_ghz = None
        plt.ion()
        fig, ax = plt.subplots(figsize=(10, 6))
        line = None
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("Amplitude (dBm)")
        ax.set_title("Live Spectrum Capture")
        ax.grid(True, linestyle="--", alpha=0.5)
        fig.tight_layout()

        # Wait for frequency axis from freq_queue
        try:
            freq_ghz = np.array(freq_queue.get(timeout=10))
        except queue.Empty:
            print("Could not get frequency axis from instrument.")
            return

        while not stop_event.is_set():
            try:
                amplitudes = data_queue.get(timeout=1)
                if line is None:
                    line, = ax.plot(freq_ghz, amplitudes, lw=1.5, color="royalblue")
                    ax.set_xlim(freq_ghz.min(), freq_ghz.max())
                    ax.set_ylim(amplitudes.min() - 2, amplitudes.max() + 2)
                else:
                    line.set_ydata(amplitudes)
                    ax.set_ylim(amplitudes.min() - 2, amplitudes.max() + 2)
                fig.canvas.draw()
                fig.canvas.flush_events()
            except queue.Empty:
                continue
            except Exception:
                break
        plt.ioff()
        plt.show()

    worker_thread = threading.Thread(
        target=capture_spectrum_worker,
        args=(data_queue, stop_event),
        kwargs={'freq_queue': freq_queue}
    )
    plot_thread = threading.Thread(target=plotter, args=(data_queue, stop_event, freq_queue))

    worker_thread.start()
    plot_thread.start()

    print("Press Ctrl+C to stop live spectrum capture and plotting.")
    try:
        while worker_thread.is_alive() and plot_thread.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop_event.set()
        print("Stopping...")
    worker_thread.join()