from PyQt5 import QtWidgets, QtCore
from Instruments.keithley2230 import Keithley2230
from functools import partial



class KeithleyPanel(QtWidgets.QWidget):
    def get_all_readings(self):
        """Return ([V1, V2, V3], [I1, I2, I3]) for all channels using fast FETC commands if available."""
        if self.inst is None:
            return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        try:
            voltages = self.inst.fetch_all_voltages()
        except Exception:
            voltages = [0.0, 0.0, 0.0]
        try:
            currents = self.inst.fetch_all_currents()
        except Exception:
            currents = [0.0, 0.0, 0.0]
        return voltages, currents
    def set_tab_name_callback(self, callback):
        self.name_edit.textChanged.connect(callback)
    """Panel for a Keithley 2230 instrument (uses keithley2230 wrapper)."""
    def __init__(self, resource, parent=None):
        super().__init__(parent)
        self.resource = resource
        self.inst = None
        self.latest_currents = {1: None, 2: None, 3: None}
        # sequence/program control flags/process
        self._sequence_abort_flag = False
        self.program_process = None
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

        # Channel setpoints
        self.vol_edits = {}
        self.iam_edits = {}
        ch_group = QtWidgets.QGroupBox('Channel Setpoints')
        ch_layout = QtWidgets.QGridLayout()
        ch_layout.addWidget(QtWidgets.QLabel('Chan'), 0, 0)
        ch_layout.addWidget(QtWidgets.QLabel('V (V)'), 0, 1)
        ch_layout.addWidget(QtWidgets.QLabel('I (A)'), 0, 2)
        ch_layout.addWidget(QtWidgets.QLabel('Action'), 0, 3)
        for i in (1, 2, 3):
            ch_layout.addWidget(QtWidgets.QLabel(str(i)), i, 0)
            v_edit = QtWidgets.QLineEdit('0')
            i_edit = QtWidgets.QLineEdit('0.03')
            set_btn = QtWidgets.QPushButton('Set')
            set_btn.clicked.connect(partial(self.on_set_channel, i))
            self.vol_edits[i] = v_edit
            self.iam_edits[i] = i_edit
            ch_layout.addWidget(v_edit, i, 1)
            ch_layout.addWidget(i_edit, i, 2)
            ch_layout.addWidget(set_btn, i, 3)
        ch_group.setLayout(ch_layout)
        layout.addWidget(ch_group)

        # Large numeric current displays
        stats_group = QtWidgets.QGroupBox('Live Currents (Read Now)')
        stats_layout = QtWidgets.QGridLayout()
        self.current_value_labels = {}
        for i in (1, 2, 3):
            lbl = QtWidgets.QLabel(f'Ch{i}:')
            val = QtWidgets.QLabel('-')
            val.setMinimumWidth(180)
            val.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            font = val.font()
            font.setPointSize(20)
            font.setBold(True)
            val.setFont(font)
            stats_layout.addWidget(lbl, i - 1, 0)
            stats_layout.addWidget(val, i - 1, 1)
            self.current_value_labels[i] = val
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Bottom controls
        bottom = QtWidgets.QHBoxLayout()
        self.read_btn = QtWidgets.QPushButton('Read Now')
        self.read_btn.clicked.connect(self.read_once)
        self.master_out_btn = QtWidgets.QPushButton('All Off')
        self.master_out_btn.setCheckable(True)
        self.master_out_btn.clicked.connect(self.on_toggle_all_outputs)
        self._update_master_out_btn_color(False)
        bottom.addWidget(self.read_btn)
        bottom.addWidget(self.master_out_btn)
        layout.addLayout(bottom)

        self.status_label = QtWidgets.QLabel('')
        layout.addWidget(self.status_label)

    def close(self):
        try:
            if self.inst is not None:
                self.inst.close()
        except Exception:
            pass

    def on_connect(self):
        res = self.resource_edit.text().strip()
        if not res:
            self.status_label.setText('Enter VISA resource string or serial number')
            return
        try:
            inst = Keithley2230(res)
            inst.open()
            idn = inst.get_identification()
            self.inst = inst
            self.status_label.setText(f'Connected: {idn.strip()}')

            # populate setpoints and read output states
            any_on = False
            for ch in (1, 2, 3):
                try:
                    v = self.inst.get_voltage_setpoint(ch)
                except Exception:
                    v = None
                try:
                    i = self.inst.get_current_setpoint(ch)
                except Exception:
                    i = None
                try:
                    out = self.inst.get_output_state(ch)
                except Exception:
                    out = False

                if v is not None:
                    try:
                        self.vol_edits[ch].setText(str(v))
                    except Exception:
                        pass
                if i is not None:
                    try:
                        self.iam_edits[ch].setText(str(i))
                    except Exception:
                        pass
                if out:
                    any_on = True

            self.master_out_btn.setChecked(any_on)
            self.master_out_btn.setText('All On' if any_on else 'All Off')
            self._update_master_out_btn_color(any_on)

        except Exception as e:
            self.status_label.setText(f'Connect failed: {e}')

    def on_set_channel(self, ch: int):
        if self.inst is None:
            self.status_label.setText('Not connected')
            return
        try:
            V = float(self.vol_edits[ch].text())
            I = float(self.iam_edits[ch].text())
            self.inst.set_voltage(ch, V)
            self.inst.set_current(ch, I)
            self.status_label.setText(f'Set ch{ch} V={V} I={I}')
        except Exception as e:
            self.status_label.setText(f'Set failed: {e}')

    def on_toggle_all_outputs(self):
        if self.inst is None:
            self.status_label.setText('Not connected')
            self.master_out_btn.setChecked(False)
            return
        on = self.master_out_btn.isChecked()
        try:
            if on:
                for ch in (1, 2, 3):
                    try:
                        V = float(self.vol_edits[ch].text())
                        I = float(self.iam_edits[ch].text())
                        self.inst.set_voltage(ch, V)
                        self.inst.set_current(ch, I)
                    except Exception as e_set:
                        self.master_out_btn.setChecked(False)
                        self.master_out_btn.setText('All Off')
                        self.status_label.setText(f'Failed to apply setpoints for ch{ch}: {e_set}')
                        return
                for ch in (1, 2, 3):
                    self.inst.set_output(ch, True)
                self.master_out_btn.setText('All On')
                self._update_master_out_btn_color(True)
                self.status_label.setText('All channels output ON')
            else:
                for ch in (1, 2, 3):
                    try:
                        self.inst.set_output(ch, False)
                    except Exception:
                        pass
                self.master_out_btn.setText('All Off')
                self._update_master_out_btn_color(False)
                self.status_label.setText('All channels output OFF')
        except Exception as e:
            self.master_out_btn.setChecked(not on)
            self.master_out_btn.setText('All On' if not on else 'All Off')
            self._update_master_out_btn_color(not on)
            self.status_label.setText(f'All-output toggle failed: {e}')

    def read_once(self):
        if self.inst is None:
            self.status_label.setText('Not connected')
            return
        try:
            for ch in (1, 2, 3):
                try:
                    v = self.inst.measure_current(ch)
                except Exception:
                    v = None
                self.latest_currents[ch] = v
                lbl = self.current_value_labels.get(ch)
                if lbl is None:
                    continue
                if v is None:
                    txt = 'N/A'
                else:
                    try:
                        txt = f'{v:.6f} A'
                    except Exception:
                        txt = str(v)
                lbl.setText(txt)
            self.status_label.setText('Read complete')
        except Exception as e:
            self.status_label.setText(f'Read failed: {e}')

    def _update_master_out_btn_color(self, on):
        if on:
            self.master_out_btn.setStyleSheet('background-color: #4CAF50; color: white;')
        else:
            self.master_out_btn.setStyleSheet('background-color: #F44336; color: white;')