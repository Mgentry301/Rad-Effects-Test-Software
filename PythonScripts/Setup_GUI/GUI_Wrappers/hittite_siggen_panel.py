from PyQt5 import QtWidgets, QtCore
from Instruments.hittite_siggen import HittiteSigGen

class HittiteSigGenPanel(QtWidgets.QWidget):
    def on_toggle_output(self):
        if self.dev is None:
            self.status_label.setText('Not connected')
            self.output_btn.setChecked(False)
            self._update_output_btn_color(False)
            return
        on = self.output_btn.isChecked()
        try:
            self.dev.set_output(on)
            self.output_btn.setText('Output On' if on else 'Output Off')
            self._update_output_btn_color(on)
            self.status_label.setText(f'Output {"ON" if on else "OFF"}')
        except Exception as e:
            self.status_label.setText(f'Failed to set output: {e}')
            self.output_btn.setChecked(not on)
            self._update_output_btn_color(not on)
    def set_tab_name_callback(self, callback):
        self.name_edit.textChanged.connect(callback)
    """Panel for Hittite Signal Generator (USB)."""
    def __init__(self, resource, parent=None):
        super().__init__(parent)
        self.resource = resource
        self.dev = None  # HittiteSigGen instance
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

            # Connection row
        row = QtWidgets.QHBoxLayout()
        self.resource_edit = QtWidgets.QLineEdit(self.resource)
        self.connect_btn = QtWidgets.QPushButton('Connect')
        self.connect_btn.clicked.connect(self.on_connect)
        row.addWidget(QtWidgets.QLabel('VISA Resource:'))
        row.addWidget(self.resource_edit)
        row.addWidget(self.connect_btn)
        layout.addLayout(row)

        # Name box row
        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(QtWidgets.QLabel('Name (tab label):'))
        self.name_edit = QtWidgets.QLineEdit()
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # Frequency control
        freq_row = QtWidgets.QHBoxLayout()
        freq_row.addWidget(QtWidgets.QLabel('Frequency:'))
        self.freq_edit = QtWidgets.QLineEdit('1')
        freq_row.addWidget(self.freq_edit)
        self.freq_unit_combo = QtWidgets.QComboBox()
        self.freq_unit_combo.addItems(['GHz', 'MHz', 'KHz', 'Hz'])
        self.freq_unit_combo.setCurrentIndex(0)
        freq_row.addWidget(self.freq_unit_combo)
        self.freq_set_btn = QtWidgets.QPushButton('Set Frequency')
        self.freq_set_btn.clicked.connect(self.on_set_frequency)
        freq_row.addWidget(self.freq_set_btn)
        layout.addLayout(freq_row)

        # Power control
        pow_row = QtWidgets.QHBoxLayout()
        pow_row.addWidget(QtWidgets.QLabel('Power (dB):'))
        self.pow_edit = QtWidgets.QLineEdit('0')
        pow_row.addWidget(self.pow_edit)
        self.pow_set_btn = QtWidgets.QPushButton('Set Power')
        self.pow_set_btn.clicked.connect(self.on_set_power)
        pow_row.addWidget(self.pow_set_btn)
        layout.addLayout(pow_row)

        # Readouts
        stats_group = QtWidgets.QGroupBox('Current Settings')
        stats_layout = QtWidgets.QGridLayout()
        self.meas_freq = QtWidgets.QLabel('-')
        self.meas_pow = QtWidgets.QLabel('-')
        font = self.meas_freq.font()
        font.setPointSize(16)
        font.setBold(True)
        self.meas_freq.setFont(font)
        self.meas_pow.setFont(font)
        stats_layout.addWidget(QtWidgets.QLabel('Frequency:'), 0, 0)
        stats_layout.addWidget(self.meas_freq, 0, 1)
        stats_layout.addWidget(QtWidgets.QLabel('Power:'), 1, 0)
        stats_layout.addWidget(self.meas_pow, 1, 1)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Bottom controls
        bottom = QtWidgets.QHBoxLayout()
        self.read_btn = QtWidgets.QPushButton('Read Now')
        self.read_btn.clicked.connect(self.read_once)
        bottom.addWidget(self.read_btn)
        layout.addLayout(bottom)

        self.status_label = QtWidgets.QLabel('')
        layout.addWidget(self.status_label)

        # Output On/Off button at the bottom
        out_row = QtWidgets.QHBoxLayout()
        self.output_btn = QtWidgets.QPushButton('Output Off')
        self.output_btn.setCheckable(True)
        self.output_btn.setChecked(False)
        self.output_btn.clicked.connect(self.on_toggle_output)
        self._update_output_btn_color(False)
        out_row.addWidget(self.output_btn)
        layout.addLayout(out_row)


    def close(self):
        try:
            if self.dev is not None:
                self.dev.close()
        except Exception:
            pass

    def on_connect(self):
        res = self.resource_edit.text().strip()
        if not res:
            self.status_label.setText('Enter VISA resource or SN')
            return
        try:
            dev = HittiteSigGen(res)
            dev.open()
            idn = dev.get_identification()
            self.dev = dev
            self.status_label.setText(f'Connected: {idn.strip()}')
        except Exception as e:
            self.status_label.setText(f'Connect failed: {e}')

    def on_set_frequency(self):
        if self.dev is None:
            self.status_label.setText('Not connected')
            return
        try:
            freq_val = float(self.freq_edit.text())
            unit = self.freq_unit_combo.currentText()
            multiplier = {'GHz': 1e9, 'MHz': 1e6, 'KHz': 1e3, 'Hz': 1}[unit]
            freq = freq_val * multiplier
            self.dev.set_frequency(freq)
            self.status_label.setText(f'Set frequency to {freq_val} {unit} ({freq:.0f} Hz)')
        except Exception as e:
            self.status_label.setText(f'Set frequency failed: {e}')

    def on_set_power(self):
        if self.dev is None:
            self.status_label.setText('Not connected')
            return
        try:
            power = float(self.pow_edit.text())
            self.dev.set_power(power)
            self.status_label.setText(f'Set power to {power} dB')
        except Exception as e:
            self.status_label.setText(f'Set power failed: {e}')

    def read_once(self):
        if self.dev is None:
            self.status_label.setText('Not connected')
            return
        try:
            freq = self.dev.get_frequency()
        except Exception:
            freq = None
        try:
            pow = self.dev.get_power()
        except Exception:
            pow = None
        self.meas_freq.setText('N/A' if freq is None else f'{freq:.2f} Hz')
        self.meas_pow.setText('N/A' if pow is None else f'{pow:.2f} dB')
        self.status_label.setText('Read complete')
        
    def _update_output_btn_color(self, on):
        if on:
            self.output_btn.setStyleSheet('background-color: #4CAF50; color: white;')
        else:
            self.output_btn.setStyleSheet('background-color: #F44336; color: white;')