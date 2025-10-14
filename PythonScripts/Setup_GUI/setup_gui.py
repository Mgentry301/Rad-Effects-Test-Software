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
import time
from typing import List, Tuple

from PyQt5 import QtWidgets, QtCore
import pyvisa

from GUI_Wrappers.power_sequence_builder import PowerSequenceBuilder
from GUI_Wrappers.keithley_panel import KeithleyPanel
from GUI_Wrappers.keysightEL_panel import KeysightELPanel
from GUI_Wrappers.keysight_e36233a_panel import KeysightE36233APanel
from GUI_Wrappers.hittite_siggen_panel import HittiteSigGenPanel
from GUI_Wrappers.rhodeschwarz_sma_panel import RhodeSchwarzSMAPanel
from GUI_Wrappers.fieldfox_sa_panel import FieldFoxSAPanel

class MainWindow(QtWidgets.QMainWindow):
    # Thread-safe log signal
    log_signal = QtCore.pyqtSignal(str)
    # --- Internal helpers to reduce duplication ---
    def _keithley_apply_settings(self, panel: KeithleyPanel, on: bool):
        if not getattr(panel, 'inst', None):
            return
        for ch in (1, 2, 3):
            try:
                if on:
                    V = float(panel.vol_edits[ch].text())
                    I = float(panel.iam_edits[ch].text())
                    panel.inst.set_voltage(ch, V)
                    panel.inst.set_current(ch, I)
                    panel.inst.set_output(ch, True)
                else:
                    panel.inst.set_output(ch, False)
            except Exception:
                pass
        panel.master_out_btn.setChecked(on)
        panel.master_out_btn.setText('All On' if on else 'All Off')

    def _keysight_el_apply_settings(self, panel: KeysightELPanel, on: bool):
        if not getattr(panel, 'dev', None):
            return
        for ch in (1, 2):
            try:
                if on:
                    # Read per-channel UI controls
                    mode = (panel.mode_combo_ch1.currentText() if ch == 1 else panel.mode_combo_ch2.currentText())
                    try:
                        value = float(panel.mode_value_ch1.text() if ch == 1 else panel.mode_value_ch2.text())
                    except Exception:
                        value = 0.0
                    panel.dev.set_mode(ch, mode)
                    panel.dev.set_parameter(ch, mode, value)
                    panel.dev.set_input(ch, True)
                else:
                    panel.dev.set_input(ch, False)
            except Exception:
                pass
        # Update per-channel UI toggles if available
        try:
            if hasattr(panel, '_set_input_toggle_ui'):
                panel._set_input_toggle_ui(1, on)
                panel._set_input_toggle_ui(2, on)
        except Exception:
            pass

    def _generic_output_toggle(self, panel, on: bool):
        dev = getattr(panel, 'dev', None)
        if not dev:
            return
        try:
            dev.set_output(on)
            if hasattr(panel, 'output_btn'):
                panel.output_btn.setChecked(on)
                panel.output_btn.setText('Output On' if on else 'Output Off')
            if hasattr(panel, 'status_label'):
                panel.status_label.setText('Output ON' if on else 'Output OFF')
        except Exception:
            pass
    def on_record_clicked(self):
        """Unified record button: start/stop recording for selected metrics."""
        if self.record_btn.isChecked():
            excel_path = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Reads', '', 'Excel Files (*.xlsx)')[0]
            if excel_path and not excel_path.lower().endswith('.xlsx'):
                excel_path += '.xlsx'
            if not excel_path:
                return
            # Write one-time bench summary sheet at recording start
            try:
                self._write_bench_info(excel_path)
            except Exception as e:
                # Non-fatal if we cannot write the bench info
                try:
                    self._log(f'Bench Info write failed: {e}')
                except Exception:
                    pass
            # Start recording selected metrics
            if self.supply_record_toggle.isChecked():
                panels = self.get_all_supply_panels()
                if not panels:
                    self.statusBar().showMessage('No supply panels to record', 4000)
                    # Do not return; continue to other selected metrics (e.g., Spectrum)
                from supply_recorder import SupplyRecorder
                def update_supply_read_speed(sps):
                    self.supply_read_speed_label.setText(f'Supply Sample Rate: {sps:.2f} samples/sec')
                class PatchedSupplyRecorder(SupplyRecorder):
                    def _flush_buffer(self):
                        if not self.buffer:
                            return
                        from openpyxl import Workbook, load_workbook
                        import os
                        header_needed = False
                        if os.path.exists(self.excel_path):
                            try:
                                wb = load_workbook(self.excel_path)
                            except Exception:
                                # Corrupt or non-xlsx; start a new workbook
                                wb = Workbook()
                                ws = wb.active
                                ws.title = self.sheet_name
                                header_needed = True
                            else:
                                ws = None
                            if self.sheet_name in wb.sheetnames:
                                ws = wb[self.sheet_name]
                            else:
                                ws = wb.create_sheet(self.sheet_name)
                                header_needed = True
                        else:
                            wb = Workbook()
                            ws = wb.active
                            ws.title = self.sheet_name
                            header_needed = True
                        if header_needed:
                            # Dynamically build header based on first row
                            if self.buffer:
                                n_total = len(self.buffer[0])
                                # 1 timestamp, then voltages, then currents
                                n_volt = n_total // 2
                                n_curr = n_total - n_volt - 1
                                header = ['timestamp']
                                header += [f'V{i+1}' for i in range(n_volt)]
                                header += [f'I{i+1}' for i in range(n_curr)]
                                ws.append(header)
                        for row in self.buffer:
                            ws.append(row)
                        wb.save(self.excel_path)
                        self.buffer.clear()
                    def _run(self):
                        sample_count = 0
                        start_time = time.time()
                        last_report_time = start_time
                        # match other recorders' cadence (update every ~2s)
                        while not self._stop_event.is_set():
                            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            all_voltages = []
                            all_currents = []
                            for func in self.get_readings_funcs:
                                voltages, currents = func()
                                all_voltages.extend(voltages)
                                all_currents.extend(currents)
                            row = [now] + all_voltages + all_currents
                            self.buffer.append(row)
                            sample_count += 1
                            # Update label with average rate at same cadence as other recorders (~2s)
                            now_ts = time.time()
                            if now_ts - last_report_time >= 2.0:
                                elapsed = max(now_ts - start_time, 1e-6)
                                sps = sample_count / elapsed
                                update_supply_read_speed(sps)
                                last_report_time = now_ts
                            time.sleep(0.01)  # ~100Hz, adjust as needed
                        self._flush_buffer()
                self.global_recorder = PatchedSupplyRecorder(panels, excel_path, sheet_name='supply reads')
                self.global_recorder.start()
                self.statusBar().showMessage('Started recording supplies', 4000)
            if self.spectrum_record_toggle.isChecked():
                # Continuous Spectrum Recording
                import threading
                fieldfox_panel = None
                for i in range(self.tabs.count()):
                    w = self.tabs.widget(i)
                    if isinstance(w, FieldFoxSAPanel):
                        fieldfox_panel = w
                        break
                if fieldfox_panel is None:
                    self.statusBar().showMessage('No FieldFox panel found', 4000)
                    # Skip spectrum but continue to other metrics
                    fieldfox_panel = None
                if fieldfox_panel is not None:
                    def update_spectrum_read_speed(sps: float):
                        self.spectrum_read_speed_label.setText(f'Spectrum Sample Rate: {sps:.2f} samples/sec')
                    self._start_spectrum_capture(fieldfox_panel, excel_path, update_spectrum_read_speed)
                    self._spectrum_recording = True
                    self._spectrum_thread_running = True
                    def running_flag():
                        return self._spectrum_recording and self._spectrum_thread_running
                    # Thread was created inside helper
                    self.statusBar().showMessage('Started recording spectrum', 4000)
            if self.register_record_toggle.isChecked():
                # Register Recording using ACE Client; read list from current config if available
                registers = []
                try:
                    if hasattr(self, 'register_read_array') and self.register_read_array:
                        registers = self.register_read_array
                    else:
                        # Fallback: try to read from current selection in configs dropdown
                        cfg_name = self.load_combo.currentText() if hasattr(self, 'load_combo') else ''
                        if cfg_name:
                            cfg_path = os.path.join(self.configs_dir, cfg_name)
                            if os.path.exists(cfg_path):
                                with open(cfg_path, 'r') as f:
                                    data = json.load(f)
                                    registers = data.get('register_read_array', [])
                except Exception:
                    registers = []
                if not registers:
                    QtWidgets.QMessageBox.warning(self, 'No registers configured', 'No register_read_array found in current config. Load a config that defines it.')
                else:
                    def update_register_read_speed(sps: float):
                        try:
                            self.register_read_speed_label.setText(f'Register Sample Rate: {sps:.2f} samples/sec')
                        except Exception:
                            pass
                    self._start_register_recording(excel_path, registers, update_register_read_speed)
                    self.statusBar().showMessage('Started recording registers', 4000)
            self.record_btn.setText('Stop Recording')
        else:
            # Stop all recordings
            self._stop_all_recordings()
            self.record_btn.setText('Record')
            self.statusBar().showMessage('Stopped recording', 4000)

    def _stop_all_recordings(self):
        """Stop supply, spectrum, and register recordings and reset labels."""
        # Supply
        try:
            if hasattr(self, 'global_recorder') and self.global_recorder:
                try:
                    self.global_recorder.stop()
                except Exception:
                    pass
                self.global_recorder = None
            if hasattr(self, 'supply_read_speed_label'):
                self.supply_read_speed_label.setText('Supply Sample Rate: --')
        except Exception:
            pass
        # Spectrum
        try:
            if hasattr(self, '_spectrum_thread') and self._spectrum_thread:
                self._spectrum_recording = False
                self._spectrum_thread_running = False
                try:
                    self._spectrum_thread.join(timeout=2)
                except Exception:
                    pass
                self._spectrum_thread = None
        except Exception:
            pass
        # Registers
        try:
            if hasattr(self, '_register_thread') and getattr(self, '_register_thread', None):
                try:
                    self._register_recording = False
                except Exception:
                    pass
                try:
                    self._register_thread.join(timeout=2)
                except Exception:
                    pass
                self._register_thread = None
            if hasattr(self, 'register_read_speed_label'):
                self.register_read_speed_label.setText('Register Sample Rate: --')
        except Exception:
            pass

    def _start_register_recording(self, excel_path: str, registers: list, rate_cb):
        """Start register recording in background thread (ACE client)."""
        import threading
        from openpyxl import Workbook, load_workbook
        # Normalize registers to integers (accept int, decimal string, or 0x-prefixed)
        reg_list = []
        for r in registers:
            try:
                if isinstance(r, str):
                    reg_list.append(int(r, 0))  # auto-detect base
                else:
                    reg_list.append(int(r))
            except Exception:
                continue
        if not reg_list:
            QtWidgets.QMessageBox.warning(self, 'No registers', 'No registers specified to record.')
            return

        buffer = []
        flush_interval = 50
        start_time = time.time()
        last_report_time = start_time
        sample_count = 0

        def flush_buffer():
            if not buffer:
                return
            sheet_name = 'register reads'
            if os.path.exists(excel_path):
                try:
                    wb = load_workbook(excel_path)
                except Exception:
                    wb = Workbook()
                    ws = wb.active
                    ws.title = sheet_name
                    header = ['timestamp'] + [f"Reg_{hex(r)}" for r in reg_list]
                    ws.append(header)
                else:
                    ws = None
                if sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                else:
                    ws = wb.create_sheet(sheet_name)
                    header = ['timestamp'] + [f"Reg_{hex(r)}" for r in reg_list]
                    ws.append(header)
            else:
                wb = Workbook()
                ws = wb.active
                ws.title = sheet_name
                header = ['timestamp'] + [f"Reg_{hex(r)}" for r in reg_list]
                ws.append(header)
            for row in buffer:
                ws.append(row)
            wb.save(excel_path)
            buffer.clear()

        def worker():
            nonlocal sample_count, last_report_time
            # Connect to ACE
            try:
                ace_path = r'C:\\Program Files\\Analog Devices\\ACE\\Client'
                if ace_path not in sys.path:
                    sys.path.append(ace_path)
                import clr  # type: ignore
                clr.AddReference('AnalogDevices.Csa.Remoting.Clients')
                clr.AddReference('AnalogDevices.Csa.Remoting.Contracts')
                from AnalogDevices.Csa.Remoting.Clients import ClientManager  # type: ignore
                manager = ClientManager.Create()
                client = manager.CreateRequestClient('localhost:2357')
            except Exception as e:
                self._log(f'ACE connection failed: {e}')
                return
            self._register_recording = True
            self._register_thread_running = True
            try:
                while getattr(self, '_register_recording', False):
                    try:
                        nowts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        values = []
                        for addr in reg_list:
                            try:
                                # ACE expects a string address; send decimal string
                                val = client.ReadRegister(str(int(addr)))
                                if hasattr(val, 'strip'):
                                    val = val.strip('\r\n')
                            except Exception as err:
                                val = f'ERR:{err}'
                            values.append(val)
                        buffer.append([nowts] + values)
                        sample_count += 1
                        if len(buffer) >= flush_interval:
                            flush_buffer()
                    except Exception as e:
                        self._log(f'Register read error: {e}')
                    now_time = time.time()
                    if now_time - last_report_time >= 2.0:
                        elapsed = max(now_time - start_time, 1e-6)
                        rate_cb(sample_count / elapsed)
                        last_report_time = now_time
                    time.sleep(0.05)
            finally:
                try:
                    flush_buffer()
                except Exception:
                    pass
                self._register_thread_running = False
        self._register_thread = threading.Thread(target=worker, daemon=True)
        self._register_thread.start()

    def _start_spectrum_capture(self, panel: FieldFoxSAPanel, excel_path: str, rate_cb):
        """Start spectrum capture in background thread."""
        import threading
        from openpyxl import Workbook, load_workbook
        import os

        # Ensure flags are set before the worker starts
        self._spectrum_recording = True
        self._spectrum_thread_running = True

        # Try to ensure the FieldFox is connected (non-fatal if not yet)
        try:
            if getattr(panel.sa, 'inst', None) is None:
                panel.on_connect()
        except Exception:
            pass

        # Read initial frequency axis (may fail; we'll refresh later)
        try:
            freq = panel.sa.get_freq_axis(panel.unit_combo.currentText())
        except Exception:
            freq = []

        # Create/ensure workbook sheet and header up front
        try:
            try:
                n = len(freq)
            except Exception:
                n = 0
            header = ['timestamp'] + ([f"{f:.6f}" for f in freq] if n > 0 else [])
            if os.path.exists(excel_path):
                try:
                    wb = load_workbook(excel_path)
                except Exception:
                    wb = Workbook()
                if 'capture data' in wb.sheetnames:
                    ws = wb['capture data']
                    if ws.max_row == 1 and ws.max_column == 1 and not ws['A1'].value:
                        ws.append(header)
                else:
                    ws = wb.create_sheet('capture data')
                    ws.append(header)
            else:
                wb = Workbook()
                ws = wb.active
                ws.title = 'capture data'
                ws.append(header)
            wb.save(excel_path)
        except Exception:
            pass

        # Clear any pending I/O on the VISA session to avoid -420 Query Unterminated
        try:
            inst = getattr(panel.sa, 'inst', None)
            if inst is not None and hasattr(inst, 'clear'):
                inst.clear()
        except Exception:
            pass

        buffer = []
        flush_interval = 25
        start_time = time.time()
        last_report_time = start_time
        last_flush_time = start_time
        sample_count = 0

        def flush_buffer():
            if not buffer:
                return
            if os.path.exists(excel_path):
                try:
                    wb = load_workbook(excel_path)
                except Exception:
                    wb = Workbook()
                    ws = wb.active
                    ws.title = 'capture data'
                    try:
                        n = len(freq)
                    except Exception:
                        n = 0
                    header = ['timestamp'] + ([f"{f:.6f}" for f in freq] if n > 0 else [])
                    ws.append(header)
                else:
                    ws = None
                if 'capture data' in wb.sheetnames:
                    ws = wb['capture data']
                else:
                    ws = wb.create_sheet('capture data')
                    try:
                        n = len(freq)
                    except Exception:
                        n = 0
                    header = ['timestamp'] + ([f"{f:.6f}" for f in freq] if n > 0 else [])
                    ws.append(header)
            else:
                wb = Workbook()
                ws = wb.active
                ws.title = 'capture data'
                try:
                    n = len(freq)
                except Exception:
                    n = 0
                header = ['timestamp'] + ([f"{f:.6f}" for f in freq] if n > 0 else [])
                ws.append(header)

            # Ensure header matches current freq axis
            try:
                n = len(freq)
            except Exception:
                n = 0
            desired_header = ['timestamp'] + ([f"{f:.6f}" for f in freq] if n > 0 else [])
            try:
                for ci, val in enumerate(desired_header, start=1):
                    ws.cell(row=1, column=ci, value=val)
            except Exception:
                pass

            for row in buffer:
                ws.append(row)
            wb.save(excel_path)
            buffer.clear()

        def running_flag():
            return getattr(self, '_spectrum_recording', False) and getattr(self, '_spectrum_thread_running', False)

        def worker():
            nonlocal sample_count, last_report_time, last_flush_time, freq
            import pyvisa
            while running_flag():
                try:
                    # Reconnect if session not open
                    if getattr(panel.sa, 'inst', None) is None:
                        try:
                            panel.on_connect()
                        except Exception:
                            pass
                        time.sleep(0.3)
                        continue
                    amplitudes = panel.sa.capture_spectrum()
                    # Refresh axis if needed
                    try:
                        n_freq = len(freq)
                    except Exception:
                        n_freq = 0
                    if not n_freq or (hasattr(amplitudes, '__len__') and len(amplitudes) != n_freq):
                        try:
                            freq = panel.sa.get_freq_axis(panel.unit_combo.currentText())
                        except Exception:
                            pass
                    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    row = [now] + [float(a) for a in amplitudes]
                    buffer.append(row)
                    sample_count += 1

                    # Flush on count threshold or every ~3 seconds
                    now_ts = time.time()
                    if len(buffer) >= flush_interval or (now_ts - last_flush_time) >= 3.0:
                        flush_buffer()
                        last_flush_time = now_ts
                except pyvisa.errors.InvalidSession:
                    break
                except Exception as e:
                    # Treat common transient VISA errors as recoverable
                    msg = ''
                    try:
                        msg = str(e.args[0]) if getattr(e, 'args', None) else str(e)
                    except Exception:
                        msg = str(e)
                    if any(tok in msg for tok in ['-410', 'Query Interrupted', '-420', 'Query UNTERMINATED', 'Query Unterminated']):
                        try:
                            inst = getattr(panel.sa, 'inst', None)
                            if inst is not None and hasattr(inst, 'clear'):
                                inst.clear()
                        except Exception:
                            pass
                        time.sleep(0.05)
                        continue
                now_time = time.time()
                if now_time - last_report_time >= 2.0:
                    elapsed = now_time - start_time
                    rate_cb(sample_count / elapsed if elapsed > 0 else 0.0)
                    last_report_time = now_time
                time.sleep(0.1)
            flush_buffer()

        self._spectrum_thread = threading.Thread(target=worker, daemon=True)
        self._spectrum_thread.start()

    def _write_bench_info(self, excel_path: str):
        """Create or update a 'Bench Info' sheet with a summary of the bench equipment and settings."""
        from openpyxl import Workbook, load_workbook
        # Gather info from all tabs
        rows = []
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        def parse_serial_from_idn(idn: str) -> str:
            try:
                parts = [p.strip() for p in idn.replace(";", ",").split(',') if p.strip()]
                if len(parts) >= 3:
                    return parts[2]
                # fallback: look for SN or serial tokens
                for tok in parts:
                    if tok.upper().startswith('SN'):
                        return tok.split(':')[-1].strip()
            except Exception:
                pass
            return ''
        for i in range(self.tabs.count()):
            panel = self.tabs.widget(i)
            tab_name = self.tabs.tabText(i)
            # Keithley 2230
            if isinstance(panel, KeithleyPanel):
                inst = getattr(panel, 'inst', None)
                connected = bool(inst)
                resource = ''
                try:
                    resource = panel.resource_edit.text().strip()
                except Exception:
                    pass
                serial = ''
                try:
                    if inst:
                        idn = inst.get_identification()
                        serial = parse_serial_from_idn(idn)
                except Exception:
                    serial = ''
                # Setpoints
                settings = {
                    'ch1': {'V': getattr(panel.vol_edits.get(1), 'text', lambda: '0')()},
                    'ch2': {'V': getattr(panel.vol_edits.get(2), 'text', lambda: '0')()},
                    'ch3': {'V': getattr(panel.vol_edits.get(3), 'text', lambda: '0')()},
                }
                try:
                    settings['ch1']['I'] = panel.iam_edits[1].text()
                    settings['ch2']['I'] = panel.iam_edits[2].text()
                    settings['ch3']['I'] = panel.iam_edits[3].text()
                except Exception:
                    pass
                # Output state
                state_parts = []
                for ch in (1, 2, 3):
                    ch_on = None
                    if connected:
                        try:
                            ch_on = bool(inst.get_output_state(ch))
                        except Exception:
                            ch_on = None
                    state_parts.append(f'ch{ch}:{"on" if ch_on else ("off" if ch_on is not None else "?")}')
                state = ', '.join(state_parts)
                rows.append([ts, 'Keithley 2230', tab_name, resource, serial, 'Yes' if connected else 'No', state, json.dumps(settings)])
            # Keysight E36233A
            elif isinstance(panel, KeysightE36233APanel):
                supply = getattr(panel, 'supply', None)
                connected = bool(supply)
                # Try to deduce resource from name field if nothing else is available
                resource = ''
                try:
                    resource = panel.name_edit.text().strip()
                except Exception:
                    pass
                serial = ''
                try:
                    if supply and getattr(supply, 'inst', None):
                        idn = supply.inst.query("*IDN?")
                        serial = parse_serial_from_idn(idn)
                except Exception:
                    serial = ''
                settings = {'ch1': {}, 'ch2': {}}
                state_parts = []
                for ch in (1, 2):
                    try:
                        settings[f'ch{ch}']['V'] = str(supply.get_voltage_setpoint(ch)) if connected else ''
                    except Exception:
                        pass
                    try:
                        settings[f'ch{ch}']['I'] = str(supply.get_current_setpoint(ch)) if connected else ''
                    except Exception:
                        pass
                    on_val = None
                    try:
                        on_val = bool(supply.get_output_state(ch)) if connected else None
                    except Exception:
                        on_val = None
                    state_parts.append(f'ch{ch}:{"on" if on_val else ("off" if on_val is not None else "?")}')
                state = ', '.join(state_parts)
                rows.append([ts, 'Keysight E36233A', tab_name, resource, serial, 'Yes' if connected else 'No', state, json.dumps(settings)])
            # Keysight EL34243A
            elif isinstance(panel, KeysightELPanel):
                dev = getattr(panel, 'dev', None)
                connected = bool(dev)
                resource = ''
                try:
                    resource = panel.resource_edit.text().strip()
                except Exception:
                    pass
                serial = ''
                try:
                    if dev:
                        idn = dev.get_identification()
                        serial = parse_serial_from_idn(idn)
                except Exception:
                    serial = ''
                settings = {
                    'ch1': {
                        'mode': getattr(panel.mode_combo_ch1, 'currentText', lambda: '')(),
                        'value': getattr(panel.mode_value_ch1, 'text', lambda: '')(),
                    },
                    'ch2': {
                        'mode': getattr(panel.mode_combo_ch2, 'currentText', lambda: '')(),
                        'value': getattr(panel.mode_value_ch2, 'text', lambda: '')(),
                    },
                }
                state = f"ch1:{'on' if panel.input_toggle_ch1.isChecked() else 'off'}, ch2:{'on' if panel.input_toggle_ch2.isChecked() else 'off'}"
                rows.append([ts, 'Keysight EL34243A', tab_name, resource, serial, 'Yes' if connected else 'No', state, json.dumps(settings)])
            # Hittite Sig Gen
            elif isinstance(panel, HittiteSigGenPanel):
                dev = getattr(panel, 'dev', None)
                connected = bool(dev)
                resource = ''
                try:
                    resource = panel.resource_edit.text().strip()
                except Exception:
                    pass
                serial = ''
                try:
                    if dev:
                        idn = dev.get_identification()
                        serial = parse_serial_from_idn(idn)
                except Exception:
                    serial = ''
                unit = getattr(panel.freq_unit_combo, 'currentText', lambda: '')()
                settings = {
                    'frequency': getattr(panel.freq_edit, 'text', lambda: '')(),
                    'freq_unit': unit,
                    'power_dB': getattr(panel.pow_edit, 'text', lambda: '')(),
                }
                state = 'on' if getattr(panel.output_btn, 'isChecked', lambda: False)() else 'off'
                rows.append([ts, 'Hittite Sig Gen', tab_name, resource, serial, 'Yes' if connected else 'No', state, json.dumps(settings)])
            # RhodeSchwarz SMA
            elif isinstance(panel, RhodeSchwarzSMAPanel):
                dev = getattr(panel, 'dev', None)
                connected = bool(dev)
                resource = ''
                try:
                    resource = panel.resource_edit.text().strip()
                except Exception:
                    pass
                serial = ''
                try:
                    if dev:
                        idn = dev.get_identification()
                        serial = parse_serial_from_idn(idn)
                except Exception:
                    serial = ''
                unit = getattr(panel.freq_unit_combo, 'currentText', lambda: '')()
                settings = {
                    'frequency': getattr(panel.freq_edit, 'text', lambda: '')(),
                    'freq_unit': unit,
                    'power_dBm': getattr(panel.pow_edit, 'text', lambda: '')(),
                }
                state = 'on' if getattr(panel.output_btn, 'isChecked', lambda: False)() else 'off'
                rows.append([ts, 'RhodeSchwarz SMA', tab_name, resource, serial, 'Yes' if connected else 'No', state, json.dumps(settings)])
            # Keysight FieldFox
            elif isinstance(panel, FieldFoxSAPanel):
                sa = getattr(panel, 'sa', None)
                connected = bool(getattr(sa, 'inst', None))
                resource = ''
                try:
                    resource = getattr(sa, 'visa_address', '')
                except Exception:
                    pass
                serial = ''
                try:
                    if connected:
                        try:
                            # prefer robust wrapper query if available
                            idn = sa._safe_query("*IDN?") if hasattr(sa, '_safe_query') else sa.inst.query("*IDN?")
                        except Exception:
                            idn = ''
                        serial = parse_serial_from_idn(idn)
                except Exception:
                    serial = ''
                unit = getattr(panel.unit_combo, 'currentText', lambda: '')()
                settings = {
                    'center': getattr(panel.center_edit, 'text', lambda: '')(),
                    'span': getattr(panel.span_edit, 'text', lambda: '')(),
                    'start': getattr(panel.start_edit, 'text', lambda: '')(),
                    'stop': getattr(panel.stop_edit, 'text', lambda: '')(),
                    'unit': unit,
                }
                # Capture thread as state
                running = bool(getattr(panel, '_capture_thread', None))
                state = 'capture:running' if running else 'capture:stopped'
                rows.append([ts, 'Keysight FieldFox', tab_name, resource, serial, 'Yes' if connected else 'No', state, json.dumps(settings)])
        # Write into Excel
        if os.path.exists(excel_path):
            try:
                wb = load_workbook(excel_path)
            except Exception:
                wb = Workbook()
        else:
            wb = Workbook()
        # Replace Bench Info sheet if it exists
        if 'Bench Info' in wb.sheetnames:
            del wb['Bench Info']
        ws = wb.create_sheet('Bench Info')
        header = ['timestamp', 'instrument', 'name', 'resource', 'serial', 'connected', 'state', 'settings']
        ws.append(header)
        for r in rows:
            ws.append(r)
        # If workbook was just created, remove default sheet if empty
        try:
            def_sheet = wb['Sheet']
            if def_sheet.max_row == 1 and def_sheet.max_column == 1 and not def_sheet['A1'].value:
                wb.remove(def_sheet)
        except Exception:
            pass
        wb.save(excel_path)

    def add_instrument_panel(self, resource, label, inst_type):
        """Add a new instrument panel to the tabs based on resource, label, and instrument type."""
        panel = None
        if inst_type == 'Keithley 2230':
            panel = KeithleyPanel(resource)
        elif inst_type == 'Keysight EL34243A':
            panel = KeysightELPanel(resource)
        elif inst_type == 'Keysight E36233A':
            panel = KeysightE36233APanel(resource)
        elif inst_type == 'Hittite Sig Gen':
            panel = HittiteSigGenPanel(resource)
        elif inst_type == 'RhodeSchwarz SMA':
            panel = RhodeSchwarzSMAPanel(resource)
        elif inst_type == 'Keysight FieldFox':
            panel = FieldFoxSAPanel(resource)
        else:
            panel = KeithleyPanel(resource)
        # Ensure a canonical 'resource' attribute exists for all panels so it can be saved
        try:
            if not hasattr(panel, 'resource') or not getattr(panel, 'resource'):
                # FieldFox panel stores address inside panel.sa.visa_address
                if isinstance(panel, FieldFoxSAPanel) and hasattr(panel, 'sa'):
                    panel.resource = panel.sa.visa_address
                else:
                    panel.resource = resource
        except Exception:
            pass
        self.tabs.addTab(panel, label)
        if hasattr(panel, 'resource_edit'):
            panel.resource_edit.setText(resource)
        if hasattr(panel, 'name_edit'):
            panel.name_edit.setText(label)
        if hasattr(panel, 'on_connect'):
            panel.on_connect()
        self._auto_turn_off_panel(panel)

    def get_all_supply_panels(self):
        panels = []
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, (KeithleyPanel, KeysightE36233APanel)):
                panels.append(w)
        return panels

    # Removed global recording buttons and logic; unified record button handles all recording
    # helper to format timestamps for logs
    def _ts(self):
        return datetime.datetime.now().strftime('%H:%M:%S')

    def _log(self, msg: str):
        # Emit through Qt signal to ensure GUI-thread-safe appending
        try:
            self.log_signal.emit(f'[{self._ts()}] {msg}')
        except Exception:
            # Fallback to status bar if no signal yet
            self.statusBar().showMessage(msg, 4000)

    @QtCore.pyqtSlot(str)
    def _append_log(self, txt: str):
        # Append to both logs if present and keep them scrolled
        try:
            if hasattr(self, 'test_log') and self.test_log is not None:
                self.test_log.appendPlainText(txt)
                try:
                    self.test_log.verticalScrollBar().setValue(self.test_log.verticalScrollBar().maximum())
                except Exception:
                    pass
            if hasattr(self, 'program_log') and self.program_log is not None:
                self.program_log.appendPlainText(txt)
                try:
                    self.program_log.verticalScrollBar().setValue(self.program_log.verticalScrollBar().maximum())
                except Exception:
                    pass
        except Exception:
            try:
                self.statusBar().showMessage(txt, 4000)
            except Exception:
                pass

    def on_abort_clicked(self):
        self._sequence_abort_flag = True
        self._log('Abort requested')

    def _auto_turn_off_panel(self, panel):
        """Safely turn off outputs/inputs for a newly added panel."""
        if isinstance(panel, KeithleyPanel) and getattr(panel, 'inst', None):
            for ch in (1, 2, 3):
                try:
                    panel.inst.set_output(ch, False)
                except Exception:
                    pass
            panel.master_out_btn.setChecked(False)
            panel.master_out_btn.setText('All Off')
        elif isinstance(panel, HittiteSigGenPanel) and getattr(panel, 'dev', None):
            try:
                panel.dev.set_output(False)
            except Exception:
                pass
            panel.output_btn.setChecked(False)
            panel.output_btn.setText('Output Off')
        elif isinstance(panel, KeysightELPanel) and getattr(panel, 'dev', None):
            for ch in (1, 2):
                if hasattr(panel, 'ch_enabled') and not panel.ch_enabled[ch].isChecked():
                    continue
                try:
                    panel.dev.set_input(ch, False)
                except Exception:
                    pass
            # Reflect in UI if available
            try:
                if hasattr(panel, '_set_input_toggle_ui'):
                    panel._set_input_toggle_ui(1, False)
                    panel._set_input_toggle_ui(2, False)
            except Exception:
                pass
        elif isinstance(panel, RhodeSchwarzSMAPanel) and getattr(panel, 'dev', None):
            try:
                panel.dev.set_output(False)
            except Exception:
                pass
            panel.output_btn.setChecked(False)
            panel.output_btn.setText('Output Off')
        elif isinstance(panel, FieldFoxSAPanel) and getattr(panel, 'dev', None):
            try:
                panel.dev.set_output(False)
            except Exception:
                pass
            panel.output_btn.setChecked(False)
            panel.output_btn.setText('Output Off')

    def _find_replacement_candidates(self, saved_resource: str, inst_type_hint: str, rm: pyvisa.ResourceManager = None) -> List[Tuple[str, str, str]]:
        """Return list of (label, resource, inst_type) candidates matching inst_type_hint."""
        candidates: List[Tuple[str, str, str]] = []
        if rm is None:
            try:
                rm = pyvisa.ResourceManager()
            except Exception:
                return candidates
        try:
            resources = rm.list_resources()
        except Exception:
            return candidates
        for res in resources:
            try:
                dev = rm.open_resource(res, timeout=1000)
                try:
                    idn = dev.query('*IDN?')
                except Exception:
                    idn = ''
                finally:
                    try:
                        dev.close()
                    except Exception:
                        pass
                lidn = idn.upper()
                inst_type = 'Unknown'
                if 'KEITHLEY' in lidn or '2230' in lidn:
                    inst_type = 'Keithley 2230'
                elif 'EL34243' in lidn or ('KEYSIGHT' in lidn and 'ELECTRONIC LOAD' in lidn):
                    inst_type = 'Keysight EL34243A'
                elif 'E36233A' in lidn:
                    inst_type = 'Keysight E36233A'
                elif 'HITTITE' in lidn or 'SIG GEN' in lidn:
                    inst_type = 'Hittite Sig Gen'
                elif 'ROHDE' in lidn or 'SCHWARZ' in lidn or 'SMA' in lidn:
                    inst_type = 'RhodeSchwarz SMA'
                elif 'FIELDFOX' in lidn or 'FIELD FOX' in lidn:
                    inst_type = 'Keysight FieldFox'
                if inst_type_hint and inst_type_hint.split()[0] == inst_type.split()[0]:
                    candidates.append((res.split('::')[3] if '::' in res else res, res, inst_type))
                elif inst_type == inst_type_hint:
                    candidates.append((res.split('::')[3] if '::' in res else res, res, inst_type))
            except Exception:
                continue
        return candidates
    
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
                    elif isinstance(widget, KeysightELPanel):
                        if widget.dev:
                            for ch in (1, 2):
                                if hasattr(widget, 'ch_enabled') and not widget.ch_enabled[ch].isChecked():
                                    continue
                                try:
                                    mode = (widget.mode_combo_ch1.currentText() if ch == 1 else widget.mode_combo_ch2.currentText())
                                    try:
                                        value = float(widget.mode_value_ch1.text() if ch == 1 else widget.mode_value_ch2.text())
                                    except Exception:
                                        value = 0.0
                                    widget.dev.set_mode(ch, mode)
                                    widget.dev.set_parameter(ch, mode, value)
                                    widget.dev.set_input(ch, True)
                                    if hasattr(widget, '_set_input_toggle_ui'):
                                        widget._set_input_toggle_ui(ch, True)
                                except Exception:
                                    pass
                    elif isinstance(widget, RhodeSchwarzSMAPanel):
                        if widget.dev:
                            try:
                                widget.dev.set_output(True)
                                widget.output_btn.setChecked(True)
                                widget.output_btn.setText('Output On')
                                widget.status_label.setText('Output ON')
                            except Exception as e:
                                widget.status_label.setText(f'Failed to set output: {e}')
                    elif isinstance(widget, FieldFoxSAPanel):
                        if widget.dev:
                            try:
                                widget.dev.set_output(True)
                                widget.output_btn.setChecked(True)
                                widget.output_btn.setText('Output On')
                                widget.status_label.setText('Output ON')
                            except Exception as e:
                                widget.status_label.setText(f'Failed to set output: {e}')
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
                    elif isinstance(widget, KeysightELPanel):
                        if widget.dev:
                            for ch in (1, 2):
                                if hasattr(widget, 'ch_enabled') and not widget.ch_enabled[ch].isChecked():
                                    continue
                                try:
                                    widget.dev.set_input(ch, False)
                                    if hasattr(widget, '_set_input_toggle_ui'):
                                        widget._set_input_toggle_ui(ch, False)
                                except Exception:
                                    pass
                    elif isinstance(widget, RhodeSchwarzSMAPanel):
                        if widget.dev:
                            try:
                                widget.dev.set_output(False)
                                widget.output_btn.setChecked(False)
                                widget.output_btn.setText('Output Off')
                                widget.status_label.setText('Output OFF')
                            except Exception as e:
                                widget.status_label.setText(f'Failed to set output: {e}')
                    elif isinstance(widget, FieldFoxSAPanel):
                        if widget.dev:
                            try:
                                widget.dev.set_output(False)
                                widget.output_btn.setChecked(False)
                                widget.output_btn.setText('Output Off')
                                widget.status_label.setText('Output OFF')
                            except Exception as e:
                                widget.status_label.setText(f'Failed to set output: {e}')
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
                self._log('Using configured power-up sequence for hard reset')
                if hasattr(self, 'test_power_toggle_btn'):
                    self.test_power_toggle_btn.setChecked(True)
                    self._update_test_power_toggle_btn(True)
                # run sequence then Soft Reset when complete
                def after_seq():
                    try:
                        self.soft_reset()
                    except Exception:
                        pass
                self._run_power_sequence(on_complete=after_seq)
            else:
                self._log('No sequence configured; powering all instruments ON then Soft Reset')
                self.power_on_all()
                try:
                    self.soft_reset()
                except Exception:
                    pass
        QtCore.QTimer.singleShot(int(delay * 1000), _do_power_on)
        self.statusBar().showMessage(f'Reset part: powered off, will power on in {delay} seconds', 4000)
    
    def __init__(self):
        super().__init__()
        # Apple liquid glass design stylesheet
        self.setStyleSheet('''
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e3eafc, stop:1 #cfd9df);
            }
            QWidget {
                background: rgba(255,255,255,0.7);
                border-radius: 16px;
                font-family: "Segoe UI", "San Francisco", Arial, sans-serif;
                font-size: 15px;
                color: #222;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: rgba(255,255,255,0.6);
                border-radius: 12px;
                padding: 8px 24px;
                margin: 4px;
                font-weight: 500;
                color: #222;
                min-width: 140px; /* ensure long labels like 'Programming' are fully visible */
                border: 1px solid rgba(0,0,0,0.15); /* subtle outline for rounded tab */
            }
            QTabBar::tab:selected {
                background: rgba(255,255,255,0.85);
                color: #007aff;
                border: 1px solid #b6c2ce; 
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fafdff, stop:1 #e3eafc);
                border-radius: 12px;
                border: 1px solid #d1d5db;
                padding: 8px 20px;
                font-size: 15px;
                color: #222;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #e3eafc;
                color: #007aff;
            }
            QPushButton:pressed {
                background: #cfd9df;
                color: #007aff;
            }
            QCheckBox {
                font-size: 15px;
                padding: 4px 12px;
                border-radius: 8px;
                background: rgba(255,255,255,0.5);
            }
            QLabel {
                font-size: 15px;
                color: #222;
                background: transparent;
            }
            QLineEdit {
                background: rgba(255,255,255,0.8);
                border-radius: 8px;
                border: 1px solid #d1d5db;
                padding: 6px 12px;
                font-size: 15px;
            }
            QPlainTextEdit {
                background: rgba(255,255,255,0.8);
                border-radius: 12px;
                border: 1px solid #d1d5db;
                font-size: 15px;
                padding: 8px;
            }
            QComboBox {
                background: rgba(255,255,255,0.8);
                border-radius: 8px;
                border: 1px solid #d1d5db;
                font-size: 15px;
                padding: 6px 12px;
            }
            QStatusBar {
                background: rgba(255,255,255,0.6);
                border-top: 1px solid #d1d5db;
                font-size: 14px;
                color: #222;
            }
        ''')
        # runtime control state for sequencing/program runs
        self._sequence_abort_flag = False
        self.program_process = None
        self._program_tempfile = None
        self._logic_thread = None
        self._logic_poll_timer = None
        self._logic_abort = False
        # programming logic directory (external logic files for Configure Part)
        try:
            self.program_logic_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'programming logics')
            os.makedirs(self.program_logic_dir, exist_ok=True)
        except Exception:
            self.program_logic_dir = os.path.dirname(__file__)
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

        # Connect logger signal to UI appender
        try:
            self.log_signal.connect(self._append_log)
        except Exception:
            pass

        # --- Test Tab ---
        test_widget = QtWidgets.QWidget()
        test_layout = QtWidgets.QVBoxLayout(test_widget)



    # (Removed duplicate Test tab UI block. All UI code is inside __init__ with correct indentation.)

        # Power sequence builder (wrapper)
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

        # Run log is presented on the Test tab (live updates via self._log)

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

        # Configure Part row only (select logic file and run)
        cfg_row = QtWidgets.QHBoxLayout()
        self.logic_combo = QtWidgets.QComboBox()
        self.logic_combo.setMinimumWidth(420)
        self._refresh_logic_combo()
        cfg_row.addWidget(QtWidgets.QLabel('Logic file:'))
        cfg_row.addWidget(self.logic_combo, 1)
        self.logic_browse_btn = QtWidgets.QPushButton('Browse…')
        self.logic_browse_btn.clicked.connect(self._browse_logic_file)
        cfg_row.addWidget(self.logic_browse_btn)
        self.configure_part_btn = QtWidgets.QPushButton('Configure Part')
        self.configure_part_btn.clicked.connect(self.on_configure_part_clicked)
        cfg_row.addWidget(self.configure_part_btn)
        prog_layout.addLayout(cfg_row)

        # Programming tab run log (live)
        prog_layout.addWidget(QtWidgets.QLabel('Run Log:'))
        self.program_log = QtWidgets.QPlainTextEdit()
        self.program_log.setReadOnly(True)
        self.program_log.setMaximumHeight(220)
        prog_layout.addWidget(self.program_log)

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
        if hasattr(self, '_update_test_power_toggle_btn'):
            self._update_test_power_toggle_btn(False)
        tpower_row.addWidget(self.test_tab_power_btn)
        test2_layout.addLayout(tpower_row)

        # --- Unified Record Controls ---
        record_row = QtWidgets.QHBoxLayout()
        self.record_btn = QtWidgets.QPushButton('Record')
        self.record_btn.setCheckable(True)
        self.record_btn.setChecked(False)
        self.record_btn.clicked.connect(self.on_record_clicked)
        record_row.addWidget(self.record_btn)
        self.supply_record_toggle = QtWidgets.QCheckBox('Supply')
        self.supply_record_toggle.setChecked(True)
        record_row.addWidget(self.supply_record_toggle)
        self.spectrum_record_toggle = QtWidgets.QCheckBox('Spectrum')
        self.spectrum_record_toggle.setChecked(False)
        record_row.addWidget(self.spectrum_record_toggle)
        # Register recording toggle
        self.register_record_toggle = QtWidgets.QCheckBox('Register')
        self.register_record_toggle.setChecked(False)
        record_row.addWidget(self.register_record_toggle)
        self.supply_read_speed_label = QtWidgets.QLabel('Supply Sample Rate: --')
        self.spectrum_read_speed_label = QtWidgets.QLabel('Spectrum Sample Rate: --')
        self.register_read_speed_label = QtWidgets.QLabel('Register Sample Rate: --')
        record_row.addWidget(self.supply_read_speed_label)
        record_row.addWidget(self.spectrum_read_speed_label)
        record_row.addWidget(self.register_read_speed_label)
        # Add more toggles here for future metrics
        test2_layout.addLayout(record_row)

        # Soft Reset button (runs Configure Part logic)
        prog_row = QtWidgets.QHBoxLayout()
        self.program_now_btn = QtWidgets.QPushButton('Soft Reset')
        self.program_now_btn.clicked.connect(self.soft_reset)
        prog_row.addWidget(self.program_now_btn)
        test2_layout.addLayout(prog_row)

        # Reset controls
        reset_row = QtWidgets.QHBoxLayout()
        reset_row.addWidget(QtWidgets.QLabel('Reset delay (s):'))
        self.reset_delay_edit = QtWidgets.QLineEdit('2.0')
        self.reset_delay_edit.setMaximumWidth(80)
        reset_row.addWidget(self.reset_delay_edit)
        self.reset_btn = QtWidgets.QPushButton('Hard Reset')
        self.reset_btn.clicked.connect(self.reset_part)
        reset_row.addWidget(self.reset_btn)
        test2_layout.addLayout(reset_row)

        # Live run log for Configure Part
        test2_layout.addWidget(QtWidgets.QLabel('Run Log:'))
        self.test_log = QtWidgets.QPlainTextEdit()
        self.test_log.setReadOnly(True)
        self.test_log.setMaximumHeight(220)
        test2_layout.addWidget(self.test_log)

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

    def power_off_all(self):
        """Turn off outputs/inputs for all instruments in tabs."""
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, KeithleyPanel):
                self._keithley_apply_settings(widget, False)
            elif isinstance(widget, HittiteSigGenPanel):
                self._generic_output_toggle(widget, False)
            elif isinstance(widget, KeysightELPanel):
                self._keysight_el_apply_settings(widget, False)
            elif isinstance(widget, RhodeSchwarzSMAPanel):
                self._generic_output_toggle(widget, False)
            elif isinstance(widget, FieldFoxSAPanel):
                self._generic_output_toggle(widget, False)
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
                self._keithley_apply_settings(widget, True)
            elif isinstance(widget, HittiteSigGenPanel):
                self._generic_output_toggle(widget, True)
            elif isinstance(widget, KeysightELPanel):
                self._keysight_el_apply_settings(widget, True)
            elif isinstance(widget, RhodeSchwarzSMAPanel):
                self._generic_output_toggle(widget, True)
            elif isinstance(widget, FieldFoxSAPanel):
                self._generic_output_toggle(widget, True)
        if hasattr(self, 'test_power_toggle_btn'):
            self.test_power_toggle_btn.setChecked(True)
            self._update_test_power_toggle_btn(True)
        self._update_global_power_btns(True)
        self.statusBar().showMessage('All instrument outputs/inputs turned ON', 4000)

    def refresh_configs_list(self):
        self.load_combo.clear()
        files = [f for f in os.listdir(self.configs_dir) if f.lower().endswith('.json')]
        for f in files:
            self.load_combo.addItem(f)
        if files:
            self.load_combo.setCurrentIndex(0)

    def disconnect_all_instruments(self):
        """Cleanly stop recordings, disconnect/clear all panels and instruments, and remove tabs.
        This prevents VISA/SCPI contention when loading a new config (e.g., FieldFox double-connect).
        """
        try:
            self.statusBar().showMessage('Disconnecting all instruments…', 3000)
        except Exception:
            pass
        # Stop any ongoing recordings first
        try:
            # If Record toggle is on, untoggle it for UI consistency
            if hasattr(self, 'record_btn') and self.record_btn.isChecked():
                try:
                    self.record_btn.setChecked(False)
                except Exception:
                    pass
            self._stop_all_recordings()
        except Exception:
            pass
        # Iterate tabs backwards: close panels and remove tabs
        try:
            for i in range(self.tabs.count() - 1, -1, -1):
                w = self.tabs.widget(i)
                # Try to turn off outputs/inputs first (best-effort)
                try:
                    if isinstance(w, KeithleyPanel):
                        self._keithley_apply_settings(w, False)
                    elif isinstance(w, KeysightELPanel):
                        self._keysight_el_apply_settings(w, False)
                    elif isinstance(w, (HittiteSigGenPanel, RhodeSchwarzSMAPanel, FieldFoxSAPanel)):
                        self._generic_output_toggle(w, False)
                except Exception:
                    pass
                # Close panel (panels should release VISA sessions/threads in close())
                try:
                    if hasattr(w, 'close'):
                        w.close()
                except Exception:
                    pass
                # As a fallback, try to close raw instrument handles
                try:
                    for attr in ('inst', 'dev', 'sa'):
                        obj = getattr(w, attr, None)
                        if obj is None:
                            continue
                        # FieldFox wrapper: has close()
                        if hasattr(obj, 'close'):
                            try:
                                obj.close()
                            except Exception:
                                pass
                        # VISA instrument directly
                        if hasattr(obj, 'inst') and hasattr(obj.inst, 'close'):
                            try:
                                obj.inst.close()
                            except Exception:
                                pass
                except Exception:
                    pass
                # Remove tab
                try:
                    self.tabs.removeTab(i)
                except Exception:
                    pass
        except Exception:
            pass
        # Small yield to let timers/threads settle
        try:
            QtWidgets.QApplication.processEvents()
        except Exception:
            pass

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
            # Determine panel type
            if isinstance(widget, KeithleyPanel):
                tab_type = 'Keithley 2230'
            elif isinstance(widget, KeysightELPanel):
                tab_type = 'Keysight EL34243A'
            elif isinstance(widget, KeysightE36233APanel):
                tab_type = 'Keysight E36233A'
            elif isinstance(widget, HittiteSigGenPanel):
                tab_type = 'Hittite Sig Gen'
            elif isinstance(widget, RhodeSchwarzSMAPanel):
                tab_type = 'RhodeSchwarz SMA'
            elif isinstance(widget, FieldFoxSAPanel):
                tab_type = 'Keysight FieldFox'
            else:
                tab_type = 'Unknown'
            # determine a saved name: prefer the editable name if present, otherwise the current tab text
            try:
                if hasattr(widget, 'name_edit') and widget.name_edit.text().strip():
                    saved_name = widget.name_edit.text().strip()
                else:
                    saved_name = self.tabs.tabText(i)
            except Exception:
                try:
                    saved_name = self.tabs.tabText(i)
                except Exception:
                    saved_name = ''
            # Robust resource determination (FieldFox panel may not expose 'resource' attribute)
            resource_val = getattr(widget, 'resource', '')
            if (not resource_val) and isinstance(widget, FieldFoxSAPanel) and hasattr(widget, 'sa'):
                try:
                    resource_val = getattr(widget.sa, 'visa_address', '')
                except Exception:
                    resource_val = ''
            entry = {'type': tab_type, 'resource': resource_val, 'name': saved_name}
            # Save per-panel attributes
            if isinstance(widget, KeithleyPanel):
                entry['channels'] = {}
                for ch in (1, 2, 3):
                    entry['channels'][ch] = {
                        'voltage': widget.vol_edits[ch].text(),
                        'current': widget.iam_edits[ch].text(),
                        'output': widget.master_out_btn.isChecked()
                    }
            elif isinstance(widget, KeysightELPanel):
                entry['channels'] = {}
                for ch in (1, 2):
                    # Read per-channel UI
                    mode = (widget.mode_combo_ch1.currentText() if ch == 1 else widget.mode_combo_ch2.currentText())
                    value = (widget.mode_value_ch1.text() if ch == 1 else widget.mode_value_ch2.text())
                    # Determine input state: prefer device state if connected
                    inp = False
                    try:
                        if getattr(widget, 'dev', None):
                            inp = bool(widget.dev.get_input_state(ch))
                        elif hasattr(widget, '_get_input_toggle_ui'):
                            inp = bool(widget._get_input_toggle_ui(ch))
                    except Exception:
                        pass
                    entry['channels'][ch] = {
                        'mode': mode,
                        'value': value,
                        'input': inp
                    }
            elif isinstance(widget, KeysightE36233APanel):
                entry['channels'] = {}
                for ch in (1, 2):
                    entry['channels'][ch] = {
                        'voltage': widget.voltage_edit.text(),
                        'current': widget.current_edit.text(),
                        'output': widget.onoff_btn.isChecked()
                    }
            elif isinstance(widget, HittiteSigGenPanel):
                # Save frequency (value + unit if separated) and power + output state if available
                try:
                    entry['settings'] = {
                        'frequency': getattr(widget, 'freq_edit', None).text() if hasattr(widget, 'freq_edit') else '',
                        'freq_unit': getattr(widget, 'freq_unit_combo', None).currentText() if hasattr(widget, 'freq_unit_combo') else 'MHz',
                        'power': getattr(widget, 'pow_edit', None).text() if hasattr(widget, 'pow_edit') else '',
                        'output': getattr(widget, 'output_btn', None).isChecked() if hasattr(widget, 'output_btn') else False
                    }
                except Exception:
                    pass
            # FieldFox SA panel settings
            if isinstance(widget, FieldFoxSAPanel):
                entry['settings'] = {
                    'center': widget.center_edit.text(),
                    'span': widget.span_edit.text(),
                    'start': widget.start_edit.text(),
                    'stop': widget.stop_edit.text(),
                    'unit': widget.unit_combo.currentText()
                }
            # RhodeSchwarz SMA panel settings
            if isinstance(widget, RhodeSchwarzSMAPanel):
                entry['settings'] = {
                    'frequency': widget.freq_edit.text(),
                    'freq_unit': widget.freq_unit_combo.currentText(),
                    'power': widget.pow_edit.text(),
                    'output': widget.output_btn.isChecked()
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
            'program_logic_path': self._get_selected_logic_path(),
            'register_read_array': getattr(self, 'register_read_array', [])
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
        # Proactively disconnect and clear any existing instruments/panels
        try:
            self.disconnect_all_instruments()
        except Exception:
            # Fallback: remove tabs if disconnect failed
            while self.tabs.count():
                try:
                    self.tabs.removeTab(0)
                except Exception:
                    break

        # Read config file and extract instruments, sequence, use_sequence
        content = None
        if not os.path.exists(path):
            QtWidgets.QMessageBox.information(self, 'No config', f'Config file not found: {path}')
            return
        try:
            with open(path, 'r') as f:
                content = json.load(f)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Load failed', str(e))
            content = None

        # Build current VISA resource list to support substitutions
        try:
            rm_for_load = pyvisa.ResourceManager()
            current_resources = list(rm_for_load.list_resources())
        except Exception:
            rm_for_load = None
            current_resources = []

        # Backwards compatibility: older configs were lists of instruments
        if content is None:
            instruments = []
            sequence = []
            use_sequence = False
        elif isinstance(content, list):
            instruments = content
            sequence = []
            use_sequence = False
        else:
            instruments = content.get('instruments', [])
            sequence = content.get('sequence', [])
            use_sequence = content.get('use_sequence', False)
            # restore selected program logic file if present
            try:
                logic_path = content.get('program_logic_path', '')
                if logic_path:
                    self._ensure_logic_in_combo(logic_path)
            except Exception:
                pass
            # load register list if present
            try:
                self.register_read_array = content.get('register_read_array', [])
            except Exception:
                self.register_read_array = []

        used_resources = set()
        for entry in instruments:
            inst_type = entry.get('type', 'Keithley 2230')
            # Heuristic reclassification for legacy configs where Hittite was saved as 'Unknown'
            if inst_type == 'Unknown':
                name_l = entry.get('name', '').lower()
                # Prefer explicit name cues
                if any(k in name_l for k in ['hittite', 'sig', 'signal']):
                    inst_type = 'Hittite Sig Gen'
                elif any(k in name_l for k in ['rohde', 'schwarz', 'sma', 'rs ']):
                    inst_type = 'RhodeSchwarz SMA'
            resource = entry.get('resource', '')
            # For FieldFox: if resource not available, auto-connect to another available FieldFox
            if inst_type == 'Keysight FieldFox' and (not resource or resource not in current_resources):
                # Attempt automatic substitution without prompting the user.
                try:
                    candidates = self._find_replacement_candidates(resource, inst_type, rm_for_load)
                except Exception:
                    candidates = []
                if not candidates:
                    # Fresh scan (in case initial resource list was stale)
                    try:
                        fresh_rm = pyvisa.ResourceManager()
                        for res in fresh_rm.list_resources():
                            try:
                                dev = fresh_rm.open_resource(res, timeout=200)
                                try:
                                    idn = dev.query('*IDN?').upper()
                                except Exception:
                                    idn = ''
                                finally:
                                    try:
                                        dev.close()
                                    except Exception:
                                        pass
                                if any(k in idn for k in ['FIELDFOX','N99','HANDHELD SPECTRUM','N991','N992','N993','N994']):
                                    candidates.append((res.split('::')[3] if '::' in res else res, res, 'Keysight FieldFox'))
                                    # don't break; gather all then pick first to allow future heuristics
                            except Exception:
                                continue
                    except Exception:
                        pass
                if candidates:
                    resource = candidates[0][1]
                    self.statusBar().showMessage(f'FieldFox resource missing; auto-connected to: {resource}', 5000)
                else:
                    # No FieldFox found; skip silently with status message.
                    self.statusBar().showMessage('FieldFox from config not found; no FieldFox detected to substitute (skipped).', 5000)
                    continue
            elif resource and resource not in current_resources:
                try:
                    candidates = self._find_replacement_candidates(resource, inst_type, rm_for_load)
                except Exception:
                    candidates = []
                if candidates:
                    items = [f'{c[2]}    ({c[1]})' for c in candidates]
                    item, ok = QtWidgets.QInputDialog.getItem(
                        self, 'Substitute instrument',
                        f'Original resource not found: {resource}\nSelect substitute or Cancel to abort load:', items, 0, False)
                    if not ok:
                        QtWidgets.QMessageBox.information(self, 'Load cancelled', 'Loading cancelled by user')
                        return
                    sel_idx = items.index(item)
                    resource = candidates[sel_idx][1]
                else:
                    resp = QtWidgets.QMessageBox.question(
                        self, 'Instrument missing',
                        f'Instrument {resource} of type {inst_type} not found and no replacements available.\nSkip this instrument? (No = cancel load)',
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
                    if resp == QtWidgets.QMessageBox.No:
                        return
                    else:
                        continue
            # Always add FieldFox panel if type matches, even if resource is missing or not detected
            panel = None
            if resource and resource in used_resources:
                for i in range(self.tabs.count()):
                    w = self.tabs.widget(i)
                    if getattr(w, 'resource', None) == resource:
                        panel = w
                        break
            if panel is None:
                if inst_type == 'Keithley 2230':
                    panel = KeithleyPanel(resource)
                elif inst_type == 'Keysight EL34243A':
                    panel = KeysightELPanel(resource)
                elif inst_type == 'Keysight E36233A':
                    panel = KeysightE36233APanel(resource)
                elif inst_type == 'Hittite Sig Gen':
                    panel = HittiteSigGenPanel(resource)
                elif inst_type == 'RhodeSchwarz SMA':
                    panel = RhodeSchwarzSMAPanel(resource)
                elif inst_type == 'Keysight FieldFox':
                    # Use resource or fallback to name if missing
                    visa_addr = resource if resource else entry.get('name', 'FieldFox')
                    panel = FieldFoxSAPanel(visa_addr)
                else:
                    panel = KeithleyPanel(resource)
                tab_label = entry.get('name', resource)
                self.tabs.addTab(panel, tab_label)
                used_resources.add(resource)
                if hasattr(panel, 'resource_edit'):
                    panel.resource_edit.setText(resource)
                if hasattr(panel, 'name_edit'):
                    panel.name_edit.setText(tab_label)
                name_val = entry.get('name') if isinstance(entry, dict) else None
                if name_val and hasattr(panel, 'name_edit'):
                    panel.name_edit.setText(name_val)
                # Auto-connect panel after loading
                if hasattr(panel, 'on_connect'):
                    try:
                        # For FieldFox, defer connection to the FieldFox settings block below
                        if inst_type != 'Keysight FieldFox':
                            panel.on_connect()
                    except Exception:
                        pass
                # Set panel values from config
                if inst_type == 'Keithley 2230':
                    for ch in (1, 2, 3):
                        ch_cfg = entry.get('channels', {}).get(str(ch)) or entry.get('channels', {}).get(ch)
                        if ch_cfg:
                            try:
                                panel.vol_edits[ch].setText(str(ch_cfg.get('voltage', '0')))
                                panel.iam_edits[ch].setText(str(ch_cfg.get('current', '0.03')))
                                panel.master_out_btn.setChecked(bool(ch_cfg.get('output', False)))
                                panel.master_out_btn.setText('All On' if ch_cfg.get('output', False) else 'All Off')
                                # Set instrument output state if connected
                                if getattr(panel, 'inst', None):
                                    panel.inst.set_voltage(ch, float(ch_cfg.get('voltage', '0')))
                                    panel.inst.set_current(ch, float(ch_cfg.get('current', '0.03')))
                                    panel.inst.set_output(ch, bool(ch_cfg.get('output', False)))
                            except Exception:
                                pass
                elif inst_type == 'Keysight EL34243A':
                    # Apply saved per-channel settings directly to the existing panel
                    tab_label = entry.get('name', resource)
                    if hasattr(panel, 'resource_edit'):
                        panel.resource_edit.setText(resource)
                    if hasattr(panel, 'name_edit'):
                        panel.name_edit.setText(tab_label)
                    try:
                        name_val = entry.get('name') if isinstance(entry, dict) else None
                        if name_val and hasattr(panel, 'name_edit'):
                            panel.name_edit.setText(name_val)
                    except Exception:
                        pass
                    # Apply saved channel settings (mode/value/input) for ch 1 and 2
                    try:
                        ch_cfgs = entry.get('channels', {})
                        for ch in (1, 2):
                            ch_cfg = ch_cfgs.get(str(ch)) or ch_cfgs.get(ch)
                            if not ch_cfg:
                                continue
                            # Update per-channel UI fields
                            try:
                                if hasattr(panel, 'mode_combo_ch1') and hasattr(panel, 'mode_combo_ch2'):
                                    combo = panel.mode_combo_ch1 if ch == 1 else panel.mode_combo_ch2
                                    if ch_cfg.get('mode'):
                                        idx = combo.findText(str(ch_cfg.get('mode')))
                                        if idx != -1:
                                            combo.setCurrentIndex(idx)
                                if hasattr(panel, 'mode_value_ch1') and hasattr(panel, 'mode_value_ch2') and (ch_cfg.get('value') is not None):
                                    (panel.mode_value_ch1 if ch == 1 else panel.mode_value_ch2).setText(str(ch_cfg.get('value')))
                            except Exception:
                                pass
                            # Apply to hardware if connected
                            if getattr(panel, 'dev', None):
                                try:
                                    mode = str(ch_cfg.get('mode', 'CC'))
                                    try:
                                        value = float(ch_cfg.get('value', '0'))
                                    except Exception:
                                        value = 0.0
                                    panel.dev.set_mode(ch, mode)
                                    panel.dev.set_parameter(ch, mode, value)
                                except Exception:
                                    pass
                                # Input state
                                try:
                                    inp = bool(ch_cfg.get('input', False))
                                    panel.dev.set_input(ch, inp)
                                    if hasattr(panel, '_set_input_toggle_ui'):
                                        panel._set_input_toggle_ui(ch, inp)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                elif inst_type == 'RhodeSchwarz SMA':
                    # Restore Rhode & Schwarz SMA generator settings
                    try:
                        settings = entry.get('settings', {})
                        freq = settings.get('frequency')
                        freq_unit = settings.get('freq_unit')
                        power = settings.get('power')
                        output_state = settings.get('output', False)
                        # Apply GUI state
                        if freq is not None and hasattr(panel, 'freq_edit'):
                            panel.freq_edit.setText(str(freq))
                        if freq_unit and hasattr(panel, 'freq_unit_combo'):
                            idx = panel.freq_unit_combo.findText(str(freq_unit))
                            if idx != -1:
                                panel.freq_unit_combo.setCurrentIndex(idx)
                        if power is not None and hasattr(panel, 'pow_edit'):
                            panel.pow_edit.setText(str(power))
                        if hasattr(panel, 'output_btn'):
                            panel.output_btn.setChecked(bool(output_state))
                            panel.output_btn.setText('Output On' if output_state else 'Output Off')
                        # Defer hardware apply to allow connect handshake
                        def apply_sma_hw():
                            if getattr(panel, 'dev', None):
                                try:
                                    # frequency value is entered along with unit; convert
                                    try:
                                        freq_val = float(panel.freq_edit.text())
                                        unit = panel.freq_unit_combo.currentText()
                                        mult = {'GHz':1e9,'MHz':1e6,'KHz':1e3,'Hz':1}.get(unit,1)
                                        panel.dev.set_frequency(freq_val * mult)
                                    except Exception:
                                        pass
                                    if power is not None:
                                        try:
                                            panel.dev.set_power(float(power))
                                        except Exception:
                                            pass
                                    panel.dev.set_output(bool(output_state))
                                except Exception:
                                    pass
                        QtCore.QTimer.singleShot(1200, apply_sma_hw)
                    except Exception:
                        pass
                elif inst_type == 'Hittite Sig Gen':
                    # Restore Hittite signal generator settings
                    try:
                        settings = entry.get('settings', {})
                        freq = settings.get('frequency')
                        freq_unit = settings.get('freq_unit')
                        power = settings.get('power')
                        output_state = settings.get('output', False)
                        if freq is not None and hasattr(panel, 'freq_edit'):
                            panel.freq_edit.setText(str(freq))
                        if freq_unit and hasattr(panel, 'freq_unit_combo'):
                            idx = panel.freq_unit_combo.findText(str(freq_unit))
                            if idx != -1:
                                panel.freq_unit_combo.setCurrentIndex(idx)
                        if power is not None and hasattr(panel, 'pow_edit'):
                            panel.pow_edit.setText(str(power))
                        if hasattr(panel, 'output_btn'):
                            panel.output_btn.setChecked(bool(output_state))
                            panel.output_btn.setText('Output On' if output_state else 'Output Off')
                        def apply_hittite_hw():
                            if getattr(panel, 'dev', None):
                                try:
                                    # Prefer panel helper methods if available
                                    if hasattr(panel, 'on_set_frequency') and hasattr(panel, 'freq_edit'):
                                        try:
                                            panel.on_set_frequency()
                                        except Exception:
                                            pass
                                    if power is not None and hasattr(panel, 'on_set_power'):
                                        try:
                                            panel.on_set_power()
                                        except Exception:
                                            pass
                                    if hasattr(panel, 'dev') and hasattr(panel, 'output_btn'):
                                        try:
                                            panel.dev.set_output(bool(output_state))
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                        QtCore.QTimer.singleShot(1500, apply_hittite_hw)
                    except Exception:
                        pass
                elif inst_type == 'Keysight FieldFox':
                    try:
                        settings = entry.get('settings', {})
                        center = settings.get('center')
                        span = settings.get('span')
                        start = settings.get('start')
                        stop = settings.get('stop')
                        unit = settings.get('unit')
                        if center is not None:
                            panel.center_edit.setText(str(center))
                        if span is not None:
                            panel.span_edit.setText(str(span))
                        if start is not None:
                            panel.start_edit.setText(str(start))
                        if stop is not None:
                            panel.stop_edit.setText(str(stop))
                        if unit is not None:
                            idx = panel.unit_combo.findText(str(unit))
                            if idx != -1:
                                panel.unit_combo.setCurrentIndex(idx)
                        # Ensure connection and capture thread start after short delay
                        def attempt(idx=0):
                            try:
                                # If already connected, don't re-connect
                                if getattr(panel.sa, 'inst', None) is None and hasattr(panel, 'on_connect'):
                                    panel.on_connect()
                                if getattr(panel.sa, 'inst', None) is None:
                                    raise RuntimeError('Not connected yet')
                                # Clear pending I/O and sync once before applying settings
                                try:
                                    inst = getattr(panel.sa, 'inst', None)
                                    if inst is not None and hasattr(inst, 'clear'):
                                        inst.clear()
                                except Exception:
                                    pass
                                try:
                                    if hasattr(panel.sa, 'sync'):
                                        panel.sa.sync()
                                except Exception:
                                    pass
                                try:
                                    panel.apply_settings()
                                except Exception:
                                    pass
                                # Start capture thread if not already running (idempotent)
                                try:
                                    panel.start_capture_thread()
                                except Exception:
                                    pass
                                return  # success
                            except Exception:
                                pass
                            # retry up to 5 times
                            if idx < 5:
                                QtCore.QTimer.singleShot(500, lambda: attempt(idx+1))
                        QtCore.QTimer.singleShot(400, attempt)
                    except Exception:
                        pass
            # Tab name update logic (no label reference)
            def update_tab_name(panel=panel, resource=resource):
                idx = self.tabs.indexOf(panel)
                if idx != -1:
                    self.tabs.setTabText(idx, getattr(panel, 'name_edit', None).text() if hasattr(panel, 'name_edit') else resource)
            if hasattr(panel, 'name_edit'):
                panel.name_edit.textChanged.connect(lambda: update_tab_name(panel, resource))
                if hasattr(self, 'power_seq_builder'):
                    try:
                        self.power_seq_builder.refresh_instr_combo()
                    except Exception:
                        pass
            update_tab_name(panel, resource)
            self._auto_turn_off_panel(panel)

        # After loading tabs, refresh logic list from disk
        try:
            self._refresh_logic_combo()
        except Exception:
            pass
        # remember last loaded config path for use during recording
        try:
            self._last_loaded_config_path = path
        except Exception:
            pass
    
    def _refresh_seq_instr_combo(self):
        self.seq_instr_combo.clear()
        for i in range(self.tabs.count()):
            name = self.tabs.tabText(i)
            self.seq_instr_combo.addItem(name)

    # Removed manual Add instrument by SN/resource; use VISA scan and Add Selected only

    def on_scan_instruments(self):
        """Scan VISA resources and populate detected_combo with resources. Attempt to classify type by *IDN?"""
        self.detected_combo.clear()
        import pyvisa
        import concurrent.futures
        rm = pyvisa.ResourceManager()
        try:
            resources = list(rm.list_resources())
        except Exception:
            resources = []

        categories = {
            'Keithley 2230': [],
            'Keysight EL34243A': [],
            'Keysight E36233A': [],
            'Hittite Sig Gen': [],
            'RhodeSchwarz SMA': [],
            'Keysight FieldFox': [],
            'Unknown': []
        }

        def scan_resource(res):
            try:
                inst = rm.open_resource(res, timeout=3000)
                try:
                    # Clear any pending I/O and status before IDN query
                    try:
                        inst.clear()
                    except Exception:
                        pass
                    try:
                        inst.write("*CLS")
                        _ = inst.query("*OPC?")
                    except Exception:
                        pass
                    idn = inst.query("*IDN?").strip()
                finally:
                    try:
                        inst.close()
                    except Exception:
                        pass
                if 'Keithley' in idn and '2230' in idn:
                    return ('Keithley 2230', res, 'Keithley 2230')
                elif 'Keysight' in idn and ('EL34243A' in idn or 'Electronic Load' in idn):
                    return ('Keysight EL34243A', res, 'Keysight EL34243A')
                elif 'Keysight' in idn and ('E36233A' in idn or 'Power Supply' in idn):
                    return ('Keysight E36233A', res, 'Keysight E36233A')
                elif 'Keysight' in idn and ('FieldFox' in idn or 'N99' in idn or 'Handheld Spectrum' in idn):
                    return ('Keysight FieldFox', res, 'Keysight FieldFox')
                elif 'Hittite' in idn or 'Sig Gen' in idn:
                    return ('Hittite Sig Gen', res, 'Hittite Sig Gen')
                elif 'Rhode' in idn or 'Schwarz' in idn or 'SMA' in idn:
                    return ('RhodeSchwarz SMA', res, 'RhodeSchwarz SMA')
                else:
                    return ('Unknown', res, 'Unknown')
            except Exception:
                return ('Unknown', res, 'Unknown')

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(resources))) as executor:
            future_to_res = {executor.submit(scan_resource, res): res for res in resources}
            for future in concurrent.futures.as_completed(future_to_res):
                cat, res, inst_type = future.result()
                categories[cat].append((res, inst_type))

        total_found = sum(len(v) for v in categories.values())
        if total_found == 0:
            self.detected_combo.addItem('No devices found', None)

        for cat, items in categories.items():
            for res, inst_type in items:
                label = f"{cat}: {res}"
                self.detected_combo.addItem(label, (res, inst_type))

        try:
            if hasattr(self, 'power_seq_builder'):
                self.power_seq_builder.refresh_instr_combo()
        except Exception:
            pass

        self.statusBar().showMessage(f'Found {total_found} device(s)', 4000)

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
                            elif isinstance(widget, KeysightELPanel):
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
                            elif isinstance(widget, RhodeSchwarzSMAPanel):
                                if widget.dev:
                                    try:
                                        widget.dev.set_output(True)
                                        widget.output_btn.setChecked(True)
                                        widget.output_btn.setText('Output On')
                                        widget.status_label.setText('Output ON')
                                    except Exception as e:
                                        widget.status_label.setText(f'Failed to set output: {e}')
                            elif isinstance(widget, FieldFoxSAPanel):
                                if widget.dev:
                                    try:
                                        widget.dev.set_output(True)
                                        widget.output_btn.setChecked(True)
                                        widget.output_btn.setText('Output On')
                                        widget.status_label.setText('Output ON')
                                    except Exception as e:
                                        widget.status_label.setText(f'Failed to set output: {e}')
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

    def soft_reset(self):
        """Soft Reset: run the same Configure Part logic as the Programming page."""
        logic_path = self._get_selected_logic_path()
        if not logic_path:
            QtWidgets.QMessageBox.information(self, 'No logic selected', 'Please select a logic .py file on the Programming tab.')
            return
        if not os.path.exists(logic_path):
            QtWidgets.QMessageBox.warning(self, 'Missing file', f'Logic file not found:\n{logic_path}')
            return
        self.run_configure_part(logic_path)

    # --- Configure Part (external logic) ---
    def _refresh_logic_combo(self):
        try:
            if not hasattr(self, 'logic_combo'):
                return
            self.logic_combo.clear()
            self.logic_combo.addItem('(Select a logic file)', '')
            try:
                files = [f for f in os.listdir(self.program_logic_dir) if f.lower().endswith('.py')]
            except Exception:
                files = []
            for f in sorted(files):
                full = os.path.join(self.program_logic_dir, f)
                self.logic_combo.addItem(f, full)
        except Exception:
            pass

    def _ensure_logic_in_combo(self, path: str):
        if not path:
            return
        try:
            # If already present, select it. Otherwise add as custom entry.
            for i in range(self.logic_combo.count()):
                if self.logic_combo.itemData(i) == path:
                    self.logic_combo.setCurrentIndex(i)
                    return
            # Add custom path
            self.logic_combo.addItem(os.path.basename(path), path)
            self.logic_combo.setCurrentIndex(self.logic_combo.count() - 1)
        except Exception:
            pass

    def _browse_logic_file(self):
        start_dir = self.program_logic_dir if os.path.isdir(self.program_logic_dir) else os.path.expanduser('~')
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select logic file', start_dir, 'Python Files (*.py)')
        if not fname:
            return
        # If file not in our logic dir, offer to copy
        try:
            target = os.path.join(self.program_logic_dir, os.path.basename(fname))
            if os.path.abspath(os.path.dirname(fname)) != os.path.abspath(self.program_logic_dir):
                resp = QtWidgets.QMessageBox.question(
                    self, 'Copy logic file?',
                    f'Copy selected file into:\n{self.program_logic_dir}\nfor easier reuse?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes)
                if resp == QtWidgets.QMessageBox.Yes:
                    try:
                        import shutil
                        os.makedirs(self.program_logic_dir, exist_ok=True)
                        shutil.copy2(fname, target)
                        fname = target
                    except Exception as e:
                        QtWidgets.QMessageBox.warning(self, 'Copy failed', str(e))
            # Ensure in combo and select
            self._ensure_logic_in_combo(fname)
        except Exception:
            pass

    def _get_selected_logic_path(self) -> str:
        try:
            data = self.logic_combo.currentData()
            return data if isinstance(data, str) else ''
        except Exception:
            return ''

    def on_configure_part_clicked(self):
        logic_path = self._get_selected_logic_path()
        if not logic_path:
            QtWidgets.QMessageBox.information(self, 'No logic selected', 'Please select a logic .py file to run.')
            return
        if not os.path.exists(logic_path):
            QtWidgets.QMessageBox.warning(self, 'Missing file', f'Logic file not found:\n{logic_path}')
            return
        self.run_configure_part(logic_path)

    def run_configure_part(self, logic_path: str):
        # Run logic directly in a background thread (no temp file, no subprocess)
        if self._logic_thread is not None and self._logic_thread.is_alive():
            self._log('Configure Part is already running')
            return

        self._logic_abort = False
        self._log(f'Starting Configure Part with logic: {os.path.basename(logic_path)}')

        def post_log(msg: str):
            try:
                QtCore.QTimer.singleShot(0, lambda m=msg: self._log(m))
            except Exception:
                pass

        def worker():
            import sys as _sys
            import importlib.util as _importlib_util
            import threading as _th
            import time as _time
            import logging as _logging
            # Forward prints from logic to the GUI logs
            class _StreamForwarder:
                def __init__(self, cb):
                    self._cb = cb
                    self._buf = ''
                    self._lock = _th.Lock()
                def write(self, s):
                    if not s:
                        return
                    with self._lock:
                        self._buf += str(s)
                        while '\n' in self._buf:
                            line, self._buf = self._buf.split('\n', 1)
                            if line.strip():
                                try:
                                    self._cb(line)
                                except Exception:
                                    pass
                def flush(self):
                    # Flush any partial line as-is to keep UI fresh
                    with self._lock:
                        if self._buf.strip():
                            try:
                                self._cb(self._buf)
                            except Exception:
                                pass
                        self._buf = ''
            try:
                # Ensure ACE Client path is available
                ace_path = r'C:\\Program Files\\Analog Devices\\ACE\\Client'
                if ace_path not in _sys.path:
                    _sys.path.append(ace_path)
                import clr  # type: ignore
                clr.AddReference('AnalogDevices.Csa.Remoting.Clients')
                clr.AddReference('AnalogDevices.Csa.Remoting.Contracts')
                from AnalogDevices.Csa.Remoting.Clients import ClientManager  # type: ignore
                manager = ClientManager.Create()
                client = manager.CreateRequestClient('localhost:2357')
                # Redirect stdout/stderr so print() in logic shows in the GUI
                _old_out, _old_err = _sys.stdout, _sys.stderr
                _fw = _StreamForwarder(post_log)
                _sys.stdout = _fw
                _sys.stderr = _fw
                # Hook Python logging to the same stream so logging.info/etc show up
                _log_handler = _logging.StreamHandler(_fw)
                _log_handler.setLevel(_logging.DEBUG)
                _log_handler.setFormatter(_logging.Formatter('%(message)s'))
                _root_logger = _logging.getLogger()
                _root_logger.addHandler(_log_handler)
                # Periodic flusher to surface partial lines at ~0.5s cadence
                _stop_evt = _th.Event()
                def _periodic_flush():
                    while not _stop_evt.is_set():
                        try:
                            _fw.flush()
                        except Exception:
                            pass
                        _time.sleep(0.5)
                _flush_thread = _th.Thread(target=_periodic_flush, daemon=True)
                _flush_thread.start()
                # Use signal-based logger for thread-safe UI update
                try:
                    self._log('ACE connection established; running logic...')
                except Exception:
                    # Last-resort: attempt direct append if logs exist
                    try:
                        if hasattr(self, 'test_log'):
                            self.test_log.appendPlainText('ACE connection established; running logic...')
                        if hasattr(self, 'program_log'):
                            self.program_log.appendPlainText('ACE connection established; running logic...')
                    except Exception:
                        pass
                # Load logic module from given path
                spec = _importlib_util.spec_from_file_location('selected_logic', logic_path)
                mod = _importlib_util.module_from_spec(spec)
                assert spec and spec.loader
                spec.loader.exec_module(mod)  # type: ignore
                func = None
                if hasattr(mod, 'execute_macro'):
                    func = getattr(mod, 'execute_macro')
                elif hasattr(mod, 'logic'):
                    func = getattr(mod, 'logic')
                if func is None:
                    self._log('Selected logic file must define execute_macro(client) or logic(client)')
                    # Restore streams before returning
                    try:
                        _fw.flush()
                    except Exception:
                        pass
                    _sys.stdout, _sys.stderr = _old_out, _old_err
                    return
                try:
                    func(client)
                finally:
                    self._log('Configure Part finished')
                    # Flush any buffered text and restore streams
                    try:
                        _fw.flush()
                    except Exception:
                        pass
                    # Stop periodic flusher
                    try:
                        _stop_evt.set()
                        _flush_thread.join(timeout=1.0)
                    except Exception:
                        pass
                    # Detach logging handler
                    try:
                        _root_logger.removeHandler(_log_handler)
                    except Exception:
                        pass
                    _sys.stdout, _sys.stderr = _old_out, _old_err                    
            except Exception as e:
                post_log(f'Configure Part error: {e}')

        import threading as _threading
        self._logic_thread = _threading.Thread(target=worker, daemon=True)
        self._logic_thread.start()

        # Update UI while running
        try:
            if hasattr(self, 'abort_program_btn'):
                self.abort_program_btn.setEnabled(True)
            if hasattr(self, 'run_program_btn'):
                self.run_program_btn.setEnabled(False)
            if hasattr(self, 'program_now_btn'):
                self.program_now_btn.setEnabled(False)
            if hasattr(self, 'configure_part_btn'):
                self.configure_part_btn.setEnabled(False)
        except Exception:
            pass

        # Poll thread to re-enable UI on completion
        try:
            if self._logic_poll_timer is None:
                self._logic_poll_timer = QtCore.QTimer(self)
                self._logic_poll_timer.setInterval(300)
                self._logic_poll_timer.timeout.connect(self._on_logic_thread_check)
            if not self._logic_poll_timer.isActive():
                self._logic_poll_timer.start()
        except Exception:
            pass

    def _on_logic_thread_check(self):
        try:
            alive = self._logic_thread is not None and self._logic_thread.is_alive()
        except Exception:
            alive = False
        if not alive:
            try:
                if self._logic_poll_timer and self._logic_poll_timer.isActive():
                    self._logic_poll_timer.stop()
            except Exception:
                pass
            self._logic_thread = None
            # Reset UI buttons
            try:
                if hasattr(self, 'run_program_btn'):
                    self.run_program_btn.setEnabled(True)
                if hasattr(self, 'abort_program_btn'):
                    self.abort_program_btn.setEnabled(False)
                if hasattr(self, 'program_now_btn'):
                    self.program_now_btn.setEnabled(True)
                if hasattr(self, 'configure_part_btn'):
                    self.configure_part_btn.setEnabled(True)
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