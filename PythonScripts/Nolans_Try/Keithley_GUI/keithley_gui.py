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

from keithley2230 import Keithley2230


import logging

class KeysightEL:
    """PyVISA wrapper for Keysight EL34243A Dual Input DC Electronic Load (with correct mode/value SCPI)."""
    def __init__(self, resource):
        self.resource = resource
        self.rm = None
        self.dev = None
        import logging
        self.logger = logging.getLogger("KeysightEL")
        if not self.logger.hasHandlers():
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

    def open(self):
        self.rm = pyvisa.ResourceManager()
        self.dev = self.rm.open_resource(self.resource, timeout=2000)
        try:
            self.dev.write_termination = '\n'
            self.dev.read_termination = '\n'
        except Exception:
            pass
        self.logger.info(f"Opened resource {self.resource}")

    def close(self):
        try:
            if self.dev is not None:
                self.dev.close()
            if self.rm is not None:
                self.rm.close()
        finally:
            self.dev = None
            self.rm = None
        self.logger.info("Closed resource")

    def get_identification(self):
        self.logger.debug("Query: *IDN?")
        resp = self.dev.query("*IDN?")
        self.logger.debug(f"Response: {resp}")
        return resp

    def select_channel(self, channel: int):
        cmd = f":INSTrument:NSELect {channel}"
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def set_input(self, channel: int, on: bool):
        self.select_channel(channel)
        cmd = f":INPut:STATe {'ON' if on else 'OFF'}"
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def set_mode(self, channel: int, mode: str):
        self.select_channel(channel)
        mapping = {'CC': 'CURR', 'CV': 'VOLT', 'CR': 'RES', 'CP': 'POW'}
        scpi_mode = mapping.get(mode.upper(), mode)
        cmd = f"MODE {scpi_mode}"
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def set_parameter(self, channel: int, mode: str, value: float):
        self.select_channel(channel)
        if mode.upper() == 'CC':
            cmd = f":CURRent:LEVel {value}"
        elif mode.upper() == 'CV':
            cmd = f":SOURce:VOLTage:LEVel {value}"
        elif mode.upper() == 'CR':
            cmd = f":SOURce:RESistance:LEVel {value}"
        else:
            raise ValueError("Unknown mode")
        self.logger.debug(f"Write: {cmd}")
        self.dev.write(cmd)

    def measure_current(self, channel: int):
        self.select_channel(channel)
        cmd = ":MEASure:CURRent?"
        self.logger.debug(f"Query: {cmd}")
        resp = self.dev.query(cmd)
        self.logger.debug(f"Response: {resp}")
        return float(resp)

    def measure_voltage(self, channel: int):
        self.select_channel(channel)
        cmd = ":MEASure:VOLTage?"
        self.logger.debug(f"Query: {cmd}")
        resp = self.dev.query(cmd)
        self.logger.debug(f"Response: {resp}")
        return float(resp)

    def get_input_state(self, channel: int):
        self.select_channel(channel)
        cmd = ":INPut:STATe?"
        self.logger.debug(f"Query: {cmd}")
        resp = self.dev.query(cmd).strip().upper()
        self.logger.debug(f"Response: {resp}")
        return resp in ('1', 'ON')


class KeithleyPanel(QtWidgets.QWidget):
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



        # Top: Scan VISA, detected devices, Save/Load Config
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

        self.statusBar().showMessage('Ready')

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
                # Set channel values and output
                for ch in (1, 2, 3):
                    ch_cfg = entry['channels'].get(str(ch)) or entry['channels'].get(ch)
                    if ch_cfg:
                        panel.vol_edits[ch].setText(str(ch_cfg.get('voltage', '0')))
                        panel.iam_edits[ch].setText(str(ch_cfg.get('current', '0.03')))
                # Set output state
                panel.master_out_btn.setChecked(any(
                    entry['channels'].get(str(ch), {}).get('output', False)
                    for ch in (1, 2, 3)
                ))
                panel.master_out_btn.setText('All On' if panel.master_out_btn.isChecked() else 'All Off')
                if panel.master_out_btn.isChecked():
                    panel.on_toggle_all_outputs()
            else:
                panel = KeysightPanel(resource)
                self.tabs.addTab(panel, resource)
                panel.resource_edit.setText(resource)
                panel.on_connect()
                # Set channel values
                for ch in (1, 2):
                    ch_cfg = entry['channels'].get(str(ch)) or entry['channels'].get(ch)
                    if ch_cfg:
                        panel.ch_select.setCurrentIndex(ch - 1)
                        panel.mode_combo.setCurrentText(ch_cfg.get('mode', 'CC'))
                        panel.mode_value.setText(str(ch_cfg.get('value', '0.1')))
                        panel.input_toggle.setChecked(ch_cfg.get('input', False))
                        panel.on_apply_mode()
                        panel.on_toggle_input()
        self.statusBar().showMessage(f'Loaded config from {path}', 4000)
        self.refresh_configs_list()

    def load_config_on_startup(self):
        # Load first config file in configs folder if present
        files = [f for f in os.listdir(self.configs_dir) if f.lower().endswith('.json')]
        if files:
            path = os.path.join(self.configs_dir, files[0])
            self.load_config(path)

    def add_instrument_panel(self, resource: str, label: str = None, inst_type: str = 'Keithley 2230'):
        tab_label = label if label else resource
        # avoid duplicate labels
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == tab_label:
                QtWidgets.QMessageBox.information(self, 'Duplicate', f'Tab "{tab_label}" already exists.')
                return
        if inst_type.startswith('Keysight'):
            panel = KeysightPanel(resource)
        else:
            panel = KeithleyPanel(resource)
        self.tabs.addTab(panel, tab_label)
        self.tabs.setCurrentWidget(panel)

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

        found = []
        for res in resources:
            # try to query IDN to classify
            inst_type = 'Unknown'
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
                else:
                    label = res
            except Exception:
                label = res
            found.append((label, res, inst_type))

        if not found:
            QtWidgets.QMessageBox.information(self, 'No devices', 'No VISA resources found.')
            return

        for label, resource, inst_type in found:
            self.detected_combo.addItem(f'{inst_type}: {label}    ({resource})', (resource, inst_type))

        self.statusBar().showMessage(f'Found {len(found)} device(s)', 4000)
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
