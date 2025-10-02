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
import pyvisa

from keithley2230 import Keithley2230


class KeysightEL:
    """Minimal pyvisa wrapper for Keysight EL34243A-like electronic load."""
    def __init__(self, resource):
        self.resource = resource
        self.rm = None
        self.dev = None

    def open(self):
        self.rm = pyvisa.ResourceManager()
        self.dev = self.rm.open_resource(self.resource, timeout=2000)
        # common termination settings
        try:
            self.dev.write_termination = '\n'
            self.dev.read_termination = '\n'
        except Exception:
            pass

    def close(self):
        try:
            if self.dev is not None:
                try:
                    self.dev.close()
                except Exception:
                    pass
            if self.rm is not None:
                try:
                    self.rm.close()
                except Exception:
                    pass
        finally:
            self.dev = None
            self.rm = None

    def get_identification(self):
        return self.dev.query("*IDN?")

    def set_input(self, channel: int, on: bool):
        # many loads accept "INP ON" (global) or "INP{n} ON" / "INP<n>:STATe ON"
        cmd = f"INP{channel} {'ON' if on else 'OFF'}"
        try:
            self.dev.write(cmd)
            return
        except Exception:
            pass
        # fallback global
        cmd2 = f"INP {'ON' if on else 'OFF'}"
        self.dev.write(cmd2)

    def set_mode(self, channel: int, mode: str):
        # mode should be 'CC', 'CV', or 'CR'
        mapping = {'CC': 'CURR', 'CV': 'VOLT', 'CR': 'RES'}
        scpi_mode = mapping.get(mode.upper(), mode)
        # try function mode command
        try:
            self.dev.write(f"FUNC:MODE {scpi_mode}")
            return
        except Exception:
            pass
        # try alternative
        self.dev.write(f"MODE {scpi_mode}")

    def set_parameter(self, channel: int, mode: str, value: float):
        # writes CURR/VOLT/RES depending on mode
        if mode.upper() == 'CC':
            self.dev.write(f"CURR {value}")
        elif mode.upper() == 'CV':
            self.dev.write(f"VOLT {value}")
        elif mode.upper() == 'CR':
            self.dev.write(f"RES {value}")
        else:
            raise ValueError("Unknown mode")

    def measure_current(self, channel: int):
        # many loads support MEAS:CURR? optionally with channel
        try:
            return float(self.dev.query(f"MEAS:CURR? (@{channel})"))
        except Exception:
            pass
        try:
            return float(self.dev.query("MEAS:CURR?"))
        except Exception:
            raise

    def measure_voltage(self, channel: int):
        try:
            return float(self.dev.query(f"MEAS:VOLT? (@{channel})"))
        except Exception:
            pass
        try:
            return float(self.dev.query("MEAS:VOLT?"))
        except Exception:
            raise

    def get_input_state(self, channel: int):
        # try queries
        for q in (f"INP{channel}?", "INP?", "INPut:STATe?"):
            try:
                r = self.dev.query(q).strip()
                if r in ('1', 'ON', 'On', 'on', 'ON\n'):
                    return True
                if r in ('0', 'OFF', 'Off', 'off'):
                    return False
            except Exception:
                continue
        return False


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
        self.mode_combo.addItems(['CC', 'CV', 'CR'])
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


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Instrument Controller - Multiple Instruments")
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Top: add-by-SN / resource input and type selector
        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(QtWidgets.QLabel('Add instrument (SN or full VISA resource):'))
        self.add_input = QtWidgets.QLineEdit()
        self.add_input.setPlaceholderText('e.g. 9200976 or USB0::0x05E6::0x2230::9200976::INSTR')
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(['Keithley 2230', 'Keysight EL34243A'])
        self.add_btn = QtWidgets.QPushButton('Add Instrument')
        self.add_btn.clicked.connect(self.on_add_instrument)

        # Scan and detected devices UI
        self.scan_btn = QtWidgets.QPushButton('Scan VISA')
        self.scan_btn.clicked.connect(self.on_scan_instruments)
        self.detected_combo = QtWidgets.QComboBox()
        self.detected_combo.setMinimumWidth(350)
        self.add_selected_btn = QtWidgets.QPushButton('Add Selected')
        self.add_selected_btn.clicked.connect(self.on_add_selected_instrument)

        top_row.addWidget(self.add_input)
        top_row.addWidget(self.type_combo)
        top_row.addWidget(self.add_btn)
        top_row.addWidget(self.scan_btn)
        top_row.addWidget(self.detected_combo)
        top_row.addWidget(self.add_selected_btn)
        layout.addLayout(top_row)

        # Tabs for instruments
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        self.statusBar().showMessage('Ready')

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

    def on_add_instrument(self):
        text = self.add_input.text().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, 'Input required', 'Enter a serial number or full VISA resource.')
            return
        inst_type = self.type_combo.currentText()
        if '::' in text:
            resource = text
            label = text
        else:
            # if user selected Keysight, do not assume same USB VID/PID; use SN as label and let user edit resource
            if inst_type.startswith('Keysight'):
                resource = text  # allow user to replace with full resource if needed
            else:
                resource = f'USB0::0x05E6::0x2230::{text}::INSTR'
            label = text
        self.add_instrument_panel(resource, label, inst_type)
        self.statusBar().showMessage(f'Added {label}', 3000)
        self.add_input.clear()

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
        if found:
            self.add_input.setText(found[0][1])

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
    w = MainWindow()
    w.resize(1000, 700)
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
