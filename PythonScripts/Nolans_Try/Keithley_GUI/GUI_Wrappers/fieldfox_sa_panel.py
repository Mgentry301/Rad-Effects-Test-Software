from PyQt5 import QtWidgets, QtCore
import matplotlib.pyplot as plt
import numpy as np
from Instruments.fieldfox_sa import FieldFoxSA

class FieldFoxSAPanel(QtWidgets.QWidget):
    def __init__(self, visa_address, parent=None):
        super().__init__(parent)
        self.sa = FieldFoxSA(visa_address)
        self.sa.open()
        self.name_edit = QtWidgets.QLineEdit(visa_address)  # For tab naming compatibility
        self.init_ui()
        self.freq = None
        self.amplitudes = None
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_spectrum)
        self.timer.start(1000)  # update every second

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

    def apply_settings(self):
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
            self.freq = self.sa.get_freq_axis(self.unit_combo.currentText())
            self.amplitudes = self.sa.capture_spectrum()
            if self.freq is not None and self.amplitudes is not None:
                self.canvas.plot(self.freq, self.amplitudes)
        except Exception:
            pass

    def close(self):
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
        self.ax.set_xlim(freq.min(), freq.max())
        self.ax.set_ylim(amplitudes.min() - 2, amplitudes.max() + 2)
        self.canvas.draw()

# Matplotlib Qt backend import
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
