from PyQt5 import QtWidgets, QtCore, QtGui
import os
import json
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
        # Cache of baseline voltages from the loaded JSON config, per channel
        self._baseline_voltages = None
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
        self.output_btns = {}
        ch_group = QtWidgets.QGroupBox('Channel Setpoints')
        ch_layout = QtWidgets.QGridLayout()
        ch_layout.addWidget(QtWidgets.QLabel('Chan'), 0, 0)
        ch_layout.addWidget(QtWidgets.QLabel('Name'), 0, 1)
        ch_layout.addWidget(QtWidgets.QLabel('V (V)'), 0, 2)
        ch_layout.addWidget(QtWidgets.QLabel('I (A)'), 0, 3)
        ch_layout.addWidget(QtWidgets.QLabel('Action'), 0, 4)
        ch_layout.addWidget(QtWidgets.QLabel('Output'), 0, 5)
        self.ch_name_edits = {}
        for i in (1, 2, 3):
            ch_layout.addWidget(QtWidgets.QLabel(str(i)), i, 0)
            name_edit = QtWidgets.QLineEdit(f'CH{i}')
            name_edit.setMaximumWidth(120)
            v_edit = QtWidgets.QLineEdit('0')
            i_edit = QtWidgets.QLineEdit('0.03')
            set_btn = QtWidgets.QPushButton('Set')
            set_btn.clicked.connect(partial(self.on_set_channel, i))
            output_btn = QtWidgets.QPushButton('Output Off')
            output_btn.setCheckable(True)
            output_btn.setChecked(False)
            output_btn.clicked.connect(partial(self.on_toggle_channel_output, i))
            self.ch_name_edits[i] = name_edit
            self.vol_edits[i] = v_edit
            self.iam_edits[i] = i_edit
            self.output_btns[i] = output_btn
            ch_layout.addWidget(name_edit, i, 1)
            ch_layout.addWidget(v_edit, i, 2)
            ch_layout.addWidget(i_edit, i, 3)
            ch_layout.addWidget(set_btn, i, 4)
            ch_layout.addWidget(output_btn, i, 5)
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

        # Voltage offset utilities
        offset_row = QtWidgets.QHBoxLayout()
        offset_row.addWidget(QtWidgets.QLabel('Offset %:'))
        self.offset_percent_edit = QtWidgets.QLineEdit('10')
        self.offset_percent_edit.setMaximumWidth(80)
        # allow negative and decimal percentages
        try:
            validator = QtGui.QDoubleValidator(-1000.0, 1000.0, 3, self)
            validator.setNotation(QtGui.QDoubleValidator.StandardNotation)
            self.offset_percent_edit.setValidator(validator)
        except Exception:
            pass
        offset_row.addWidget(self.offset_percent_edit)
        self.apply_offset_btn = QtWidgets.QPushButton('Apply Offset')
        self.apply_offset_btn.setToolTip('Multiply each channel voltage by (1 + percent/100). Default is +10%.')
        self.apply_offset_btn.clicked.connect(self.on_apply_offset)
        offset_row.addWidget(self.apply_offset_btn)
        # Reset to baseline button
        self.reset_baseline_btn = QtWidgets.QPushButton('Reset to Baseline')
        self.reset_baseline_btn.setToolTip('Restore channel voltages to baseline from loaded config (non-compounding).')
        self.reset_baseline_btn.clicked.connect(self.on_reset_to_baseline)
        offset_row.addWidget(self.reset_baseline_btn)
        layout.addLayout(offset_row)

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

    def on_apply_offset(self):
        """Apply a percentage offset to channel voltage setpoints based on JSON baseline.
        Uses baseline voltages from the last loaded config (if available) so offsets are
        not compounded from current UI values. Falls back to current UI if no baseline.
        """
        # Parse percentage
        try:
            pct = float(self.offset_percent_edit.text())
        except Exception:
            self.status_label.setText('Invalid offset percentage')
            return

        factor = 1.0 + (pct / 100.0)
        # Ensure baseline is available
        if self._baseline_voltages is None:
            self._load_baseline_from_config()
        # Fallback to current UI as baseline if none found
        if self._baseline_voltages is None:
            self._baseline_voltages = {}
            for ch in (1, 2, 3):
                try:
                    self._baseline_voltages[ch] = float(self.vol_edits[ch].text())
                except Exception:
                    self._baseline_voltages[ch] = 0.0

        new_values = {}
        for ch in (1, 2, 3):
            base_v = float(self._baseline_voltages.get(ch, 0.0))
            new_v = base_v * factor
            new_values[ch] = new_v
            # Update the UI field
            try:
                self.vol_edits[ch].setText(f'{new_v:.6f}')
            except Exception:
                pass
        # If connected, program the new voltages
        if self.inst is not None:
            for ch, new_v in new_values.items():
                try:
                    self.inst.set_voltage(ch, new_v)
                except Exception:
                    # keep going for other channels
                    pass
            conn_note = ''
        else:
            conn_note = ' (setpoints only; not connected)'

        sign = '+' if pct >= 0 else ''
        self.status_label.setText(f'Applied {sign}{pct:.2f}% voltage offset{conn_note}')

    def on_reset_to_baseline(self):
        """Reset UI and instrument voltages to the baseline values from config.
        If baseline isn't loaded yet, attempts to load it. If still not found,
        leaves UI as-is and informs the user.
        """
        if self._baseline_voltages is None:
            self._load_baseline_from_config()
        if self._baseline_voltages is None:
            self.status_label.setText('No baseline found (load a config first)')
            return
        # Update UI fields
        for ch in (1, 2, 3):
            try:
                v = float(self._baseline_voltages.get(ch, 0.0))
            except Exception:
                v = 0.0
            try:
                self.vol_edits[ch].setText(f'{v:.6f}')
            except Exception:
                pass
        # Program instrument if connected
        if self.inst is not None:
            for ch in (1, 2, 3):
                try:
                    v = float(self._baseline_voltages.get(ch, 0.0))
                    self.inst.set_voltage(ch, v)
                except Exception:
                    pass
            self.status_label.setText('Voltages reset to baseline')
        else:
            self.status_label.setText('Voltages reset to baseline (not connected)')

    def _load_baseline_from_config(self):
        """Load baseline voltages from last loaded config JSON in MainWindow.
        Attempts to match by instrument name first, then resource. Sets _baseline_voltages.
        """
        # Get the last loaded config path from the main window
        try:
            main_win = self.window()
        except Exception:
            main_win = None
        cfg_path = None
        try:
            cfg_path = getattr(main_win, '_last_loaded_config_path', None)
        except Exception:
            cfg_path = None
        if not cfg_path or not isinstance(cfg_path, str) or not os.path.exists(cfg_path):
            return
        # Identify this instrument
        try:
            name_text = self.name_edit.text().strip()
        except Exception:
            name_text = None
        try:
            res_text = self.resource_edit.text().strip()
        except Exception:
            res_text = None

        try:
            with open(cfg_path, 'r') as f:
                content = json.load(f)
        except Exception:
            return

        instruments = []
        if isinstance(content, dict):
            instruments = content.get('instruments', []) or []
        elif isinstance(content, list):
            instruments = content

        # Find matching Keithley instrument
        k_items = [it for it in instruments if isinstance(it, dict) and str(it.get('type', '')).strip().lower() == 'keithley 2230']
        chosen = None
        if name_text:
            for it in k_items:
                try:
                    if str(it.get('name', '')).strip().lower() == name_text.lower():
                        chosen = it
                        break
                except Exception:
                    pass
        if chosen is None and res_text:
            for it in k_items:
                try:
                    if str(it.get('resource', '')).strip() == res_text:
                        chosen = it
                        break
                except Exception:
                    pass
        if chosen is None and len(k_items) == 1:
            chosen = k_items[0]
        if chosen is None:
            return

        channels = chosen.get('channels', {}) or {}
        baseline = {}
        for key in ('1', '2', '3'):
            try:
                v = channels.get(key, {}).get('voltage', 0.0)
                baseline[int(key)] = float(v)
            except Exception:
                baseline[int(key)] = 0.0
            # Accept baseline even if zeros; some configs may set 0V intentionally
            self._baseline_voltages = baseline

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
            for ch in (1, 2, 3):
                self.output_btns[ch].setChecked(False)
                self.output_btns[ch].setText('Output Off')
                self.output_btns[ch].setStyleSheet('background-color: #F44336; color: white;')
            return
        on = self.master_out_btn.isChecked()
        for ch in (1, 2, 3):
            try:
                if on:
                    V = float(self.vol_edits[ch].text())
                    I = float(self.iam_edits[ch].text())
                    self.inst.set_voltage(ch, V)
                    self.inst.set_current(ch, I)
                    self.inst.set_output(ch, True)
                    self.output_btns[ch].setChecked(True)
                    self.output_btns[ch].setText('Output On')
                    self.output_btns[ch].setStyleSheet('background-color: #4CAF50; color: white;')
                else:
                    self.inst.set_output(ch, False)
                    self.output_btns[ch].setChecked(False)
                    self.output_btns[ch].setText('Output Off')
                    self.output_btns[ch].setStyleSheet('background-color: #F44336; color: white;')
            except Exception:
                pass
        self.master_out_btn.setText('All On' if on else 'All Off')
        self._update_master_out_btn_color(on)
        self.status_label.setText('All channels output ON' if on else 'All channels output OFF')
    def on_toggle_channel_output(self, ch: int):
        if self.inst is None:
            self.status_label.setText('Not connected')
            self.output_btns[ch].setChecked(False)
            self.output_btns[ch].setText('Output Off')
            self.output_btns[ch].setStyleSheet('background-color: #F44336; color: white;')
            return
        on = self.output_btns[ch].isChecked()
        try:
            if on:
                V = float(self.vol_edits[ch].text())
                I = float(self.iam_edits[ch].text())
                self.inst.set_voltage(ch, V)
                self.inst.set_current(ch, I)
                self.inst.set_output(ch, True)
                self.output_btns[ch].setText('Output On')
                self.output_btns[ch].setStyleSheet('background-color: #4CAF50; color: white;')
                self.status_label.setText(f'Channel {ch} output ON')
                # Set other channels' voltage and current to zero, but do not toggle their output off
                for other_ch in (1, 2, 3):
                    if other_ch != ch and not self.output_btns[other_ch].isChecked():
                        self.inst.set_voltage(other_ch, 0.0)
                        self.inst.set_current(other_ch, 0.0)
            else:
                # Set voltage and current to zero, but keep output ON
                self.inst.set_voltage(ch, 0.0)
                self.inst.set_current(ch, 0.0)
                self.output_btns[ch].setText('Output Off')
                self.output_btns[ch].setStyleSheet('background-color: #F44336; color: white;')
                self.status_label.setText(f'Channel {ch} output ON (zeroed)')
        except Exception as e:
            self.output_btns[ch].setChecked(not on)
            self.output_btns[ch].setText('Output On' if not on else 'Output Off')
            self.output_btns[ch].setStyleSheet('background-color: #4CAF50; color: white;' if not on else 'background-color: #F44336; color: white;')
            self.status_label.setText(f'Failed to set output for channel {ch}: {e}')

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