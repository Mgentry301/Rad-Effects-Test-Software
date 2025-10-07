from PyQt5 import QtWidgets, QtCore
from Instruments.keysight_el import KeysightEL


class KeysightELPanel(QtWidgets.QWidget):
    def set_tab_name_callback(self, callback):
        self.name_edit.textChanged.connect(callback)
    """Panel for Keysight EL34243A-style dual-input electronic load."""
    def __init__(self, resource, parent=None):
        super().__init__(parent)
        self.resource = resource
        self.dev = None  # KeysightEL instance
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

        # Channel selector (EL34243A has two inputs)
        ch_row = QtWidgets.QHBoxLayout()
        ch_row.addWidget(QtWidgets.QLabel('Channel:'))
        self.ch_select = QtWidgets.QComboBox()
        self.ch_select.addItems(['1', '2'])
        ch_row.addWidget(self.ch_select)
        # Add enable/disable checkboxes for each channel
        self.ch_enabled = {1: QtWidgets.QCheckBox('Enable Ch 1'), 2: QtWidgets.QCheckBox('Enable Ch 2')}
        self.ch_enabled[1].setChecked(True)
        self.ch_enabled[2].setChecked(True)
        ch_row.addWidget(self.ch_enabled[1])
        ch_row.addWidget(self.ch_enabled[2])
        self.ch_enabled[1].stateChanged.connect(lambda _: self._update_input_toggle_color(self.ch_enabled[1].isChecked()))
        self.ch_enabled[2].stateChanged.connect(lambda _: self._update_input_toggle_color(self.ch_enabled[2].isChecked()))
        layout.addLayout(ch_row)

        # On/Off control
        inp_row = QtWidgets.QHBoxLayout()
        self.input_toggle = QtWidgets.QPushButton('Input Off')
        self.input_toggle.setCheckable(True)
        self.input_toggle.clicked.connect(self.on_toggle_input)
        self._update_input_toggle_color(False)
        inp_row.addWidget(self.input_toggle)
        layout.addLayout(inp_row)

        # Mode selection and parameter
        mode_group = QtWidgets.QGroupBox('Mode and Parameter')
        mlay = QtWidgets.QHBoxLayout()
        mlay.addWidget(QtWidgets.QLabel('Mode:'))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(['CC', 'CV', 'CR', 'CP'])
        mlay.addWidget(self.mode_combo)
        mlay.addWidget(QtWidgets.QLabel('Value:'))
        self.mode_value = QtWidgets.QLineEdit('0.1')
        mlay.addWidget(self.mode_value)
        self.mode_apply = QtWidgets.QPushButton('Apply')
        self.mode_apply.clicked.connect(self.on_apply_mode)
        mlay.addWidget(self.mode_apply)
        mode_group.setLayout(mlay)
        layout.addWidget(mode_group)

        # Readouts
        stats_group = QtWidgets.QGroupBox('Measurements (Read Now)')
        stats_layout = QtWidgets.QGridLayout()
        self.meas_voltage = QtWidgets.QLabel('-')
        self.meas_current = QtWidgets.QLabel('-')
        font = self.meas_voltage.font()
        font.setPointSize(16)
        font.setBold(True)
        self.meas_voltage.setFont(font)
        self.meas_current.setFont(font)
        stats_layout.addWidget(QtWidgets.QLabel('Voltage:'), 0, 0)
        stats_layout.addWidget(self.meas_voltage, 0, 1)
        stats_layout.addWidget(QtWidgets.QLabel('Current:'), 1, 0)
        stats_layout.addWidget(self.meas_current, 1, 1)
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
            dev = KeysightEL(res)
            dev.open()
            idn = dev.get_identification()
            self.dev = dev
            self.status_label.setText(f'Connected: {idn.strip()}')
            # try to read input state for selected channel
            ch = int(self.ch_select.currentText())
            try:
                on = self.dev.get_input_state(ch)
                if not self.ch_enabled[ch].isChecked():
                    on = False
                self.input_toggle.setChecked(on)
                self.input_toggle.setText('Input On' if on else 'Input Off')
                self._update_input_toggle_color(on)
                self._update_input_toggle()
            except Exception:
                pass
        except Exception as e:
            self.status_label.setText(f'Connect failed: {e}')

    def on_toggle_input(self):
        if self.dev is None:
            self.status_label.setText('Not connected')
            self.input_toggle.setChecked(False)
            return
        ch = int(self.ch_select.currentText())
        if not self.ch_enabled[ch].isChecked():
            self.input_toggle.setChecked(False)
            self.input_toggle.setText('Input Off')
            self.status_label.setText(f'Channel {ch} is disabled')
            return
        on = self.input_toggle.isChecked()
        try:
            self.dev.set_input(ch, on)
            self.input_toggle.setText('Input On' if on else 'Input Off')
            self._update_input_toggle_color(on)
            self.status_label.setText(f'Channel {ch} {"enabled" if on else "disabled"}')
        except Exception as e:
            self.input_toggle.setChecked(not on)
            self._update_input_toggle_color(not on)
            self.status_label.setText(f'Failed to toggle input: {e}')

    def on_apply_mode(self):
        if self.dev is None:
            self.status_label.setText('Not connected')
            return
        ch = int(self.ch_select.currentText())
        mode = self.mode_combo.currentText()
        try:
            value = float(self.mode_value.text())
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
        if self.dev is None:
            self.status_label.setText('Not connected')
            return
        ch = int(self.ch_select.currentText())
        try:
            v = self.dev.measure_voltage(ch)
        except Exception:
            v = None
        try:
            i = self.dev.measure_current(ch)
        except Exception:
            i = None
        self.meas_voltage.setText('N/A' if v is None else f'{v:.6f} V')
        self.meas_current.setText('N/A' if i is None else f'{i:.6f} A')
        self.status_label.setText('Read complete')

    def _update_input_toggle_color(self, on):
        if on:
            self.input_toggle.setStyleSheet('background-color: #4CAF50; color: white;')
        else:
            self.input_toggle.setStyleSheet('background-color: #F44336; color: white;')