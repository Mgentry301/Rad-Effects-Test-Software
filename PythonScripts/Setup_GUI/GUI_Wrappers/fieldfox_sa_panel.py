from PyQt5 import QtWidgets, QtCore
import matplotlib.pyplot as plt
import numpy as np
from Instruments.fieldfox_sa import FieldFoxSA

class FieldFoxSAPanel(QtWidgets.QWidget):
    def __init__(self, visa_address, parent=None):
        super().__init__(parent)
        self.sa = FieldFoxSA(visa_address)
        self.name_edit = QtWidgets.QLineEdit(visa_address)  # For tab naming compatibility
        self.init_ui()
        self.freq = None
        self.amplitudes = None
        import threading
        import queue
        self._spectrum_buffer = queue.Queue(maxsize=1)
        self._capture_thread_running = True
        self._capture_thread = None
    # Streaming state (controls capture + plotting updates)
        self.streaming_enabled = True
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_spectrum)
        self.timer.start(1000)  # update every second

    def set_settings_enabled(self, enabled):
        self.center_edit.setEnabled(enabled)
        self.span_edit.setEnabled(enabled)
        self.start_edit.setEnabled(enabled)
        self.stop_edit.setEnabled(enabled)
        self.unit_combo.setEnabled(enabled)
        self.apply_btn.setEnabled(enabled)

    def on_connect(self):
        try:
            self.sa.open()
            try:
                # Clear status and pending I/O; reduces -410/-420 on first queries
                self.sa.sync()
            except Exception:
                pass
            self.status_label.setText("Connected")
            self.set_settings_enabled(True)
            # Start capture shortly after connect so manual add shows live plot
            try:
                if self.streaming_enabled:
                    QtCore.QTimer.singleShot(200, self.start_capture_thread)
            except Exception:
                if self.streaming_enabled:
                    self.start_capture_thread()
        except Exception as e:
            self.status_label.setText(f"Connection Failed: {e}")
            self.set_settings_enabled(False)
    # Capture thread will refresh freq axis each loop, reflecting future setting changes

    def start_capture_thread(self):
        """Idempotently start spectrum capture thread (safe to call multiple times)."""
        if self._capture_thread is not None:
            return
        if self.sa.inst is None:
            return
        if not self.streaming_enabled:
            return
        import threading, time
        def capture_thread():
            # Always use current unit and fetch freq axis each loop so X-axis reflects UI changes
            freq = None
            while self._capture_thread_running:
                try:
                    unit = self.unit_combo.currentText()
                    try:
                        freq = self.sa.get_freq_axis(unit)
                    except Exception:
                        freq = None
                    amplitudes = self.sa.capture_spectrum()
                    if freq is not None and amplitudes is not None:
                        if self._spectrum_buffer.full():
                            try:
                                self._spectrum_buffer.get_nowait()
                            except Exception:
                                pass
                        self._spectrum_buffer.put((freq, amplitudes))
                except Exception:
                    pass
                time.sleep(1)
        self._capture_thread = threading.Thread(target=capture_thread, daemon=True)
        self._capture_thread.start()

    def stop_capture_thread(self):
        if self._capture_thread is None:
            return
        self._capture_thread_running = False
        try:
            self._capture_thread.join(timeout=1.5)
        except Exception:
            pass
        self._capture_thread = None
        self._capture_thread_running = True

    def retry_connect(self):
        # User can call this to retry connection
        self.on_connect()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.center_edit = QtWidgets.QLineEdit("4.0")
        self.span_edit = QtWidgets.QLineEdit("8.0")
        self.start_edit = QtWidgets.QLineEdit("")
        self.stop_edit = QtWidgets.QLineEdit("")
        self.unit_combo = QtWidgets.QComboBox()
        self.unit_combo.addItems(["GHz", "MHz"])
        form.addRow("Center Frequency:", self.center_edit)
        form.addRow("Span:", self.span_edit)
        form.addRow("Start Frequency:", self.start_edit)
        form.addRow("Stop Frequency:", self.stop_edit)
        form.addRow("Unit:", self.unit_combo)
        form.addRow("Instrument Name:", self.name_edit)
        layout.addLayout(form)
        # Streaming toggle button
        btn_row = QtWidgets.QHBoxLayout()
        self.stream_btn = QtWidgets.QPushButton("Pause Streaming")
        self.stream_btn.setCheckable(True)
        self.stream_btn.setChecked(True)
        self.stream_btn.toggled.connect(self.toggle_streaming)
        btn_row.addWidget(self.stream_btn)
        layout.addLayout(btn_row)
        self.apply_btn = QtWidgets.QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_settings)
        layout.addWidget(self.apply_btn)
        self.connect_btn = QtWidgets.QPushButton("Connect to FieldFox")
        self.connect_btn.clicked.connect(self.on_connect)
        layout.addWidget(self.connect_btn)
        self.status_label = QtWidgets.QLabel("Not Connected")
        layout.addWidget(self.status_label)
        self.canvas = SpectrumCanvas(self)
        layout.addWidget(self.canvas)
        # Disable settings until connected
        self.set_settings_enabled(False)

    def toggle_streaming(self, checked: bool):
        """Toggle live streaming/plotting of spectrum."""
        self.streaming_enabled = bool(checked)
        if self.streaming_enabled:
            self.stream_btn.setText("Pause Streaming")
            # Start capture if connected
            try:
                if self.sa.inst is not None:
                    self.start_capture_thread()
            except Exception:
                pass
        else:
            self.stream_btn.setText("Start Streaming")
            # Stop capture thread; keep last plot displayed
            try:
                self.stop_capture_thread()
            except Exception:
                pass

    def apply_settings(self):
        if self.sa.inst is None:
            QtWidgets.QMessageBox.warning(self, "Not Connected", "Instrument is not connected. Please connect first.")
            return
        # Pause capture to avoid VISA query races during settings update
        self.stop_capture_thread()
        try:
            # Clear/CLS/OPC before applying new settings
            self.sa.sync()
        except Exception:
            pass
        unit = self.unit_combo.currentText()
        center = self.center_edit.text().strip()
        span = self.span_edit.text().strip()
        start = self.start_edit.text().strip()
        stop = self.stop_edit.text().strip()
        if center:
            self.sa.set_center(center, unit)
        if span:
            self.sa.set_span(span, unit)
        if start:
            self.sa.set_start(start, unit)
        if stop:
            self.sa.set_stop(stop, unit)
        # Resume capture after settings apply
        if self.streaming_enabled:
            self.start_capture_thread()

    def update_spectrum(self):
        try:
            if not self._spectrum_buffer.empty():
                self.freq, self.amplitudes = self._spectrum_buffer.get()
                if self.freq is not None and self.amplitudes is not None:
                    self.canvas.plot(self.freq, self.amplitudes)
        except Exception:
            pass

    def close(self):
        self.stop_capture_thread()
        self.sa.close()
        self.timer.stop()

class SpectrumCanvas(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = None
        self.line = None
        self.setMinimumHeight(300)
        self.setMinimumWidth(600)
        self.ax.set_xlabel("Frequency")
        self.ax.set_ylabel("Amplitude (dBm)")
        self.ax.set_title("FieldFox Spectrum")
        self.ax.grid(True, linestyle="--", alpha=0.5)
        self.fig.tight_layout()
        self.canvas = FigureCanvasQTAgg(self.fig)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def plot(self, freq, amplitudes):
        if self.line is None:
            self.line, = self.ax.plot(freq, amplitudes, lw=1.5, color="royalblue")
        else:
            self.line.set_xdata(freq)
            self.line.set_ydata(amplitudes)
        try:
            fmin = float(np.min(freq))
            fmax = float(np.max(freq))
            if fmin == fmax:
                eps = 1e-6 if fmin == 0 else abs(fmin) * 1e-6
                fmin -= eps
                fmax += eps
            self.ax.set_xlim(fmin, fmax)
        except Exception:
            pass
        try:
            amin = float(np.min(amplitudes))
            amax = float(np.max(amplitudes))
            if amin == amax:
                eps = 0.1
                amin -= eps
                amax += eps
            self.ax.set_ylim(amin - 2, amax + 2)
        except Exception:
            pass
        self.canvas.draw()

# Matplotlib Qt backend import
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
