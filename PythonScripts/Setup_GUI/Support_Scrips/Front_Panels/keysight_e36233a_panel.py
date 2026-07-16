from PyQt5 import QtWidgets, QtCore, QtGui
from Instruments.keysight_e36233a import KeysightE36233A

class KeysightE36233APanel(QtWidgets.QWidget):
    def __init__(self, visa_address, parent=None):
        super().__init__(parent)
        self.supply = KeysightE36233A(visa_address)
        # Opening the VISA resource can fail when the unit isn't connected (or
        # the resource is empty). Don't let that abort the whole app while
        # loading a config; build the panel anyway and mark it disconnected.
        self.connected = False
        try:
            self.supply.open()
            self.connected = True
        except Exception:
            self.connected = False
        # Remember the VISA resource so configs save/restore the correct unit
        # (otherwise two E36233A supplies collapse onto the same instrument).
        self.resource = visa_address
        self.name_edit = QtWidgets.QLineEdit(visa_address)
        # User-editable display names for the two physical channels. The actual
        # SCPI channel number (1 or 2) is preserved via the combo item data.
        self.channel_names = ["1", "2"]
        # Independent set-point storage for each physical channel so switching
        # the channel selector recalls that channel's own voltage/current.
        self.channel_voltages = ["0.0", "0.0"]
        self.channel_currents = ["0.0", "0.0"]
        self._active_channel_index = 0
        self.is_on = False
        # Recorder integration
        self.recorder = None
        self.recording = False
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.channel_combo = QtWidgets.QComboBox()
        self._rebuild_channel_combo()
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        form.addRow("Channel:", self.channel_combo)

        # Editable per-channel names
        self.ch1_name_edit = QtWidgets.QLineEdit(self.channel_names[0])
        self.ch2_name_edit = QtWidgets.QLineEdit(self.channel_names[1])
        self.ch1_name_edit.setPlaceholderText("Channel 1 name")
        self.ch2_name_edit.setPlaceholderText("Channel 2 name")
        self.ch1_name_edit.textChanged.connect(lambda t: self._set_channel_name(0, t))
        self.ch2_name_edit.textChanged.connect(lambda t: self._set_channel_name(1, t))
        form.addRow("Channel 1 Name:", self.ch1_name_edit)
        form.addRow("Channel 2 Name:", self.ch2_name_edit)

        form.addRow("Instrument Name:", self.name_edit)
        layout.addLayout(form)

        # Voltage/Current set controls (values are per-channel, recalled on switch)
        set_row = QtWidgets.QHBoxLayout()
        self.voltage_edit = QtWidgets.QLineEdit(self.channel_voltages[0])
        self.voltage_edit.setMaximumWidth(80)
        self.current_edit = QtWidgets.QLineEdit(self.channel_currents[0])
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

    def _rebuild_channel_combo(self):
        """Populate the channel combo with display names, keeping channel data."""
        idx = self.channel_combo.currentIndex()
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()
        for i, name in enumerate(self.channel_names):
            label = (name or "").strip() or str(i + 1)
            self.channel_combo.addItem(label, str(i + 1))
        if 0 <= idx < self.channel_combo.count():
            self.channel_combo.setCurrentIndex(idx)
        self.channel_combo.blockSignals(False)

    def _set_channel_name(self, index, text):
        self.channel_names[index] = text
        self._rebuild_channel_combo()

    def sync_active_channel(self):
        """Persist the visible set-point fields into the active channel's store."""
        idx = self._active_channel_index
        if 0 <= idx < len(self.channel_voltages):
            self.channel_voltages[idx] = self.voltage_edit.text()
            self.channel_currents[idx] = self.current_edit.text()

    def _on_channel_changed(self, _idx=None):
        """Save fields for the previous channel and recall the new channel's values."""
        prev = self._active_channel_index
        if 0 <= prev < len(self.channel_voltages):
            self.channel_voltages[prev] = self.voltage_edit.text()
            self.channel_currents[prev] = self.current_edit.text()
        new = self.channel_combo.currentIndex()
        if 0 <= new < len(self.channel_voltages):
            self._active_channel_index = new
            self.voltage_edit.blockSignals(True)
            self.current_edit.blockSignals(True)
            self.voltage_edit.setText(self.channel_voltages[new])
            self.current_edit.setText(self.channel_currents[new])
            self.voltage_edit.blockSignals(False)
            self.current_edit.blockSignals(False)

    def apply_channel_setpoints(self):
        """Refresh the visible fields from the active channel's stored values."""
        idx = self._active_channel_index
        if 0 <= idx < len(self.channel_voltages):
            self.voltage_edit.setText(self.channel_voltages[idx])
            self.current_edit.setText(self.channel_currents[idx])

    @property
    def channel_labels(self):
        """Display name for each physical channel, falling back to its number."""
        return [(n or "").strip() or str(i + 1) for i, n in enumerate(self.channel_names)]

    def _current_channel(self):
        """Return the real SCPI channel number for the selected combo item."""
        data = self.channel_combo.currentData()
        return data if data is not None else self.channel_combo.currentText()

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
        ch = self._current_channel()
        v = self.voltage_edit.text().strip()
        c = self.current_edit.text().strip()
        idx = self._active_channel_index
        if 0 <= idx < len(self.channel_voltages):
            self.channel_voltages[idx] = self.voltage_edit.text()
            self.channel_currents[idx] = self.current_edit.text()
        try:
            self.supply.set_voltage(ch, v)
            self.supply.set_current(ch, c)
        except Exception:
            pass

    def toggle_output(self):
        ch = self._current_channel()
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
        ch = self._current_channel()
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
