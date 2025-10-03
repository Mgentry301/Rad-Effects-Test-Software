
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
from functools import partial

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QPalette
from PyQt5.QtCore import Qt
import pyvisa

from Instruments.keithley2230 import Keithley2230
from Instruments.keysight_el import KeysightEL
from Instruments.hittite_siggen import HittiteSigGen


class KeithleyPanel(QtWidgets.QWidget):
    def set_tab_name_callback(self, callback):
        self.name_edit.textChanged.connect(callback)
    """Panel for a Keithley 2230 instrument (uses keithley2230 wrapper)."""
    def __init__(self, resource, parent=None):
        super().__init__(parent)
        self.resource = resource
        self.inst = None
        self.latest_currents = {1: None, 2: None, 3: None}
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
                self.status_label.setText('All channels output ON')
            else:
                for ch in (1, 2, 3):
                    try:
                        self.inst.set_output(ch, False)
                    except Exception:
                        pass
                self.master_out_btn.setText('All Off')
                self.status_label.setText('All channels output OFF')
        except Exception as e:
            self.master_out_btn.setChecked(not on)
            self.master_out_btn.setText('All On' if not on else 'All Off')
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
        layout.addLayout(ch_row)

        # On/Off control
        inp_row = QtWidgets.QHBoxLayout()
        self.input_toggle = QtWidgets.QPushButton('Input Off')
        self.input_toggle.setCheckable(True)
        self.input_toggle.clicked.connect(self.on_toggle_input)
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
                self.input_toggle.setChecked(on)
                self.input_toggle.setText('Input On' if on else 'Input Off')
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
        on = self.input_toggle.isChecked()
        try:
            self.dev.set_input(ch, on)
            self.input_toggle.setText('Input On' if on else 'Input Off')
            self.status_label.setText(f'Channel {ch} {"enabled" if on else "disabled"}')
        except Exception as e:
            self.input_toggle.setChecked(not on)
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



import json
import os
class HittiteSigGenPanel(QtWidgets.QWidget):
    def on_toggle_output(self):
        if self.dev is None:
            self.status_label.setText('Not connected')
            self.output_btn.setChecked(False)
            return
        on = self.output_btn.isChecked()
        try:
            self.dev.set_output(on)
            self.output_btn.setText('Output On' if on else 'Output Off')
            self.status_label.setText(f'Output {"ON" if on else "OFF"}')
        except Exception as e:
            self.status_label.setText(f'Failed to set output: {e}')
            self.output_btn.setChecked(not on)
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
        
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Instrument Controller - Multiple Instruments")
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

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
        layout.addLayout(top_row)

        # Tabs for instruments
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tabs)

        # Bottom: Power Off/On All buttons
        power_row = QtWidgets.QHBoxLayout()
        self.poweroff_btn = QtWidgets.QPushButton('Power Off All')
        self.poweroff_btn.clicked.connect(self.power_off_all)
        self.poweron_btn = QtWidgets.QPushButton('Power On All')
        self.poweron_btn.clicked.connect(self.power_on_all)
        power_row.addWidget(self.poweroff_btn)
        power_row.addWidget(self.poweron_btn)
        layout.addLayout(power_row)

        self.statusBar().showMessage('Ready')

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
            elif isinstance(widget, KeysightPanel):
                # Turn off both inputs
                if widget.dev:
                    for ch in (1, 2):
                        try:
                            widget.dev.set_input(ch, False)
                        except Exception:
                            pass
                widget.input_toggle.setChecked(False)
                widget.input_toggle.setText('Input Off')
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
            elif isinstance(widget, KeysightPanel):
                # Turn on both inputs
                if widget.dev:
                    for ch in (1, 2):
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
        config = []
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
            config.append(entry)
        try:
            with open(path, 'w') as f:
                json.dump(config, f, indent=2)
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
                config = json.load(f)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Load failed', str(e))
            return
        # Remove all tabs
        while self.tabs.count():
            self.tabs.removeTab(0)
        # Add instruments from config
        for entry in config:
            inst_type = entry.get('type', 'Keithley 2230')
            resource = entry.get('resource', '')
            panel = None
            if inst_type == 'Keithley 2230':
                panel = KeithleyPanel(resource)
                self.tabs.addTab(panel, resource)
                panel.resource_edit.setText(resource)
                panel.on_connect()
                # Set channel values only (do not turn on outputs)
                for ch in (1, 2, 3):
                    ch_cfg = entry['channels'].get(str(ch)) or entry['channels'].get(ch)
                    if ch_cfg:
                        panel.vol_edits[ch].setText(str(ch_cfg.get('voltage', '0')))
                        panel.iam_edits[ch].setText(str(ch_cfg.get('current', '0.03')))
                # Set output button state but do NOT turn on outputs
                panel.master_out_btn.setChecked(False)
                panel.master_out_btn.setText('All Off')
            else:
                panel = KeysightPanel(resource)
                self.tabs.addTab(panel, resource)
                panel.resource_edit.setText(resource)
                panel.on_connect()
                # Set channel values only (do not turn on inputs)
                for ch in (1, 2):
                    ch_cfg = entry['channels'].get(str(ch)) or entry['channels'].get(ch)
                    if ch_cfg:
                        panel.ch_select.setCurrentIndex(ch - 1)
                        panel.mode_combo.setCurrentText(ch_cfg.get('mode', 'CC'))
                        panel.mode_value.setText(str(ch_cfg.get('value', '0.1')))
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
            update_tab_name(panel, resource)
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
        update_tab_name(panel, label, resource)

    def add_instrument_by_serial(self, sn: str, inst_type: str = 'Keithley 2230'):
        sn = sn.strip()
        if not sn:
            return
        # If full resource given, use as-is; otherwise construct USB resource
        resource = sn if '::' in sn else f'USB0::0x05E6::0x2230::{sn}::INSTR'
        self.add_instrument_panel(resource, sn if '::' not in sn else resource, inst_type)

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
        self.statusBar().showMessage(f'Added {label}', 3000)

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        try:
            widget.close()
        except Exception:
            pass
        self.tabs.removeTab(index)

    def closeEvent(self, event):
        # close all panels to ensure instruments are closed
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            try:
                widget.close()
            except Exception:
                pass
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    # Set Fusion style for cross-platform consistency
    app.setStyle('Fusion')
    # Mac-like palette
    palette = QPalette()
    palette.setColor(QPalette.Window, Qt.white)
    palette.setColor(QPalette.WindowText, QtCore.Qt.black)
    palette.setColor(QPalette.Base, Qt.white)
    palette.setColor(QPalette.AlternateBase, QtCore.Qt.lightGray)
    palette.setColor(QPalette.ToolTipBase, QtCore.Qt.white)
    palette.setColor(QPalette.ToolTipText, QtCore.Qt.black)
    palette.setColor(QPalette.Text, QtCore.Qt.black)
    palette.setColor(QPalette.Button, QtCore.Qt.white)
    palette.setColor(QPalette.ButtonText, QtCore.Qt.black)
    palette.setColor(QPalette.Highlight, QtCore.Qt.gray)
    palette.setColor(QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(palette)
    # Mac-like font
    font = app.font()
    font.setFamily('San Francisco')
    font.setPointSize(12)
    app.setFont(font)
    # Mac-like style sheet for rounded buttons and spacing
    app.setStyleSheet('''
        QPushButton {
            border-radius: 8px;
            padding: 6px 16px;
            background: #f5f5f7;
            color: #222;
            font-weight: 500;
            border: 1px solid #d1d1d6;
        }
        QPushButton:pressed {
            background: #e0e0e0;
        }
        QLineEdit, QComboBox {
            border-radius: 6px;
            padding: 4px 8px;
            background: #fff;
            border: 1px solid #d1d1d6;
        }
        QTabWidget::pane {
            border-radius: 10px;
            border: 1px solid #d1d1d6;
            background: #f5f5f7;
        }
        QTabBar::tab {
            border-radius: 8px;
            padding: 8px 20px;
            background: #fff;
            border: 1px solid #d1d1d6;
            margin: 2px;
        }
        QTabBar::tab:selected {
            background: #e5e5ea;
            color: #007aff;
        }
        QGroupBox {
            border-radius: 10px;
            border: 1px solid #d1d1d6;
            margin-top: 10px;
            background: #f5f5f7;
        }
        QLabel {
            color: #222;
        }
    ''')
    w = MainWindow()
    w.resize(1000, 700)
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
