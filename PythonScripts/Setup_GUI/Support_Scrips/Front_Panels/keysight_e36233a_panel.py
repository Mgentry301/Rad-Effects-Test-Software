from PyQt5 import QtWidgets, QtCore, QtGui
from Instruments.keysight_e36233a import KeysightE36233A

class KeysightE36233APanel(QtWidgets.QWidget):
    def __init__(self, visa_address, parent=None):
        super().__init__(parent)
        self.supply = KeysightE36233A(visa_address)
        self.supply.open()
        self.name_edit = QtWidgets.QLineEdit(visa_address)
        self.is_on = False
        # Recorder integration
        self.recorder = None
        self.recording = False
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.channel_combo = QtWidgets.QComboBox()
        self.channel_combo.addItems(["1", "2"])
        form.addRow("Channel:", self.channel_combo)
        form.addRow("Instrument Name:", self.name_edit)
        layout.addLayout(form)

        # Voltage/Current set controls
        set_row = QtWidgets.QHBoxLayout()
        self.voltage_edit = QtWidgets.QLineEdit("0.0")
        self.voltage_edit.setMaximumWidth(80)
        self.current_edit = QtWidgets.QLineEdit("0.0")
        self.current_edit.setMaximumWidth(80)
        set_row.addWidget(QtWidgets.QLabel("Set Voltage (V):"))
        set_row.addWidget(self.voltage_edit)
        set_row.addWidget(QtWidgets.QLabel("Set Current (A):"))
        set_row.addWidget(self.current_edit)
        self.set_btn = QtWidgets.QPushButton("Set")
        self.set_btn.setMaximumWidth(80)
        self.set_btn.clicked.connect(self.set_output)
        set_row.addWidget(self.set_btn)
        layout.addLayout(set_row)

        # On/Off button
        self.onoff_btn = QtWidgets.QPushButton("Output OFF")
        self.onoff_btn.setCheckable(True)
        self.onoff_btn.setChecked(False)
        self._update_onoff_btn_color(False)
        self.onoff_btn.setMinimumHeight(40)
        self.onoff_btn.setMinimumWidth(160)
        self.onoff_btn.clicked.connect(self.toggle_output)
        layout.addWidget(self.onoff_btn)

        # Readout labels (large font)
        self.voltage_label = QtWidgets.QLabel("Voltage: --")
        self.voltage_label.setFont(QtGui.QFont("Arial", 24, QtGui.QFont.Bold))
        self.voltage_label.setAlignment(QtCore.Qt.AlignCenter)
        self.current_label = QtWidgets.QLabel("Current: --")
        self.current_label.setFont(QtGui.QFont("Arial", 24, QtGui.QFont.Bold))
        self.current_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.voltage_label)
        layout.addWidget(self.current_label)

        # Read All button
        self.read_all_btn = QtWidgets.QPushButton("Read All")
        self.read_all_btn.setMinimumHeight(32)
        self.read_all_btn.setMaximumWidth(120)
        self.read_all_btn.clicked.connect(self.read_all)
        layout.addWidget(self.read_all_btn)

    def get_all_readings(self):
        """Return ([V1, V2], [I1, I2]) for both channels using fast FETC commands."""
        try:
            voltages = self.supply.fetch_all_voltages()
        except Exception:
            voltages = [0.0, 0.0]
        try:
            currents = self.supply.fetch_all_currents()
        except Exception:
            currents = [0.0, 0.0]
        return voltages, currents

    def start_recording(self):
        if self.recording:
            return
        from supply_recorder import SupplyRecorder
        excel_path = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Supply Reads', '', 'Excel Files (*.xlsx)')[0]
        if not excel_path:
            return
        self.recorder = SupplyRecorder(self.get_all_readings, excel_path, sheet_name="supply reads")
        self.recorder.start()
        self.recording = True
        self.start_rec_btn.setEnabled(False)
        self.stop_rec_btn.setEnabled(True)

    def stop_recording(self):
        if not self.recording or not self.recorder:
            return
        self.recorder.stop()
        self.recording = False
        self.start_rec_btn.setEnabled(True)
        self.stop_rec_btn.setEnabled(False)

    def set_output(self):
        ch = self.channel_combo.currentText()
        v = self.voltage_edit.text().strip()
        c = self.current_edit.text().strip()
        try:
            self.supply.set_voltage(ch, v)
            self.supply.set_current(ch, c)
        except Exception:
            pass

    def toggle_output(self):
        ch = self.channel_combo.currentText()
        if self.onoff_btn.isChecked():
            try:
                self.supply.output_on(ch)
                self.is_on = True
            except Exception:
                self.is_on = False
        else:
            try:
                self.supply.output_off(ch)
                self.is_on = False
            except Exception:
                self.is_on = True
        self._update_onoff_btn_color(self.is_on)

    def _update_onoff_btn_color(self, on):
        if on:
            self.onoff_btn.setText("Output ON")
            self.onoff_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold;')
        else:
            self.onoff_btn.setText("Output OFF")
            self.onoff_btn.setStyleSheet('background-color: #FF5722; color: white; font-weight: bold;')

    def read_all(self):
        ch = self.channel_combo.currentText()
        try:
            v = self.supply.measure_voltage(ch)
            c = self.supply.measure_current(ch)
            self.voltage_label.setText(f"Voltage: {v:.3f} V")
            self.current_label.setText(f"Current: {c:.3f} A")
        except Exception:
            self.voltage_label.setText("Voltage: --")
            self.current_label.setText("Current: --")

    def close(self):
        self.supply.close()
