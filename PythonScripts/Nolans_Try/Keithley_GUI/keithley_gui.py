"""
Multi-instrument GUI: Keithley 2230 panels + Keysight EL34243A panel.
- Add instruments by typing SN or full VISA resource.
- Choose instrument type on add (Keithley or Keysight).
- Scan VISA to detect connected devices.
- Each instrument gets its own tab and independent controls.

Notes:
- Keysight EL34243A wrapper uses common SCPI patterns for electronic loads
  (INP ON/OFF, FUNC:MODE <CURR|VOLT|RES>, CURR/VOLT/RES <value>, MEAS:CURR?).
  If your model uses different commands, the wrapper will report errors and
  can be adjusted easily.
"""
import sys
import os
import json
import tempfile
import datetime
from functools import partial

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QPalette
from PyQt5.QtCore import Qt
import pyvisa

from Instruments.keithley2230 import Keithley2230
from Instruments.keysight_el import KeysightEL
from Instruments.hittite_siggen import HittiteSigGen
from GUI_Wrappers.power_sequence_builder import PowerSequenceBuilder


class KeithleyPanel(QtWidgets.QWidget):
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


class KeysightPanel(QtWidgets.QWidget):
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
        
class MainWindow(QtWidgets.QMainWindow):
    # helper to format timestamps for logs
    def _ts(self):
        return datetime.datetime.now().strftime('%H:%M:%S')

    def _log(self, msg: str):
        try:
            txt = f'[{self._ts()}] {msg}'
            if hasattr(self, 'test_log'):
                self.test_log.appendPlainText(txt)
            else:
                # fallback to status bar
                self.statusBar().showMessage(msg, 4000)
        except Exception:
            pass

    def on_abort_clicked(self):
        # Set abort flag; running _run_power_sequence checks this flag and stops.
        self._sequence_abort_flag = True
        self._log('Abort requested')
        # Terminate any running program process
        try:
            if getattr(self, 'program_process', None) is not None:
                proc = self.program_process
                try:
                    proc.kill()
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                self.program_process = None
                self._log('Program process terminated')
        except Exception:
            pass

    def _auto_turn_off_panel(self, panel):
        """Safely turn off outputs/inputs for a single panel after it's added.
        Used to ensure newly-added instruments don't power outputs unexpectedly.
        """
        try:
            if isinstance(panel, KeithleyPanel):
                if getattr(panel, 'inst', None):
                    try:
                        for ch in (1, 2, 3):
                            panel.inst.set_output(ch, False)
                    except Exception:
                        pass
                try:
                    panel.master_out_btn.setChecked(False)
                    panel.master_out_btn.setText('All Off')
                except Exception:
                    pass
            elif isinstance(panel, HittiteSigGenPanel):
                if getattr(panel, 'dev', None):
                    try:
                        panel.dev.set_output(False)
                    except Exception:
                        pass
                try:
                    panel.output_btn.setChecked(False)
                    panel.output_btn.setText('Output Off')
                except Exception:
                    pass
            elif isinstance(panel, KeysightPanel):
                if getattr(panel, 'dev', None):
                    try:
                        for ch in (1, 2):
                            if hasattr(panel, 'ch_enabled') and not panel.ch_enabled[ch].isChecked():
                                continue
                            try:
                                panel.dev.set_input(ch, False)
                            except Exception:
                                pass
                    except Exception:
                        pass
                try:
                    panel.input_toggle.setChecked(False)
                    panel.input_toggle.setText('Input Off')
                except Exception:
                    pass
        except Exception:
            pass
    def sequence_power_on(self):
        order = self.seq_order_edit.text().strip()
        if not order:
            self.statusBar().showMessage('No sequence order specified', 4000)
            return
        names = [n.strip().lower() for n in order.split(',') if n.strip()]
        for name in names:
            for i in range(self.tabs.count()):
                widget = self.tabs.widget(i)
                tab_name = self.tabs.tabText(i).lower()
                if name in tab_name:
                    if isinstance(widget, KeithleyPanel):
                        if widget.inst:
                            for ch in (1, 2, 3):
                                try:
                                    V = float(widget.vol_edits[ch].text())
                                    I = float(widget.iam_edits[ch].text())
                                    widget.inst.set_voltage(ch, V)
                                    widget.inst.set_current(ch, I)
                                    widget.inst.set_output(ch, True)
                                except Exception:
                                    pass
                            widget.master_out_btn.setChecked(True)
                            widget.master_out_btn.setText('All On')
                    elif isinstance(widget, HittiteSigGenPanel):
                        if widget.dev:
                            try:
                                widget.dev.set_output(True)
                                widget.output_btn.setChecked(True)
                                widget.output_btn.setText('Output On')
                                widget.status_label.setText('Output ON')
                            except Exception as e:
                                widget.status_label.setText(f'Failed to set output: {e}')
                    elif isinstance(widget, KeysightPanel):
                        if widget.dev:
                            for ch in (1, 2):
                                if hasattr(widget, 'ch_enabled') and not widget.ch_enabled[ch].isChecked():
                                    continue
                                try:
                                    mode = widget.mode_combo.currentText()
                                    value = float(widget.mode_value.text())
                                    widget.dev.set_mode(ch, mode)
                                    widget.dev.set_parameter(ch, mode, value)
                                    widget.dev.set_input(ch, True)
                                except Exception:
                                    pass
                            widget.input_toggle.setChecked(True)
                            widget.input_toggle.setText('Input On')
        self.statusBar().showMessage('Sequence power on complete', 4000)

    def sequence_power_off(self):
        order = self.seq_order_edit.text().strip()
        if not order:
            self.statusBar().showMessage('No sequence order specified', 4000)
            return
        names = [n.strip().lower() for n in order.split(',') if n.strip()]
        for name in names:
            for i in range(self.tabs.count()):
                widget = self.tabs.widget(i)
                tab_name = self.tabs.tabText(i).lower()
                if name in tab_name:
                    if isinstance(widget, KeithleyPanel):
                        if widget.inst:
                            for ch in (1, 2, 3):
                                try:
                                    widget.inst.set_output(ch, False)
                                except Exception:
                                    pass
                            widget.master_out_btn.setChecked(False)
                            widget.master_out_btn.setText('All Off')
                    elif isinstance(widget, HittiteSigGenPanel):
                        if widget.dev:
                            try:
                                widget.dev.set_output(False)
                                widget.output_btn.setChecked(False)
                                widget.output_btn.setText('Output Off')
                                widget.status_label.setText('Output OFF')
                            except Exception as e:
                                widget.status_label.setText(f'Failed to set output: {e}')
                    elif isinstance(widget, KeysightPanel):
                        if widget.dev:
                            for ch in (1, 2):
                                if hasattr(widget, 'ch_enabled') and not widget.ch_enabled[ch].isChecked():
                                    continue
                                try:
                                    widget.dev.set_input(ch, False)
                                except Exception:
                                    pass
                            widget.input_toggle.setChecked(False)
                            widget.input_toggle.setText('Input Off')
        self.statusBar().showMessage('Sequence power off complete', 4000)

    def reset_part(self):
        try:
            delay = float(self.reset_delay_edit.text())
        except Exception:
            delay = 2.0
        # clear any previous abort request and power off
        try:
            self._sequence_abort_flag = False
        except Exception:
            pass
        self._log(f'Reset requested: powering off, will power on in {delay} seconds')
        self.power_off_all()

        def _do_power_on():
            # If a power-up sequence is configured and enabled, use it; otherwise power all
            use_seq = False
            seq = []
            try:
                if hasattr(self, 'power_seq_builder'):
                    use_seq = self.power_seq_builder.use_sequence()
                    seq = self.power_seq_builder.get_sequence()
            except Exception:
                pass
            if use_seq and seq:
                self._log('Using configured power-up sequence for reset')
                if hasattr(self, 'test_power_toggle_btn'):
                    self.test_power_toggle_btn.setChecked(True)
                    self._update_test_power_toggle_btn(True)
                # run sequence (no further action required after)
                self._run_power_sequence()
            else:
                self._log('No sequence configured; powering all instruments ON')
                self.power_on_all()

        QtCore.QTimer.singleShot(int(delay * 1000), _do_power_on)
        self.statusBar().showMessage(f'Reset part: powered off, will power on in {delay} seconds', 4000)
    def __init__(self):
        super().__init__()
        # runtime control state for sequencing/program runs
        self._sequence_abort_flag = False
        self.program_process = None
        self._program_tempfile = None
        self.setWindowTitle("Instrument Controller - Multiple Instruments")
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)

        # Top-level tabs: Setup and Test
        self.top_tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.top_tabs)

        # --- Setup Tab ---
        setup_widget = QtWidgets.QWidget()
        setup_layout = QtWidgets.QVBoxLayout(setup_widget)

        # Configs folder
        self.configs_dir = os.path.join(os.path.dirname(__file__), 'configs')
        os.makedirs(self.configs_dir, exist_ok=True)

        # Top: Instrument type selector, Scan VISA, detected devices, Save/Load Config
        top_row = QtWidgets.QHBoxLayout()
        self.scan_btn = QtWidgets.QPushButton('Scan VISA')
        self.scan_btn.clicked.connect(self.on_scan_instruments)
        self.detected_combo = QtWidgets.QComboBox()
        self.detected_combo.setMinimumWidth(350)
        self.add_selected_btn = QtWidgets.QPushButton('Add Selected')
        self.add_selected_btn.clicked.connect(self.on_add_selected_instrument)
        self.save_btn = QtWidgets.QPushButton('Save Config')
        self.save_btn.clicked.connect(self.save_config_dialog)
        self.load_combo = QtWidgets.QComboBox()
        self.load_combo.setMinimumWidth(200)
        self.load_btn = QtWidgets.QPushButton('Load Config')
        self.load_btn.clicked.connect(self.load_config_dialog)
        self.refresh_configs_list()

        top_row.addWidget(self.scan_btn)
        top_row.addWidget(self.detected_combo)
        top_row.addWidget(self.add_selected_btn)
        top_row.addWidget(self.save_btn)
        top_row.addWidget(self.load_combo)
        top_row.addWidget(self.load_btn)
        setup_layout.addLayout(top_row)

        # Tabs for instruments
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        setup_layout.addWidget(self.tabs)

        self.statusBar().showMessage('Ready')

        self.top_tabs.addTab(setup_widget, "Setup")

        # --- Test Tab ---
        test_widget = QtWidgets.QWidget()
        test_layout = QtWidgets.QVBoxLayout(test_widget)

        # Power controls
        power_row = QtWidgets.QHBoxLayout()
        self.test_power_toggle_btn = QtWidgets.QPushButton('Power Off All')
        self.test_power_toggle_btn.setCheckable(True)
        self.test_power_toggle_btn.setChecked(False)
        self.test_power_toggle_btn.clicked.connect(self.on_test_power_toggle)
        self._update_test_power_toggle_btn(False)
        power_row.addWidget(self.test_power_toggle_btn)
        test_layout.addLayout(power_row)

        # Power sequence builder (wrapper)
        # sequence builder should only list instruments that currently have active tabs
        self.power_seq_builder = PowerSequenceBuilder(
            parent=self,
            get_instruments_callback=lambda: [self.tabs.tabText(i) for i in range(self.tabs.count())]
        )
        test_layout.addWidget(self.power_seq_builder)

        # Abort / Cancel button and run log
        abort_row = QtWidgets.QHBoxLayout()
        self.abort_btn = QtWidgets.QPushButton('Abort')
        self.abort_btn.setStyleSheet('background-color: #FF5722; color: white;')
        self.abort_btn.clicked.connect(self.on_abort_clicked)
        abort_row.addWidget(self.abort_btn)
        test_layout.addLayout(abort_row)

        # Test run log (read-only)
        self.test_log = QtWidgets.QPlainTextEdit()
        self.test_log.setReadOnly(True)
        self.test_log.setMaximumHeight(200)
        test_layout.addWidget(QtWidgets.QLabel('Run Log:'))
        test_layout.addWidget(self.test_log)

        self.top_tabs.addTab(test_widget, "Sequencing")

        # Ensure sequence builder combo is populated with any existing tabs
        try:
            if hasattr(self, 'power_seq_builder'):
                self.power_seq_builder.refresh_instr_combo()
        except Exception:
            pass

        # --- Programming Tab ---
        prog_widget = QtWidgets.QWidget()
        prog_layout = QtWidgets.QVBoxLayout(prog_widget)

        prog_layout.addWidget(QtWidgets.QLabel('Programming Block (Python code)'))
        self.program_code_edit = QtWidgets.QPlainTextEdit()
        self.program_code_edit.setPlaceholderText('# Write Python code here.\n# Available variables: main (MainWindow), tabs (QTabWidget), panels (dict name->widget)')
        prog_layout.addWidget(self.program_code_edit)

        prog_btn_row = QtWidgets.QHBoxLayout()
        self.run_program_btn = QtWidgets.QPushButton('Run Program')
        self.run_program_btn.clicked.connect(lambda: self.run_program_code())
        prog_btn_row.addWidget(self.run_program_btn)
        # Abort Program button in the Programming tab
        self.abort_program_btn = QtWidgets.QPushButton('Abort Program')
        self.abort_program_btn.setStyleSheet('background-color: #FF5722; color: white;')
        self.abort_program_btn.setEnabled(False)
        self.abort_program_btn.clicked.connect(self.on_program_abort)
        prog_btn_row.addWidget(self.abort_program_btn)
        prog_layout.addLayout(prog_btn_row)

        self.top_tabs.addTab(prog_widget, 'Programming')

        # --- Test Tab ---
        test2_widget = QtWidgets.QWidget()
        test2_layout = QtWidgets.QVBoxLayout(test2_widget)

        # Power On/Off toggle (syncs with Sequencing tab power button)
        tpower_row = QtWidgets.QHBoxLayout()
        self.test_tab_power_btn = QtWidgets.QPushButton('Power Off All')
        self.test_tab_power_btn.setCheckable(True)
        self.test_tab_power_btn.setChecked(False)
        self.test_tab_power_btn.clicked.connect(self.on_test_power_toggle)
        # initialize color
        if hasattr(self, '_update_test_power_toggle_btn'):
            self._update_test_power_toggle_btn(False)
        tpower_row.addWidget(self.test_tab_power_btn)
        test2_layout.addLayout(tpower_row)

        # Program / Reprogram button
        prog_row = QtWidgets.QHBoxLayout()
        self.program_now_btn = QtWidgets.QPushButton('Program / Reprogram')
        self.program_now_btn.clicked.connect(lambda: self.run_program_code())
        prog_row.addWidget(self.program_now_btn)
        test2_layout.addLayout(prog_row)

        # Reset controls
        reset_row = QtWidgets.QHBoxLayout()
        reset_row.addWidget(QtWidgets.QLabel('Reset delay (s):'))
        self.reset_delay_edit = QtWidgets.QLineEdit('2.0')
        self.reset_delay_edit.setMaximumWidth(80)
        reset_row.addWidget(self.reset_delay_edit)
        self.reset_btn = QtWidgets.QPushButton('Reset Device')
        self.reset_btn.clicked.connect(self.reset_part)
        reset_row.addWidget(self.reset_btn)
        test2_layout.addLayout(reset_row)

        # Run Test orchestration: power on (sequence) then program
        run_row = QtWidgets.QHBoxLayout()
        self.run_test_btn = QtWidgets.QPushButton('Run Test (Power+Program)')
        self.run_test_btn.clicked.connect(self.run_test_sequence)
        run_row.addWidget(self.run_test_btn)
        test2_layout.addLayout(run_row)

        self.top_tabs.addTab(test2_widget, 'Test')

        # Auto-scan VISA resources shortly after startup so detected devices
        # appear without the user needing to press Scan (Scan button remains as backup).
        try:
            QtCore.QTimer.singleShot(200, lambda: self.on_scan_instruments())
        except Exception:
            pass

    def get_instrument_names(self):
        names = []
        for i in range(self.tabs.count()):
            names.append(self.tabs.tabText(i))
        return names

    def _add_seq_instr(self):
        name = self.seq_instr_combo.currentText()
        if name:
            self.seq_list.addItem(f'Instrument: {name}')

    def _add_seq_delay(self):
        delay, ok = QtWidgets.QInputDialog.getDouble(self, 'Add Delay', 'Delay (seconds):', 1.0, 0.1, 60.0, 1)
        if ok:
            self.seq_list.addItem(f'Delay: {delay:.1f} s')

    def _remove_seq_selected(self):
        for item in self.seq_list.selectedItems():
            self.seq_list.takeItem(self.seq_list.row(item))

    def power_off_all(self):
        """Turn off outputs/inputs for all instruments in tabs."""
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, KeithleyPanel):
                # Turn off all outputs
                if widget.inst:
                    for ch in (1, 2, 3):
                        try:
                            widget.inst.set_output(ch, False)
                        except Exception:
                            pass
                widget.master_out_btn.setChecked(False)
                widget.master_out_btn.setText('All Off')
            elif isinstance(widget, HittiteSigGenPanel):
                # Turn off output
                if widget.dev:
                    try:
                        widget.dev.set_output(False)
                        widget.output_btn.setChecked(False)
                        widget.output_btn.setText('Output Off')
                        widget.status_label.setText('Output OFF')
                    except Exception as e:
                        widget.status_label.setText(f'Failed to set output: {e}')
            elif isinstance(widget, KeysightPanel):
                # Turn off both inputs
                if widget.dev:
                    for ch in (1, 2):
                        if hasattr(widget, 'ch_enabled') and not widget.ch_enabled[ch].isChecked():
                            continue
                        try:
                            widget.dev.set_input(ch, False)
                        except Exception:
                            pass
                widget.input_toggle.setChecked(False)
                widget.input_toggle.setText('Input Off')
        if hasattr(self, 'test_power_toggle_btn'):
            self.test_power_toggle_btn.setChecked(False)
            self._update_test_power_toggle_btn(False)
        self._update_global_power_btns(False)
        self.statusBar().showMessage('All instrument outputs/inputs turned OFF', 4000)

    def power_on_all(self):
        """Turn on outputs/inputs for all instruments in tabs."""
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, KeithleyPanel):
                # Turn on all outputs
                if widget.inst:
                    for ch in (1, 2, 3):
                        try:
                            V = float(widget.vol_edits[ch].text())
                            I = float(widget.iam_edits[ch].text())
                            widget.inst.set_voltage(ch, V)
                            widget.inst.set_current(ch, I)
                            widget.inst.set_output(ch, True)
                        except Exception:
                            pass
                widget.master_out_btn.setChecked(True)
                widget.master_out_btn.setText('All On')
            elif isinstance(widget, HittiteSigGenPanel):
                # Turn on output
                if widget.dev:
                    try:
                        widget.dev.set_output(True)
                        widget.output_btn.setChecked(True)
                        widget.output_btn.setText('Output On')
                        widget.status_label.setText('Output ON')
                    except Exception as e:
                        widget.status_label.setText(f'Failed to set output: {e}')
            elif isinstance(widget, KeysightPanel):
                # Turn on both inputs
                if widget.dev:
                    for ch in (1, 2):
                        if hasattr(widget, 'ch_enabled') and not widget.ch_enabled[ch].isChecked():
                            continue
                        try:
                            mode = widget.mode_combo.currentText()
                            value = float(widget.mode_value.text())
                            widget.dev.set_mode(ch, mode)
                            widget.dev.set_parameter(ch, mode, value)
                            widget.dev.set_input(ch, True)
                        except Exception:
                            pass
                widget.input_toggle.setChecked(True)
                widget.input_toggle.setText('Input On')
        if hasattr(self, 'test_power_toggle_btn'):
            self.test_power_toggle_btn.setChecked(True)
            self._update_test_power_toggle_btn(True)
        self._update_global_power_btns(True)
        self.statusBar().showMessage('All instrument outputs/inputs turned ON', 4000)


    # Do not autoload config on startup; GUI starts empty

    def refresh_configs_list(self):
        self.load_combo.clear()
        files = [f for f in os.listdir(self.configs_dir) if f.lower().endswith('.json')]
        for f in files:
            self.load_combo.addItem(f)
        if files:
            self.load_combo.setCurrentIndex(0)

    def save_config_dialog(self):
        # Ask for filename to save config
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Config', self.configs_dir, 'JSON Files (*.json)')
        if not fname:
            return
        if not fname.lower().endswith('.json'):
            fname += '.json'
        self.save_config(fname)
        self.refresh_configs_list()

    def save_config(self, path):
        instruments = []
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            tab_type = 'Keithley 2230' if isinstance(widget, KeithleyPanel) else 'Keysight EL34243A'
            entry = {'type': tab_type, 'resource': widget.resource}
            if tab_type == 'Keithley 2230':
                entry['channels'] = {}
                for ch in (1, 2, 3):
                    entry['channels'][ch] = {
                        'voltage': widget.vol_edits[ch].text(),
                        'current': widget.iam_edits[ch].text(),
                        'output': widget.master_out_btn.isChecked()
                    }
            else:
                entry['channels'] = {}
                for ch in (1, 2):
                    entry['channels'][ch] = {
                        'mode': widget.mode_combo.currentText(),
                        'value': widget.mode_value.text(),
                        'input': widget.input_toggle.isChecked()
                    }
            instruments.append(entry)

        # Save sequencing information if available
        seq = []
        use_seq = False
        try:
            if hasattr(self, 'power_seq_builder'):
                seq = self.power_seq_builder.get_sequence()
                use_seq = self.power_seq_builder.use_sequence()
        except Exception:
            seq = []
            use_seq = False

        payload = {
            'instruments': instruments,
            'sequence': seq,
            'use_sequence': use_seq,
            'program_code': self.program_code_edit.toPlainText() if hasattr(self, 'program_code_edit') else ''
        }
        try:
            with open(path, 'w') as f:
                json.dump(payload, f, indent=2)
            self.statusBar().showMessage(f'Saved config to {path}', 4000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Save failed', str(e))

    def load_config_dialog(self):
        # Load config from selected file in dropdown
        fname = self.load_combo.currentText()
        if not fname:
            QtWidgets.QMessageBox.information(self, 'No config', 'No config file selected.')
            return
        path = os.path.join(self.configs_dir, fname)
        self.load_config(path)

    def load_config(self, path):
        if not os.path.exists(path):
            QtWidgets.QMessageBox.information(self, 'No config', f'Config file not found: {path}')
            return
        try:
            with open(path, 'r') as f:
                content = json.load(f)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Load failed', str(e))
            return

        # Backwards compatibility: older configs were lists of instruments
        if isinstance(content, list):
            instruments = content
            sequence = []
            use_sequence = False
        else:
            instruments = content.get('instruments', [])
            sequence = content.get('sequence', [])
            use_sequence = content.get('use_sequence', False)

        # Remove all tabs
        while self.tabs.count():
            self.tabs.removeTab(0)

        # Add instruments from config
        for entry in instruments:
            inst_type = entry.get('type', 'Keithley 2230')
            resource = entry.get('resource', '')
            panel = None
            if inst_type == 'Keithley 2230':
                panel = KeithleyPanel(resource)
                self.tabs.addTab(panel, resource)
                panel.resource_edit.setText(resource)
                panel.on_connect()
                # Set channel values and apply them to instrument
                for ch in (1, 2, 3):
                    ch_cfg = entry['channels'].get(str(ch)) or entry['channels'].get(ch)
                    if ch_cfg:
                        panel.vol_edits[ch].setText(str(ch_cfg.get('voltage', '0')))
                        panel.iam_edits[ch].setText(str(ch_cfg.get('current', '0.03')))
                        if panel.inst:
                            try:
                                panel.inst.set_voltage(ch, float(panel.vol_edits[ch].text()))
                                panel.inst.set_current(ch, float(panel.iam_edits[ch].text()))
                            except Exception:
                                pass
                panel.master_out_btn.setChecked(False)
                panel.master_out_btn.setText('All Off')
            else:
                panel = KeysightPanel(resource)
                self.tabs.addTab(panel, resource)
                panel.resource_edit.setText(resource)
                panel.on_connect()
                # Set channel values and apply them to instrument
                for ch in (1, 2):
                    ch_cfg = entry['channels'].get(str(ch)) or entry['channels'].get(ch)
                    if ch_cfg:
                        panel.ch_select.setCurrentIndex(ch - 1)
                        panel.mode_combo.setCurrentText(ch_cfg.get('mode', 'CC'))
                        panel.mode_value.setText(str(ch_cfg.get('value', '0.1')))
                        if panel.dev:
                            try:
                                panel.dev.set_mode(ch, panel.mode_combo.currentText())
                                panel.dev.set_parameter(ch, panel.mode_combo.currentText(), float(panel.mode_value.text()))
                            except Exception:
                                pass
                        panel.input_toggle.setChecked(False)
                        panel.input_toggle.setText('Input Off')
            # Set up tab name update callback for loaded panels
            def update_tab_name(panel=panel, resource=resource):
                idx = self.tabs.indexOf(panel)
                if idx != -1:
                    name = panel.name_edit.text().strip() if hasattr(panel, 'name_edit') else ''
                    self.tabs.setTabText(idx, name if name else resource)
            if hasattr(panel, 'name_edit'):
                panel.name_edit.textChanged.connect(lambda: update_tab_name(panel, resource))
                # refresh sequence builder dropdown when name changes
                try:
                    if hasattr(self, 'power_seq_builder'):
                        panel.name_edit.textChanged.connect(lambda: self.power_seq_builder.refresh_instr_combo())
                except Exception:
                    pass
            update_tab_name(panel, resource)

        # Restore sequencing info if present
        try:
            if hasattr(self, 'power_seq_builder'):
                # clear existing sequence
                self.power_seq_builder.seq_list.clear()
                for step in sequence:
                    self.power_seq_builder.seq_list.addItem(step)
                # set enabled state
                self.power_seq_builder.enable_checkbox.setChecked(bool(use_sequence))
                # refresh combo entries to reflect loaded tab names
                self.power_seq_builder.refresh_instr_combo()
        except Exception:
            pass
        # Restore programming code if present
        try:
            prog = content.get('program_code', '') if isinstance(content, dict) else ''
            if hasattr(self, 'program_code_edit') and prog:
                self.program_code_edit.setPlainText(prog)
        except Exception:
            pass
        self.statusBar().showMessage(f'Loaded config from {path}', 4000)
        self.refresh_configs_list()
        # Set the dropdown to the currently loaded config
        fname = os.path.basename(path)
        idx = self.load_combo.findText(fname)
        if idx != -1:
            self.load_combo.setCurrentIndex(idx)

    def load_config_on_startup(self):
        # Load first config file in configs folder if present
        files = [f for f in os.listdir(self.configs_dir) if f.lower().endswith('.json')]
        if files:
            path = os.path.join(self.configs_dir, files[0])
            self.load_config(path)

    def add_instrument_panel(self, resource: str, label: str = None, inst_type: str = 'Keithley 2230'):
        # Create panel
        if inst_type.startswith('Keysight'):
            panel = KeysightPanel(resource)
        elif inst_type.startswith('Hittite') or inst_type.startswith('Sig Gen') or 'Hittite' in inst_type or 'Sig Gen' in inst_type:
            panel = HittiteSigGenPanel(resource)
        else:
            panel = KeithleyPanel(resource)
        # Use name from name_edit if populated, else label or resource
        tab_label = label if label else resource
        if hasattr(panel, 'name_edit') and panel.name_edit.text().strip():
            tab_label = panel.name_edit.text().strip()
        # avoid duplicate labels
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == tab_label:
                QtWidgets.QMessageBox.information(self, 'Duplicate', f'Tab "{tab_label}" already exists.')
                return
        self.tabs.addTab(panel, tab_label)
        self.tabs.setCurrentWidget(panel)
        # Set up tab name update callback (connect after tab is added)
        def update_tab_name(panel=panel, label=label, resource=resource):
            idx = self.tabs.indexOf(panel)
            if idx != -1:
                name = panel.name_edit.text().strip()
                self.tabs.setTabText(idx, name if name else label if label else resource)
        if hasattr(panel, 'name_edit'):
            panel.name_edit.textChanged.connect(lambda: update_tab_name(panel, label, resource))
            # refresh sequence builder dropdown when name changes
            try:
                if hasattr(self, 'power_seq_builder'):
                    panel.name_edit.textChanged.connect(lambda: self.power_seq_builder.refresh_instr_combo())
            except Exception:
                pass
        update_tab_name(panel, label, resource)
        self.power_seq_builder.refresh_instr_combo()
        # Auto-connect shortly after adding the panel so VISA resources initialize
        try:
            QtCore.QTimer.singleShot(100, lambda: (hasattr(panel, 'on_connect') and panel.on_connect()))
            # After a small delay, ensure the newly-added instrument outputs are OFF
            QtCore.QTimer.singleShot(250, lambda: self._auto_turn_off_panel(panel))
        except Exception:
            try:
                if hasattr(panel, 'on_connect'):
                    panel.on_connect()
                try:
                    self._auto_turn_off_panel(panel)
                except Exception:
                    pass
            except Exception:
                pass

    def add_instrument_by_serial(self, sn: str, inst_type: str = 'Keithley 2230'):
        sn = sn.strip()
        if not sn:
            return
        # If full resource given, use as-is; otherwise construct USB resource
        resource = sn if '::' in sn else f'USB0::0x05E6::0x2230::{sn}::INSTR'
        self.add_instrument_panel(resource, sn if '::' not in sn else resource, inst_type)

    def get_all_instruments(self):
        # return list of instrument names from tabs and detected combo (if present)
        names = [self.tabs.tabText(i) for i in range(self.tabs.count())]
        # also include detected combo simple labels (resource parts)
        try:
            for i in range(self.detected_combo.count()):
                data = self.detected_combo.itemData(i)
                text = self.detected_combo.itemText(i)
                if data and isinstance(data, tuple):
                    # resource entries
                    parts = text.split('(')
                    label = parts[0].strip()
                    if label and label not in names:
                        names.append(label)
        except Exception:
            pass
        return names

    def _refresh_seq_instr_combo(self):
        self.seq_instr_combo.clear()
        for i in range(self.tabs.count()):
            name = self.tabs.tabText(i)
            self.seq_instr_combo.addItem(name)

    # Removed manual Add instrument by SN/resource; use VISA scan and Add Selected only

    def on_scan_instruments(self):
        """Scan VISA resources and populate detected_combo with resources. Attempt to classify type by *IDN?"""
        self.detected_combo.clear()
        try:
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Scan failed', f'VISA scan failed: {e}')
            return

        # Categorize instruments
        categories = {
            'Keithley 2230': [],
            'Keysight EL34243A': [],
            'Hittite Sig Gen': [],
            'Unknown': []
        }
        for res in resources:
            inst_type = 'Unknown'
            label = res
            try:
                dev = rm.open_resource(res, timeout=1000)
                idn = dev.query("*IDN?")
                dev.close()
                lidn = idn.upper()
                if 'KEITHLEY' in lidn or '2230' in res:
                    inst_type = 'Keithley 2230'
                    label = res.split('::')[3] if '::' in res else res
                elif 'KEYSIGHT' in lidn or 'AGILENT' in lidn or 'EL34243' in lidn.upper():
                    inst_type = 'Keysight EL34243A'
                    label = res.split('::')[3] if '::' in res else res
                elif 'HITTITE' in lidn or 'SIG GEN' in lidn or 'HITTITE' in res.upper():
                    inst_type = 'Hittite Sig Gen'
                    label = res.split('::')[3] if '::' in res else res
            except Exception:
                pass
            categories.setdefault(inst_type, []).append((label, res, inst_type))

        total_found = sum(len(v) for v in categories.values())
        if total_found == 0:
            QtWidgets.QMessageBox.information(self, 'No devices', 'No VISA resources found.')
            return

        # Add grouped items to combo box
        for cat, items in categories.items():
            if items:
                self.detected_combo.addItem(f'--- {cat} ---', None)
                for label, resource, inst_type in items:
                    self.detected_combo.addItem(f'{inst_type}: {label}    ({resource})', (resource, inst_type))

        # refresh sequence builder instrument list as available detected devices changed
        try:
            if hasattr(self, 'power_seq_builder'):
                self.power_seq_builder.refresh_instr_combo()
        except Exception:
            pass

        self.statusBar().showMessage(f'Found {total_found} device(s)', 4000)
        # Removed self.add_input.setText; Add instrument text box no longer exists

    def on_add_selected_instrument(self):
        data = self.detected_combo.currentData()
        if not data:
            QtWidgets.QMessageBox.information(self, 'No selection', 'Select a detected device first (Scan VISA).')
            return
        resource, inst_type = data
        parts = resource.split('::')
        label = parts[3] if len(parts) >= 4 else resource
        self.add_instrument_panel(resource, label, inst_type)
        # refresh sequence builder after adding a tab
        try:
            if hasattr(self, 'power_seq_builder'):
                self.power_seq_builder.refresh_instr_combo()
        except Exception:
            pass
        self.statusBar().showMessage(f'Added {label}', 3000)

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        try:
            widget.close()
        except Exception:
            pass
        self.tabs.removeTab(index)
        self.power_seq_builder.refresh_instr_combo()

    def closeEvent(self, event):
        # close all panels to ensure instruments are closed
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            try:
                widget.close()
            except Exception:
                pass
        event.accept()

    def _update_global_power_btns(self, on):
        if hasattr(self, 'test_power_toggle_btn'):
            if on:
                self.test_power_toggle_btn.setStyleSheet('background-color: #4CAF50; color: white;')
            else:
                self.test_power_toggle_btn.setStyleSheet('background-color: #F44336; color: white;')

    def _update_test_power_toggle_btn(self, on):
        # Update both Sequencing tab primary button and the Test tab button (if present)
        if hasattr(self, 'test_power_toggle_btn'):
            if on:
                self.test_power_toggle_btn.setText('Power On All')
                self.test_power_toggle_btn.setStyleSheet('background-color: #4CAF50; color: white;')
            else:
                self.test_power_toggle_btn.setText('Power Off All')
                self.test_power_toggle_btn.setStyleSheet('background-color: #F44336; color: white;')
            try:
                self.test_power_toggle_btn.setChecked(on)
            except Exception:
                pass
        if hasattr(self, 'test_tab_power_btn'):
            try:
                self.test_tab_power_btn.setChecked(on)
                if on:
                    self.test_tab_power_btn.setText('Power On All')
                    self.test_tab_power_btn.setStyleSheet('background-color: #4CAF50; color: white;')
                else:
                    self.test_tab_power_btn.setText('Power Off All')
                    self.test_tab_power_btn.setStyleSheet('background-color: #F44336; color: white;')
            except Exception:
                pass

    def on_test_power_toggle(self):
        # Use the clicked button's checked state if possible so the button behaves as a toggle.
        on = None
        try:
            sender = self.sender()
            if sender is not None:
                try:
                    on = bool(sender.isChecked())
                except Exception:
                    on = None
        except Exception:
            on = None

        # Fallback: if we couldn't get the sender, derive from either button
        if on is None:
            try:
                on = False
                if hasattr(self, 'test_power_toggle_btn') and self.test_power_toggle_btn.isChecked():
                    on = True
                if hasattr(self, 'test_tab_power_btn') and self.test_tab_power_btn.isChecked():
                    on = True
            except Exception:
                on = False

        # Synchronize both UI buttons to the chosen state
        try:
            if hasattr(self, 'test_power_toggle_btn'):
                self.test_power_toggle_btn.setChecked(on)
            if hasattr(self, 'test_tab_power_btn'):
                self.test_tab_power_btn.setChecked(on)
        except Exception:
            pass

        # Perform the action for the chosen state
        if on:
            # Power ON (use sequence if configured)
            try:
                self._update_test_power_toggle_btn(True)
            except Exception:
                pass
            try:
                self._run_power_sequence()
            except Exception:
                pass
        else:
            # Power OFF
            try:
                self._update_test_power_toggle_btn(False)
            except Exception:
                pass
            try:
                self.power_off_all()
            except Exception:
                pass

    def _run_power_sequence(self, on_complete=None):
        """Run the configured power-up sequence. If on_complete is provided, it will be
        called (safely via QTimer) when the sequence finishes.
        """
        sequence = self.power_seq_builder.get_sequence()
        use_seq = self.power_seq_builder.use_sequence()
        if use_seq and sequence:
            def run_step(idx):
                # check global abort flag
                if getattr(self, '_sequence_abort_flag', False):
                    self._log('Sequence aborted by user')
                    # reset flag for next run
                    try:
                        self._sequence_abort_flag = False
                    except Exception:
                        pass
                    if on_complete:
                        try:
                            QtCore.QTimer.singleShot(100, on_complete)
                        except Exception:
                            try:
                                on_complete()
                            except Exception:
                                pass
                    return
                if idx >= len(sequence):
                    self.statusBar().showMessage('Sequence power on complete', 4000)
                    if on_complete:
                        # call back shortly after finishing to keep UI responsive
                        try:
                            QtCore.QTimer.singleShot(100, on_complete)
                        except Exception:
                            try:
                                on_complete()
                            except Exception:
                                pass
                    return
                item = sequence[idx]
                self._log(f'Processing step: {item}')
                if item.startswith('Instrument: '):
                    name = item[len('Instrument: '):]
                    for i in range(self.tabs.count()):
                        tab_name = self.tabs.tabText(i)
                        if tab_name == name:
                            widget = self.tabs.widget(i)
                            if isinstance(widget, KeithleyPanel):
                                if widget.inst:
                                    for ch in (1, 2, 3):
                                        try:
                                            V = float(widget.vol_edits[ch].text())
                                            I = float(widget.iam_edits[ch].text())
                                            widget.inst.set_voltage(ch, V)
                                            widget.inst.set_current(ch, I)
                                            widget.inst.set_output(ch, True)
                                        except Exception:
                                            pass
                                    widget.master_out_btn.setChecked(True)
                                    widget.master_out_btn.setText('All On')
                            elif isinstance(widget, HittiteSigGenPanel):
                                if widget.dev:
                                    try:
                                        widget.dev.set_output(True)
                                        widget.output_btn.setChecked(True)
                                        widget.output_btn.setText('Output On')
                                        widget.status_label.setText('Output ON')
                                    except Exception as e:
                                        widget.status_label.setText(f'Failed to set output: {e}')
                            elif isinstance(widget, KeysightPanel):
                                if widget.dev:
                                    for ch in (1, 2):
                                        if hasattr(widget, 'ch_enabled') and not widget.ch_enabled[ch].isChecked():
                                            continue
                                        try:
                                            mode = widget.mode_combo.currentText()
                                            value = float(widget.mode_value.text())
                                            widget.dev.set_mode(ch, mode)
                                            widget.dev.set_parameter(ch, mode, value)
                                            widget.dev.set_input(ch, True)
                                        except Exception:
                                            pass
                                    widget.input_toggle.setChecked(True)
                                    widget.input_toggle.setText('Input On')
                    QtCore.QTimer.singleShot(100, lambda: run_step(idx + 1))
                elif item.startswith('Delay: '):
                    delay_val = float(item[len('Delay: '):-3])
                    self._log(f'Waiting {delay_val} s')
                    QtCore.QTimer.singleShot(int(delay_val * 1000), lambda: run_step(idx + 1))
                else:
                    run_step(idx + 1)
            run_step(0)
        else:
            # No sequence configured or sequence disabled: just power on all now
            self.power_on_all()
            # If caller provided a completion callback, call it shortly after powering on
            if on_complete:
                try:
                    QtCore.QTimer.singleShot(100, on_complete)
                except Exception:
                    try:
                        on_complete()
                    except Exception:
                        pass

    def run_program_code(self):
        """Run the user-supplied programming code in a separate Python process.
        The code is written to a temporary file and executed with the same Python
        interpreter. Stdout/stderr are captured and appended to the Test Run Log.
        This avoids blocking the GUI and isolates errors.
        """
        if not hasattr(self, 'program_code_edit'):
            return
        code = self.program_code_edit.toPlainText()
        if not code.strip():
            self._log('No program code to run')
            return

        # write to a temporary file
        try:
            tf = tempfile.NamedTemporaryFile('w', delete=False, suffix='.py')
            tf.write('# Auto-generated program file from GUI\n')
            # provide a small bootstrap that injects 'main','tabs','panels' into globals
            tf.write('import sys\n')
            tf.write('def _bootstrap(main=None, tabs=None, panels=None):\n')
            tf.write('    globals().update({"main": main, "tabs": tabs, "panels": panels})\n')
            tf.write('\n')
            tf.write(code)
            tf.flush()
            tf.close()
            self._program_tempfile = tf.name
        except Exception as e:
            self._log(f'Failed to write temp program file: {e}')
            return

        # prepare process
        try:
            proc = QtCore.QProcess(self)
            self.program_process = proc
            # set up handlers
            proc.readyReadStandardOutput.connect(lambda: self._on_proc_stdout(proc))
            proc.readyReadStandardError.connect(lambda: self._on_proc_stderr(proc))
            proc.finished.connect(lambda code, status: self._on_proc_finished(code, status, proc))
            python_exe = sys.executable or 'python'
            args = [self._program_tempfile]
            self._log(f'Starting program: {os.path.basename(self._program_tempfile)}')
            proc.start(python_exe, args)
            # Update UI: disable run buttons, enable abort
            try:
                if hasattr(self, 'run_program_btn'):
                    self.run_program_btn.setEnabled(False)
                if hasattr(self, 'abort_program_btn'):
                    self.abort_program_btn.setEnabled(True)
                if hasattr(self, 'program_now_btn'):
                    self.program_now_btn.setEnabled(False)
            except Exception:
                pass
        except Exception as e:
            self._log(f'Failed to start program process: {e}')

    def _on_proc_stdout(self, proc: QtCore.QProcess):
        try:
            data = proc.readAllStandardOutput().data().decode('utf-8', errors='replace')
            for line in data.splitlines():
                self._log(f'OUT: {line}')
        except Exception:
            pass

    def _on_proc_stderr(self, proc: QtCore.QProcess):
        try:
            data = proc.readAllStandardError().data().decode('utf-8', errors='replace')
            for line in data.splitlines():
                self._log(f'ERR: {line}')
        except Exception:
            pass

    def _on_proc_finished(self, exit_code, exit_status, proc: QtCore.QProcess):
        try:
            self._log(f'Program process finished (code={exit_code})')
        except Exception:
            pass
        finally:
            try:
                if proc is self.program_process:
                    self.program_process = None
            except Exception:
                pass
            # cleanup temp file
            try:
                if getattr(self, '_program_tempfile', None):
                    os.remove(self._program_tempfile)
                    self._program_tempfile = None
            except Exception:
                pass
        # Update UI buttons
        try:
            if hasattr(self, 'run_program_btn'):
                self.run_program_btn.setEnabled(True)
            if hasattr(self, 'abort_program_btn'):
                self.abort_program_btn.setEnabled(False)
            if hasattr(self, 'program_now_btn'):
                self.program_now_btn.setEnabled(True)
        except Exception:
            pass

    def on_program_abort(self):
        # Abort the running program process if present
        try:
            if getattr(self, 'program_process', None) is not None:
                try:
                    self.program_process.kill()
                except Exception:
                    try:
                        self.program_process.terminate()
                    except Exception:
                        pass
                self._log('Program aborted by user')
                self.program_process = None
        except Exception:
            pass
        # Update UI
        try:
            if hasattr(self, 'run_program_btn'):
                self.run_program_btn.setEnabled(True)
            if hasattr(self, 'abort_program_btn'):
                self.abort_program_btn.setEnabled(False)
            if hasattr(self, 'program_now_btn'):
                self.program_now_btn.setEnabled(True)
        except Exception:
            pass

    def run_test_sequence(self):
        """Run the Test sequence: apply power sequence (if enabled), then run programming code (if present).
        Any blank menus (no sequence, no program) are ignored per user request.
        """
        # Step 1: Power on according to sequence or all-on
        use_seq = False
        try:
            if hasattr(self, 'power_seq_builder'):
                use_seq = self.power_seq_builder.use_sequence()
        except Exception:
            use_seq = False

        # If there is a sequence and it's enabled, run it; otherwise power on all
        seq = []
        try:
            if hasattr(self, 'power_seq_builder'):
                seq = self.power_seq_builder.get_sequence()
        except Exception:
            seq = []
        if use_seq and seq:
            # Ensure UI shows power-on state
            if hasattr(self, 'test_power_toggle_btn'):
                self.test_power_toggle_btn.setChecked(True)
                self._update_test_power_toggle_btn(True)

            # Run the sequence and when complete, run programming if present
            def after_seq():
                try:
                    self._program_after_power()
                except Exception:
                    pass

            self._run_power_sequence(on_complete=after_seq)
        else:
            # No sequence: power on all now
            self.power_on_all()
            # Immediately program (if code present)
            self._program_after_power()

    def _program_after_power(self):
        # Run program code only if present
        try:
            if hasattr(self, 'program_code_edit') and self.program_code_edit.toPlainText().strip():
                self.run_program_code()
        except Exception:
            pass

def main():
    import traceback
    app = QtWidgets.QApplication(sys.argv)
    # ...existing setup code...
    try:
        print('Launching MainWindow...')
        w = MainWindow()
        w.resize(1000, 700)
        w.show()
        sys.exit(app.exec_())
    except Exception:
        print('Exception occurred while launching GUI:')
        traceback.print_exc()

if __name__ == '__main__':
    main()