from PyQt5 import QtWidgets, QtCore, QtGui
from Instruments.keysight_el import KeysightEL


class KeysightELPanel(QtWidgets.QWidget):
    def on_connect(self):
        res = self.resource_edit.text().strip()
        if not res:
            self.status_label.setText('Enter VISA resource or SN')
            return
        try:
            dev = KeysightEL(res)
            dev.open()
            idn = dev.get_identification()
            self.dev = dev
            self.status_label.setText(f'Connected: {idn.strip()}')
            # Initialize per-channel input states
            for ch in (1, 2):
                try:
                    on = self.dev.get_input_state(ch)
                except Exception:
                    on = False
                self._set_input_toggle_ui(ch, on)
        except Exception as e:
            self.status_label.setText(f'Connect failed: {e}')
    def set_tab_name_callback(self, callback):
        self.name_edit.textChanged.connect(callback)
    """Panel for Keysight EL34243A-style dual-input electronic load with dedicated per-channel controls."""
    def __init__(self, resource, parent=None):
        super().__init__(parent)
        self.resource = resource
        self.dev = None  # KeysightEL instance
        self.status_label = QtWidgets.QLabel('')
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

    # (Enable/disable per channel removed; dedicated controls shown at all times)

        # Per-channel controls
        ch_grid = QtWidgets.QGridLayout()
        header_font = QtGui.QFont()
        header_font.setBold(True)
        ch_grid.addWidget(QtWidgets.QLabel('Channel'), 0, 0)
        ch_grid.addWidget(QtWidgets.QLabel('Mode'), 0, 1)
        ch_grid.addWidget(QtWidgets.QLabel('Value'), 0, 2)
        ch_grid.addWidget(QtWidgets.QLabel('Apply'), 0, 3)
        ch_grid.addWidget(QtWidgets.QLabel('Input'), 0, 4)
        ch_grid.addWidget(QtWidgets.QLabel('Voltage'), 0, 5)
        ch_grid.addWidget(QtWidgets.QLabel('Current'), 0, 6)

        # Channel 1 row
        ch_grid.addWidget(QtWidgets.QLabel('Ch 1'), 1, 0)
        self.mode_combo_ch1 = QtWidgets.QComboBox()
        self.mode_combo_ch1.addItems(['CC', 'CV', 'CR', 'CP', 'Disable'])
        ch_grid.addWidget(self.mode_combo_ch1, 1, 1)
        self.mode_value_ch1 = QtWidgets.QLineEdit('0.1')
        ch_grid.addWidget(self.mode_value_ch1, 1, 2)
        self.mode_apply_ch1 = QtWidgets.QPushButton('Apply Ch1')
        self.mode_apply_ch1.clicked.connect(lambda: self.on_apply_mode(1))
        ch_grid.addWidget(self.mode_apply_ch1, 1, 3)
        self.input_toggle_ch1 = QtWidgets.QPushButton('Input Off')
        self.input_toggle_ch1.setCheckable(True)
        self.input_toggle_ch1.clicked.connect(lambda: self.on_toggle_input(1))
        ch_grid.addWidget(self.input_toggle_ch1, 1, 4)
        self.meas_voltage_ch1 = QtWidgets.QLabel('-')
        self.meas_current_ch1 = QtWidgets.QLabel('-')
        f1 = QtGui.QFont(); f1.setPointSize(11); f1.setBold(True)
        self.meas_voltage_ch1.setFont(f1)
        self.meas_current_ch1.setFont(f1)
        ch_grid.addWidget(self.meas_voltage_ch1, 1, 5)
        ch_grid.addWidget(self.meas_current_ch1, 1, 6)
        # Ramp controls for Channel 1
        ch_grid.addWidget(QtWidgets.QLabel('Rise Time (s)'), 1, 7)
        self.rise_time_ch1 = QtWidgets.QLineEdit('0')
        ch_grid.addWidget(self.rise_time_ch1, 1, 8)
        self.ramp_enable_ch1 = QtWidgets.QCheckBox('Enable Ramp')
        ch_grid.addWidget(self.ramp_enable_ch1, 1, 9)

        # Channel 2 row
        ch_grid.addWidget(QtWidgets.QLabel('Ch 2'), 2, 0)
        self.mode_combo_ch2 = QtWidgets.QComboBox()
        self.mode_combo_ch2.addItems(['CC', 'CV', 'CR', 'CP', 'Disable'])
        ch_grid.addWidget(self.mode_combo_ch2, 2, 1)
        self.mode_value_ch2 = QtWidgets.QLineEdit('0.1')
        ch_grid.addWidget(self.mode_value_ch2, 2, 2)
        self.mode_apply_ch2 = QtWidgets.QPushButton('Apply Ch2')
        self.mode_apply_ch2.clicked.connect(lambda: self.on_apply_mode(2))
        ch_grid.addWidget(self.mode_apply_ch2, 2, 3)
        self.input_toggle_ch2 = QtWidgets.QPushButton('Input Off')
        self.input_toggle_ch2.setCheckable(True)
        self.input_toggle_ch2.clicked.connect(lambda: self.on_toggle_input(2))
        ch_grid.addWidget(self.input_toggle_ch2, 2, 4)
        self.meas_voltage_ch2 = QtWidgets.QLabel('-')
        self.meas_current_ch2 = QtWidgets.QLabel('-')
        f2 = QtGui.QFont(); f2.setPointSize(11); f2.setBold(True)
        self.meas_voltage_ch2.setFont(f2)
        self.meas_current_ch2.setFont(f2)
        ch_grid.addWidget(self.meas_voltage_ch2, 2, 5)
        ch_grid.addWidget(self.meas_current_ch2, 2, 6)
        ch_grid.addWidget(QtWidgets.QLabel('Rise Time (s)'), 2, 7)
        self.rise_time_ch2 = QtWidgets.QLineEdit('0')
        ch_grid.addWidget(self.rise_time_ch2, 2, 8)
        self.ramp_enable_ch2 = QtWidgets.QCheckBox('Enable Ramp')
        ch_grid.addWidget(self.ramp_enable_ch2, 2, 9)

        layout.addLayout(ch_grid)

        # Bottom controls
        bottom = QtWidgets.QHBoxLayout()
        self.read_btn = QtWidgets.QPushButton('Read Now (Both)')
        self.read_btn.clicked.connect(self.read_once)
        bottom.addWidget(self.read_btn)
        layout.addLayout(bottom)

        layout.addWidget(self.status_label)
    def on_toggle_input(self, ch: int):
        if self.dev is None:
            self.status_label.setText('Not connected')
            self._set_input_toggle_ui(ch, False)
            return
        on = self._get_input_toggle_ui(ch)
        try:
            ramp_enabled = self.ramp_enable_ch1.isChecked() if ch == 1 else self.ramp_enable_ch2.isChecked()
            rise_time_edit = self.rise_time_ch1 if ch == 1 else self.rise_time_ch2
            mode_combo = self.mode_combo_ch1 if ch == 1 else self.mode_combo_ch2
            mode = mode_combo.currentText()
            value_edit = self.mode_value_ch1 if ch == 1 else self.mode_value_ch2
            try:
                value = float(value_edit.text())
            except Exception:
                value = 0
            try:
                rise_time = float(rise_time_edit.text())
            except Exception:
                rise_time = 0
            if mode == 'Disable':
                self.dev.set_input(ch, False)
                self._set_input_toggle_ui(ch, False)
                self.status_label.setText(f'Channel {ch} disabled (mode: Disable)')
                return
            self.dev.set_input(ch, on)
            if on and ramp_enabled and rise_time > 0:
                import numpy as np
                import time
                steps = 20
                for v in np.linspace(0, value, steps):
                    self.dev.set_parameter(ch, mode, v)
                    QtWidgets.QApplication.processEvents()
                    time.sleep(rise_time / steps)
                self.dev.set_parameter(ch, mode, value)
            self._set_input_toggle_ui(ch, on)
            self.status_label.setText(f'Channel {ch} {"enabled" if on else "disabled"}')
        except Exception as e:
            self._set_input_toggle_ui(ch, not on)
            self.status_label.setText(f'Failed to toggle input: {e}')

    def on_apply_mode(self, ch: int):
        if self.dev is None:
            self.status_label.setText('Not connected')
            return
        mode_combo = self.mode_combo_ch1 if ch == 1 else self.mode_combo_ch2
        value_edit = self.mode_value_ch1 if ch == 1 else self.mode_value_ch2
        mode = mode_combo.currentText()
        try:
            value = float(value_edit.text())
        except Exception:
            self.status_label.setText('Invalid numeric value')
            return
        try:
            self.dev.set_mode(ch, mode)
            self.dev.set_parameter(ch, mode, value)
            self.status_label.setText(f'Applied {mode} {value} on ch{ch}')
        except Exception as e:
            self.status_label.setText(f'Apply failed: {e}')

    def read_once(self):
        # Read both channels
        for ch in (1, 2):
            try:
                v = self.dev.measure_voltage(ch)
            except Exception:
                v = None
            try:
                i = self.dev.measure_current(ch)
            except Exception:
                i = None
            if ch == 1:
                self.meas_voltage_ch1.setText('N/A' if v is None else f'{v:.6f} V')
                self.meas_current_ch1.setText('N/A' if i is None else f'{i:.6f} A')
            else:
                self.meas_voltage_ch2.setText('N/A' if v is None else f'{v:.6f} V')
                self.meas_current_ch2.setText('N/A' if i is None else f'{i:.6f} A')
        self.status_label.setText('Read complete')

    def get_all_readings(self):
        """Return ([V_ch1, V_ch2], [I_ch1, I_ch2]); used by SupplyRecorder."""
        voltages = []
        currents = []
        for ch in (1, 2):
            try:
                v = self.dev.measure_voltage(ch) if self.dev else None
            except Exception:
                v = None
            try:
                i = self.dev.measure_current(ch) if self.dev else None
            except Exception:
                i = None
            voltages.append(0.0 if v is None else float(v))
            currents.append(0.0 if i is None else float(i))
        return voltages, currents

    def _set_input_toggle_ui(self, ch: int, on: bool):
        btn = self.input_toggle_ch1 if ch == 1 else self.input_toggle_ch2
        btn.setChecked(on)
        btn.setText('Input On' if on else 'Input Off')
        if on:
            btn.setStyleSheet('background-color: #4CAF50; color: white;')
        else:
            btn.setStyleSheet('background-color: #F44336; color: white;')

    def _get_input_toggle_ui(self, ch: int) -> bool:
        return (self.input_toggle_ch1.isChecked() if ch == 1 else self.input_toggle_ch2.isChecked())