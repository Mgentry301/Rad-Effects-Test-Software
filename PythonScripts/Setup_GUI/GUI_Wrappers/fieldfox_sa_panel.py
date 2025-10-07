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
            self.status_label.setText("Connected")
            self.set_settings_enabled(True)
        except Exception:
            self.status_label.setText("Connection Failed")
            self.set_settings_enabled(False)
        # Start capture thread only after connection
        if self._capture_thread is None and self.sa.inst is not None:
            import threading
            def capture_thread():
                unit = self.unit_combo.currentText()
                try:
                    freq = self.sa.get_freq_axis(unit)
                except Exception:
                    freq = None
                while self._capture_thread_running:
                    try:
                        amplitudes = self.sa.capture_spectrum()
                        if freq is not None and amplitudes is not None:
                            if self._spectrum_buffer.full():
                                self._spectrum_buffer.get()
                            self._spectrum_buffer.put((freq, amplitudes))
                    except Exception:
                        pass
                    import time; time.sleep(0.1)
            self._capture_thread = threading.Thread(target=capture_thread, daemon=True)
            self._capture_thread.start()

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
        self.apply_btn = QtWidgets.QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_settings)
        layout.addWidget(self.apply_btn)
        self.canvas = SpectrumCanvas(self)
        layout.addWidget(self.canvas)
        self.status_label = QtWidgets.QLabel("Disconnected")
        layout.addWidget(self.status_label)

    def apply_settings(self):
        if self.sa.inst is None:
            QtWidgets.QMessageBox.warning(self, "Not Connected", "Instrument is not connected. Please connect first.")
            return
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

    def update_spectrum(self):
        try:
            if not self._spectrum_buffer.empty():
                self.freq, self.amplitudes = self._spectrum_buffer.get()
                if self.freq is not None and self.amplitudes is not None:
                    self.canvas.plot(self.freq, self.amplitudes)
        except Exception:
            pass

    def close(self):
        self.sa.close()
        self.timer.stop()
        self._capture_thread_running = False

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
        self.ax.set_xlim(freq.min(), freq.max())
        self.ax.set_ylim(amplitudes.min() - 2, amplitudes.max() + 2)
        self.canvas.draw()

# Matplotlib Qt backend import
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
