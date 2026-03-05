"""
Configuration save/load mixin for MainWindow.

Provides save_config, load_config, disconnect_all_instruments,
and related helpers.
"""
import os
import json

from PyQt5 import QtWidgets, QtCore
import pyvisa

from Support_Scrips.Front_Panels.keithley_panel import KeithleyPanel
from Support_Scrips.Front_Panels.keysightEL_panel import KeysightELPanel
from Support_Scrips.Front_Panels.keysight_e36233a_panel import KeysightE36233APanel
from Support_Scrips.Front_Panels.hittite_siggen_panel import HittiteSigGenPanel
from Support_Scrips.Front_Panels.rhodeschwarz_sma_panel import RhodeSchwarzSMAPanel
from Support_Scrips.Front_Panels.fieldfox_sa_panel import FieldFoxSAPanel


class ConfigMixin:
    """Mixin that adds configuration save/load to MainWindow."""

    def refresh_configs_list(self):
        self.load_combo.clear()
        placeholder = '---Config List--'
        self.load_combo.addItem(placeholder, None)
        files = sorted([f for f in os.listdir(self.configs_dir) if f.lower().endswith('.json')])
        for f in files:
            full = os.path.join(self.configs_dir, f)
            self.load_combo.addItem(f, full)
        self.load_combo.setCurrentIndex(0)
        try:
            if hasattr(self, 'alias_profile_combo'):
                self._refresh_alias_profiles()
        except Exception:
            pass

    def disconnect_all_instruments(self):
        """Cleanly stop recordings, disconnect/clear all panels and instruments, and remove tabs."""
        try:
            self.statusBar().showMessage('Disconnecting all instruments…', 3000)
        except Exception:
            pass
        try:
            if hasattr(self, 'record_btn') and self.record_btn.isChecked():
                try:
                    self.record_btn.setChecked(False)
                except Exception:
                    pass
            self._stop_all_recordings()
        except Exception:
            pass
        try:
            for i in range(self.tabs.count() - 1, -1, -1):
                w = self.tabs.widget(i)
                try:
                    if isinstance(w, KeithleyPanel):
                        self._keithley_apply_settings(w, False)
                    elif isinstance(w, KeysightELPanel):
                        self._keysight_el_apply_settings(w, False)
                    elif isinstance(w, (HittiteSigGenPanel, RhodeSchwarzSMAPanel, FieldFoxSAPanel)):
                        self._generic_output_toggle(w, False)
                except Exception:
                    pass
                try:
                    if hasattr(w, 'close'):
                        w.close()
                except Exception:
                    pass
                try:
                    for attr in ('inst', 'dev', 'sa'):
                        obj = getattr(w, attr, None)
                        if obj is None:
                            continue
                        if hasattr(obj, 'close'):
                            try:
                                obj.close()
                            except Exception:
                                pass
                        if hasattr(obj, 'inst') and hasattr(obj.inst, 'close'):
                            try:
                                obj.inst.close()
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    self.tabs.removeTab(i)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            QtWidgets.QApplication.processEvents()
        except Exception:
            pass

    def save_config_dialog(self):
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
            resource_val = getattr(widget, 'resource', '')
            if (not resource_val) and isinstance(widget, FieldFoxSAPanel) and hasattr(widget, 'sa'):
                try:
                    resource_val = getattr(widget.sa, 'visa_address', '')
                except Exception:
                    resource_val = ''
            try:
                if isinstance(resource_val, str) and self.alias_map:
                    for alias_key, res in self.alias_map.items():
                        if res == resource_val:
                            resource_val = f"alias:{alias_key}"
                            break
            except Exception:
                pass
            entry = {'type': tab_type, 'resource': resource_val, 'name': saved_name}
            if isinstance(widget, KeithleyPanel):
                entry['channels'] = {}
                for ch in (1, 2, 3):
                    entry['channels'][ch] = {
                        'voltage': widget.vol_edits[ch].text(),
                        'current': widget.iam_edits[ch].text(),
                        'output': widget.master_out_btn.isChecked(),
                        'name': (widget.ch_name_edits[ch].text() if hasattr(widget, 'ch_name_edits') and widget.ch_name_edits.get(ch) else f'CH{ch}')
                    }
            elif isinstance(widget, KeysightELPanel):
                entry['channels'] = {}
                for ch in (1, 2):
                    mode = (widget.mode_combo_ch1.currentText() if ch == 1 else widget.mode_combo_ch2.currentText())
                    value = (widget.mode_value_ch1.text() if ch == 1 else widget.mode_value_ch2.text())
                    inp = False
                    try:
                        if getattr(widget, 'dev', None):
                            inp = bool(widget.dev.get_input_state(ch))
                        elif hasattr(widget, '_get_input_toggle_ui'):
                            inp = bool(widget._get_input_toggle_ui(ch))
                    except Exception:
                        pass
                    ramp_enable = (widget.ramp_enable_ch1.isChecked() if ch == 1 else widget.ramp_enable_ch2.isChecked())
                    rise_time = (widget.rise_time_ch1.text() if ch == 1 else widget.rise_time_ch2.text())
                    entry['channels'][ch] = {
                        'mode': mode, 'value': value, 'input': inp,
                        'ramp_enabled': ramp_enable, 'rise_time': rise_time
                    }
            elif isinstance(widget, KeysightE36233APanel):
                entry['channels'] = {}
                for ch in (1, 2):
                    entry['channels'][ch] = {
                        'voltage': widget.voltage_edit.text(),
                        'current': widget.current_edit.text(),
                        'output': widget.onoff_btn.isChecked(),
                        'name': f'CH{ch}'
                    }
            elif isinstance(widget, HittiteSigGenPanel):
                try:
                    entry['settings'] = {
                        'frequency': getattr(widget, 'freq_edit', None).text() if hasattr(widget, 'freq_edit') else '',
                        'freq_unit': getattr(widget, 'freq_unit_combo', None).currentText() if hasattr(widget, 'freq_unit_combo') else 'MHz',
                        'power': getattr(widget, 'pow_edit', None).text() if hasattr(widget, 'pow_edit') else '',
                        'output': getattr(widget, 'output_btn', None).isChecked() if hasattr(widget, 'output_btn') else False
                    }
                except Exception:
                    pass
            if isinstance(widget, FieldFoxSAPanel):
                entry['settings'] = {
                    'center': widget.center_edit.text(),
                    'span': widget.span_edit.text(),
                    'start': widget.start_edit.text(),
                    'stop': widget.stop_edit.text(),
                    'unit': widget.unit_combo.currentText()
                }
            if isinstance(widget, RhodeSchwarzSMAPanel):
                entry['settings'] = {
                    'frequency': widget.freq_edit.text(),
                    'freq_unit': widget.freq_unit_combo.currentText(),
                    'power': widget.pow_edit.text(),
                    'output': widget.output_btn.isChecked()
                }
            instruments.append(entry)

        seq = []
        use_seq = False
        try:
            if hasattr(self, 'power_seq_builder'):
                seq = self.power_seq_builder.get_sequence()
                use_seq = self.power_seq_builder.use_sequence()
        except Exception:
            seq = []
            use_seq = False

        notes = {}
        try:
            notes = self._get_notes_dict()
        except Exception:
            pass

        payload = {
            'instruments': instruments,
            'sequence': seq,
            'use_sequence': use_seq,
            'program_logic_path': self._get_selected_logic_path(),
            'register_read_array': getattr(self, 'register_read_array', []),
            'notes': notes
        }
        try:
            with open(path, 'w') as f:
                json.dump(payload, f, indent=2)
            self.statusBar().showMessage(f'Saved config to {path}', 4000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Save failed', str(e))

    def load_config_dialog(self):
        data = self.load_combo.currentData()
        text = self.load_combo.currentText()
        if (data is None) or (not text) or text.startswith('---'):
            QtWidgets.QMessageBox.information(self, 'No config', 'No config file selected.')
            return
        path = str(data)
        self.load_config(path)

    def load_config(self, path):
        if not os.path.exists(path):
            QtWidgets.QMessageBox.information(self, 'No config', f'Config file not found: {path}')
            return
        try:
            self.disconnect_all_instruments()
        except Exception:
            while self.tabs.count():
                try:
                    self.tabs.removeTab(0)
                except Exception:
                    break

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

        try:
            rm_for_load = pyvisa.ResourceManager()
            current_resources = list(rm_for_load.list_resources())
        except Exception:
            rm_for_load = None
            current_resources = []

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
            try:
                logic_path = content.get('program_logic_path', '')
                if logic_path and os.path.exists(logic_path):
                    self._ensure_logic_in_combo(logic_path)
                else:
                    try:
                        auto_logic = self._auto_select_logic_for_config(path, instruments, content)
                    except Exception:
                        auto_logic = ''
                    if auto_logic:
                        self._ensure_logic_in_combo(auto_logic)
                        try:
                            self.statusBar().showMessage(f"Auto-selected logic: {os.path.basename(auto_logic)}", 4000)
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                self.register_read_array = content.get('register_read_array', [])
            except Exception:
                self.register_read_array = []
            try:
                notes_data = content.get('notes', {})
                has_saved_notes = notes_data and any(
                    notes_data.get(k, '').strip()
                    for k in ('connections', 'sources', 'monitoring', 'general')
                )
                append_mode = False
                try:
                    append_mode = (hasattr(self, 'notes_append_mode')
                                   and self.notes_append_mode.currentText() == 'Append on Load')
                except Exception:
                    pass
                if has_saved_notes:
                    self._set_notes_from_dict(notes_data, append=append_mode)
                else:
                    config_name = os.path.splitext(os.path.basename(path))[0]
                    self._auto_populate_notes_from_config(
                        config_name=config_name,
                        instruments=instruments,
                        sequence=sequence,
                        use_sequence=use_sequence,
                        registers=content.get('register_read_array', []),
                        logic_path=content.get('program_logic_path', '')
                    )
            except Exception:
                pass

        if hasattr(self, 'power_seq_builder'):
            try:
                self.power_seq_builder.set_sequence(sequence)
                self.power_seq_builder.set_use_sequence(use_sequence)
            except Exception:
                pass
        used_resources = set()
        for entry in instruments:
            inst_type = entry.get('type', 'Keithley 2230')
            if inst_type == 'Unknown':
                name_l = entry.get('name', '').lower()
                if any(k in name_l for k in ['hittite', 'sig', 'signal']):
                    inst_type = 'Hittite Sig Gen'
                elif any(k in name_l for k in ['rohde', 'schwarz', 'sma', 'rs ']):
                    inst_type = 'RhodeSchwarz SMA'
            resource = entry.get('resource', '')
            try:
                if isinstance(resource, str) and resource.startswith('alias:'):
                    alias_key = resource.split(':', 1)[1]
                    if not self.alias_map:
                        try:
                            rm_tmp = pyvisa.ResourceManager()
                            self._auto_select_alias_profile(list(rm_tmp.list_resources()))
                        except Exception:
                            pass
                    resource = self.alias_map.get(alias_key, '')
            except Exception:
                pass
            if (not resource) and inst_type in ('Hittite Sig Gen', 'RhodeSchwarz SMA', 'Keysight E36233A', 'Keysight EL34243A', 'Keithley 2230'):
                try:
                    candidates = self._find_replacement_candidates(resource, inst_type, rm_for_load)
                except Exception:
                    candidates = []
                if candidates:
                    resource = candidates[0][1]
                    self.statusBar().showMessage(f'{inst_type} resource missing; auto-connected to: {resource}', 5000)
            if inst_type == 'Keysight FieldFox' and (not resource or resource not in current_resources):
                try:
                    candidates = self._find_replacement_candidates(resource, inst_type, rm_for_load)
                except Exception:
                    candidates = []
                if not candidates:
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
                            except Exception:
                                continue
                    except Exception:
                        pass
                if candidates:
                    resource = candidates[0][1]
                    self.statusBar().showMessage(f'FieldFox resource missing; auto-connected to: {resource}', 5000)
                else:
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
                if hasattr(panel, 'on_connect'):
                    try:
                        if inst_type not in ('Keysight FieldFox', 'Hittite Sig Gen'):
                            panel.on_connect()
                    except Exception:
                        pass
                if inst_type == 'Keithley 2230':
                    for ch in (1, 2, 3):
                        ch_cfg = entry.get('channels', {}).get(str(ch)) or entry.get('channels', {}).get(ch)
                        if ch_cfg:
                            try:
                                if hasattr(panel, 'ch_name_edits') and panel.ch_name_edits.get(ch):
                                    nm = ch_cfg.get('name') if isinstance(ch_cfg, dict) else None
                                    if nm is not None:
                                        panel.ch_name_edits[ch].setText(str(nm))
                                panel.vol_edits[ch].setText(str(ch_cfg.get('voltage', '0')))
                                panel.iam_edits[ch].setText(str(ch_cfg.get('current', '0.03')))
                                panel.master_out_btn.setChecked(bool(ch_cfg.get('output', False)))
                                panel.master_out_btn.setText('All On' if ch_cfg.get('output', False) else 'All Off')
                                if getattr(panel, 'inst', None):
                                    panel.inst.set_voltage(ch, float(ch_cfg.get('voltage', '0')))
                                    panel.inst.set_current(ch, float(ch_cfg.get('current', '0.03')))
                                    panel.inst.set_output(ch, bool(ch_cfg.get('output', False)))
                            except Exception:
                                pass
                elif inst_type == 'Keysight EL34243A':
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
                    try:
                        ch_cfgs = entry.get('channels', {})
                        for ch in (1, 2):
                            ch_cfg = ch_cfgs.get(str(ch)) or ch_cfgs.get(ch)
                            if not ch_cfg:
                                continue
                            try:
                                if hasattr(panel, 'mode_combo_ch1') and hasattr(panel, 'mode_combo_ch2'):
                                    combo = panel.mode_combo_ch1 if ch == 1 else panel.mode_combo_ch2
                                    if ch_cfg.get('mode'):
                                        idx = combo.findText(str(ch_cfg.get('mode')))
                                        if idx != -1:
                                            combo.setCurrentIndex(idx)
                                if hasattr(panel, 'mode_value_ch1') and hasattr(panel, 'mode_value_ch2') and (ch_cfg.get('value') is not None):
                                    (panel.mode_value_ch1 if ch == 1 else panel.mode_value_ch2).setText(str(ch_cfg.get('value')))
                                if hasattr(panel, 'ramp_enable_ch1') and hasattr(panel, 'ramp_enable_ch2'):
                                    ramp_enable = ch_cfg.get('ramp_enabled', False)
                                    (panel.ramp_enable_ch1 if ch == 1 else panel.ramp_enable_ch2).setChecked(bool(ramp_enable))
                                if hasattr(panel, 'rise_time_ch1') and hasattr(panel, 'rise_time_ch2'):
                                    rise_time = ch_cfg.get('rise_time', '')
                                    (panel.rise_time_ch1 if ch == 1 else panel.rise_time_ch2).setText(str(rise_time))
                            except Exception:
                                pass
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
                        def apply_sma_hw():
                            if getattr(panel, 'dev', None):
                                try:
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
                    try:
                        settings = entry.get('settings', {})
                        freq = settings.get('frequency')
                        freq_unit = settings.get('freq_unit')
                        power = settings.get('power')
                        output_state = settings.get('output', False)
                        try:
                            if hasattr(panel, 'auto_apply_on_connect'):
                                panel.auto_apply_on_connect = False
                        except Exception:
                            pass
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
                        try:
                            if hasattr(panel, 'on_connect'):
                                panel.on_connect()
                        except Exception:
                            pass
                        def apply_hittite_hw(attempt_idx: int = 0):
                            try:
                                if getattr(panel, 'dev', None) is None:
                                    try:
                                        if hasattr(panel, 'on_connect'):
                                            panel.on_connect()
                                    except Exception:
                                        pass
                                if attempt_idx == 0:
                                    QtCore.QTimer.singleShot(500, lambda: apply_hittite_hw(attempt_idx + 1))
                                    return
                                try:
                                    freq_val = float(panel.freq_edit.text())
                                except Exception:
                                    freq_val = None
                                try:
                                    unit = panel.freq_unit_combo.currentText()
                                except Exception:
                                    unit = 'GHz'
                                mult = {'GHz': 1e9, 'MHz': 1e6, 'KHz': 1e3, 'Hz': 1}.get(unit, 1)
                                if freq_val is not None:
                                    try:
                                        panel.dev.set_frequency(freq_val * mult)
                                    except Exception:
                                        try:
                                            if hasattr(panel, 'on_set_frequency'):
                                                panel.on_set_frequency()
                                        except Exception:
                                            pass
                                if power is not None:
                                    try:
                                        panel.dev.set_power(float(power))
                                    except Exception:
                                        try:
                                            if hasattr(panel, 'on_set_power'):
                                                panel.on_set_power()
                                        except Exception:
                                            pass
                                try:
                                    panel.dev.set_output(bool(output_state))
                                except Exception:
                                    pass
                                try:
                                    panel.status_label.setText('Applied JSON freq/power/output')
                                except Exception:
                                    pass
                            except Exception:
                                if attempt_idx < 8:
                                    QtCore.QTimer.singleShot(600, lambda: apply_hittite_hw(attempt_idx + 1))
                        QtCore.QTimer.singleShot(400, apply_hittite_hw)
                        try:
                            if getattr(panel, 'dev', None) is not None and hasattr(panel, '_apply_ui_to_hw'):
                                QtCore.QTimer.singleShot(800, panel._apply_ui_to_hw)
                        except Exception:
                            pass
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
                        def attempt(idx=0):
                            try:
                                if getattr(panel.sa, 'inst', None) is None and hasattr(panel, 'on_connect'):
                                    panel.on_connect()
                                if getattr(panel.sa, 'inst', None) is None:
                                    raise RuntimeError('Not connected yet')
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
                                try:
                                    panel.start_capture_thread()
                                except Exception:
                                    pass
                                return
                            except Exception:
                                pass
                            if idx < 5:
                                QtCore.QTimer.singleShot(500, lambda: attempt(idx+1))
                        QtCore.QTimer.singleShot(400, attempt)
                    except Exception:
                        pass
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

        try:
            self._refresh_logic_combo()
        except Exception:
            pass
        try:
            self._last_loaded_config_path = path
        except Exception:
            pass
