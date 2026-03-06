"""
Notes-tab mixin for MainWindow.

Provides structured notes fields (Connection, Sources, Monitoring, General)
for documenting DUT wiring and test setup.
"""
import os
import json

from PyQt5 import QtWidgets


class NotesMixin:
    """Mixin that adds the Notes tab and its helpers to MainWindow."""

    def _init_notes_tab(self):
        """Create the Notes tab with structured fields for setup documentation."""
        notes_widget = QtWidgets.QWidget()
        notes_layout = QtWidgets.QVBoxLayout(notes_widget)

        # ---- Connection Notes ----
        notes_layout.addWidget(QtWidgets.QLabel(
            '<b>Connection Notes</b>  –  How / where to plug sources into the DUT'))
        self.notes_connections = QtWidgets.QPlainTextEdit()
        self.notes_connections.setPlaceholderText(
            'e.g.  Keithley CH1 (3.0 V) → J3-Pin 2 (VDD)\n'
            '      Hittite 0 RF OUT → SMA J1 (LO IN)\n'
            '      FieldFox PORT 1 → SMA J4 (RF OUT)')
        self.notes_connections.setMinimumHeight(100)
        notes_layout.addWidget(self.notes_connections)

        # ---- Sources ----
        notes_layout.addWidget(QtWidgets.QLabel(
            '<b>Sources</b>  –  Which instruments / supplies are used and their roles'))
        self.notes_sources = QtWidgets.QPlainTextEdit()
        self.notes_sources.setPlaceholderText(
            'e.g.  Keithley 0 – DUT power (3.0 V, 1.8 V_A, 1.8 V_B)\n'
            '      Hittite 0 – LO drive @ 13 GHz, −5 dBm\n'
            '      Hittite 1 – IF hybrid input @ 8 GHz, −20 dBm')
        self.notes_sources.setMinimumHeight(100)
        notes_layout.addWidget(self.notes_sources)

        # ---- Monitoring ----
        notes_layout.addWidget(QtWidgets.QLabel(
            '<b>Monitoring</b>  –  What to monitor / record during the test'))
        self.notes_monitoring = QtWidgets.QPlainTextEdit()
        self.notes_monitoring.setPlaceholderText(
            'e.g.  Supply currents on Keithley 0 (all channels)\n'
            '      Output spectrum on FieldFox 0 – center 20 GHz, span 10 GHz\n'
            '      Register reads: 0x000, 0x004, 0x00A …')
        self.notes_monitoring.setMinimumHeight(100)
        notes_layout.addWidget(self.notes_monitoring)

        # ---- General Notes ----
        notes_layout.addWidget(QtWidgets.QLabel(
            '<b>General Notes</b>  –  Any additional setup information'))
        self.notes_general = QtWidgets.QPlainTextEdit()
        self.notes_general.setPlaceholderText(
            'e.g.  Power-on order matters – enable VDD before LO.\n'
            '      DUT must be programmed via ACE macro before RF test.')
        self.notes_general.setMinimumHeight(80)
        notes_layout.addWidget(self.notes_general)

        # ---- Save controls ----
        notes_btn_row = QtWidgets.QHBoxLayout()
        self.save_notes_btn = QtWidgets.QPushButton('Save Notes to Config')
        self.save_notes_btn.setToolTip(
            'Save the current notes back to the last loaded config file')
        self.save_notes_btn.clicked.connect(self._save_notes_to_config)
        notes_btn_row.addWidget(self.save_notes_btn)
        notes_btn_row.addStretch(1)
        notes_layout.addLayout(notes_btn_row)

        notes_layout.addStretch(1)
        self.top_tabs.addTab(notes_widget, 'Notes')

    def _get_notes_dict(self) -> dict:
        """Return the current notes fields as a serialisable dict."""
        return {
            'connections': self.notes_connections.toPlainText(),
            'sources': self.notes_sources.toPlainText(),
            'monitoring': self.notes_monitoring.toPlainText(),
            'general': self.notes_general.toPlainText(),
        }

    def _save_notes_to_config(self):
        """Save the current notes back to the last loaded config JSON file."""
        config_path = getattr(self, '_last_loaded_config_path', '')
        if not config_path or not os.path.exists(config_path):
            QtWidgets.QMessageBox.information(
                self, 'No config loaded',
                'No config file is currently loaded.\n'
                'Use "Save Config" on the Setup tab to create one first.')
            return
        try:
            with open(config_path, 'r') as f:
                content = json.load(f)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Read failed', str(e))
            return
        if isinstance(content, dict):
            content['notes'] = self._get_notes_dict()
        else:
            content = {'instruments': content, 'notes': self._get_notes_dict()}
        try:
            with open(config_path, 'w') as f:
                json.dump(content, f, indent=2)
            config_name = os.path.basename(config_path)
            self.statusBar().showMessage(f'Notes saved to {config_name}', 4000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Save failed', str(e))

    def _set_notes_from_dict(self, d: dict):
        """Populate notes fields from a dict (e.g. loaded from config)."""
        if not isinstance(d, dict):
            return
        fields = [
            (self.notes_connections, 'connections'),
            (self.notes_sources, 'sources'),
            (self.notes_monitoring, 'monitoring'),
            (self.notes_general, 'general'),
        ]
        for widget, key in fields:
            widget.setPlainText(d.get(key, ''))

    def _auto_populate_notes_from_config(self, config_name: str, instruments: list,
                                          sequence: list = None, use_sequence: bool = False,
                                          registers: list = None, logic_path: str = ''):
        """Generate human-readable notes from a loaded config's instrument list."""
        conn_lines = []
        src_lines = []
        mon_lines = []
        gen_lines = []

        for entry in instruments:
            inst_type = entry.get('type', 'Unknown')
            name = entry.get('name', '')
            resource = entry.get('resource', '')
            label = name if name else resource

            if inst_type == 'Keithley 2230':
                channels = entry.get('channels', {})
                ch_descs = []
                for ch_num in sorted(channels.keys(), key=lambda x: int(x)):
                    ch = channels[ch_num]
                    ch_name = ch.get('name', f'CH{ch_num}')
                    voltage = ch.get('voltage', '0')
                    current = ch.get('current', '0')
                    ch_descs.append(f'CH{ch_num} "{ch_name}" → {voltage} V, {current} A limit')
                conn_lines.append(f'{label}  (Power Supply)')
                for d in ch_descs:
                    conn_lines.append(f'    {d}')
                summary_parts = []
                for ch_num in sorted(channels.keys(), key=lambda x: int(x)):
                    ch = channels[ch_num]
                    ch_name = ch.get('name', f'CH{ch_num}')
                    voltage = ch.get('voltage', '0')
                    try:
                        if float(voltage) == 0:
                            continue
                    except (ValueError, TypeError):
                        pass
                    summary_parts.append(f'{ch_name} @ {voltage} V')
                if summary_parts:
                    src_lines.append(f'{label} – DUT power: {", ".join(summary_parts)}')
                else:
                    src_lines.append(f'{label} – DUT power supply (channels unused or 0 V)')
                mon_lines.append(f'{label} – Monitor supply currents on all active channels')

            elif inst_type == 'Keysight EL34243A':
                channels = entry.get('channels', {})
                ch_descs = []
                for ch_num in sorted(channels.keys(), key=lambda x: int(x)):
                    ch = channels[ch_num]
                    mode = ch.get('mode', 'CC')
                    value = ch.get('value', '0')
                    inp = ch.get('input', False)
                    state = 'ON' if inp else 'OFF'
                    ch_descs.append(f'CH{ch_num} – {mode} mode, {value}, input {state}')
                conn_lines.append(f'{label}  (Electronic Load)')
                for d in ch_descs:
                    conn_lines.append(f'    {d}')
                src_lines.append(f'{label} – Electronic load')
                mon_lines.append(f'{label} – Monitor load currents / voltages')

            elif inst_type == 'Keysight E36233A':
                channels = entry.get('channels', {})
                ch_descs = []
                for ch_num in sorted(channels.keys(), key=lambda x: int(x)):
                    ch = channels[ch_num]
                    voltage = ch.get('voltage', '0')
                    current = ch.get('current', '0')
                    ch_descs.append(f'CH{ch_num} → {voltage} V, {current} A limit')
                conn_lines.append(f'{label}  (Power Supply)')
                for d in ch_descs:
                    conn_lines.append(f'    {d}')
                src_lines.append(f'{label} – Power supply')
                mon_lines.append(f'{label} – Monitor supply currents')

            elif inst_type in ('Hittite Sig Gen', 'RhodeSchwarz SMA'):
                settings = entry.get('settings', {})
                freq = settings.get('frequency', '?')
                unit = settings.get('freq_unit', 'MHz')
                power = settings.get('power', '?')
                kind = 'Signal Generator' if inst_type == 'Hittite Sig Gen' else 'R&S SMA Signal Generator'
                dut_port = entry.get('dut_port', '')
                if dut_port:
                    conn_lines.append(f'{label}  ({kind}) → {dut_port}')
                else:
                    conn_lines.append(f'{label}  ({kind}) → DUT')
                src_lines.append(f'{label} – {freq} {unit}, {power} dBm')

            elif inst_type == 'Keysight FieldFox':
                settings = entry.get('settings', {})
                center = settings.get('center', '?')
                span = settings.get('span', '?')
                unit = settings.get('unit', 'GHz')
                dut_port = entry.get('dut_port', '')
                if dut_port:
                    conn_lines.append(f'{label}  (Spectrum Analyzer) ← {dut_port}')
                else:
                    conn_lines.append(f'{label}  (Spectrum Analyzer) ← DUT output')
                src_lines.append(f'{label} – Spectrum analyzer, center {center} {unit}, span {span} {unit}')
                mon_lines.append(f'{label} – Record output spectrum')

            else:
                conn_lines.append(f'{label}  ({inst_type})')
                src_lines.append(f'{label} – {inst_type}')

        if registers:
            hex_list = []
            for r in registers[:20]:
                try:
                    hex_list.append(f'{int(r):#x}')
                except (ValueError, TypeError):
                    hex_list.append(str(r))
            suffix = f'  … and {len(registers) - 20} more' if len(registers) > 20 else ''
            mon_lines.append(f'Register reads: {", ".join(hex_list)}{suffix}')

        if use_sequence and sequence:
            gen_lines.append('Power-up sequence (order matters):')
            for step in sequence:
                gen_lines.append(f'    {step}')
        if logic_path:
            gen_lines.append(f'Programming logic: {os.path.basename(logic_path)}')
        if config_name:
            gen_lines.insert(0, f'Config: {config_name}')

        self.notes_connections.setPlainText('\n'.join(conn_lines))
        self.notes_sources.setPlainText('\n'.join(src_lines))
        self.notes_monitoring.setPlainText('\n'.join(mon_lines))
        self.notes_general.setPlainText('\n'.join(gen_lines))
