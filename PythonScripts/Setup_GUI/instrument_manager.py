"""
Instrument scanning / panel management mixin for MainWindow.

Provides VISA scanning, adding instrument panels, closing tabs,
and related helpers.
"""
import concurrent.futures

from PyQt5 import QtWidgets, QtCore
import pyvisa

from Support_Scrips.Front_Panels.keithley_panel import KeithleyPanel
from Support_Scrips.Front_Panels.keysightEL_panel import KeysightELPanel
from Support_Scrips.Front_Panels.keysight_e36233a_panel import KeysightE36233APanel
from Support_Scrips.Front_Panels.hittite_siggen_panel import HittiteSigGenPanel
from Support_Scrips.Front_Panels.rhodeschwarz_sma_panel import RhodeSchwarzSMAPanel
from Support_Scrips.Front_Panels.fieldfox_sa_panel import FieldFoxSAPanel


class InstrumentMixin:
    """Mixin that adds VISA scan and instrument-panel management to MainWindow."""

    def on_scan_instruments(self):
        """Scan VISA resources and populate detected_combo with resources."""
        try:
            self.statusBar().showMessage('Scanning instruments please wait')
        except Exception:
            pass
        self.detected_combo.clear()
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

        if resources:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(resources))) as executor:
                future_to_res = {executor.submit(scan_resource, res): res for res in resources}
                for future in concurrent.futures.as_completed(future_to_res):
                    cat, res, inst_type = future.result()
                    categories[cat].append((res, inst_type))

        total_found = sum(len(v) for v in categories.values())
        if total_found == 0:
            self.detected_combo.addItem('No devices found', None)

        # Build reverse alias map for quick lookup
        try:
            rev_alias = {v: k for k, v in (self.alias_map or {}).items()}
        except Exception:
            rev_alias = {}

        def _alias_base_for_type(_t: str) -> str:
            t = (_t or '').strip()
            if t == 'Keithley 2230':
                return 'Keithley'
            if t == 'Keysight FieldFox':
                return 'FieldFox'
            if t == 'Keysight EL34243A':
                return 'Keysight EL'
            if t == 'Keysight E36233A':
                return 'E36233A'
            if t == 'Hittite Sig Gen':
                return 'Hittite'
            if t == 'RhodeSchwarz SMA':
                return 'RohdeSchwarz SMA'
            return 'Unknown'

        alias_counters = {}
        for cat, items in categories.items():
            for res, inst_type in items:
                alias_name = rev_alias.get(res)
                if not alias_name:
                    base = _alias_base_for_type(inst_type)
                    idx = alias_counters.get(base, 0)
                    alias_name = f"{base} {idx}"
                    alias_counters[base] = idx + 1
                self.detected_combo.addItem(alias_name, (res, inst_type, alias_name))

        # Apply aliasing choice from startup prompt
        try:
            mode = getattr(self, '_alias_startup_choice', '')
            if mode == 'preconfigured' and getattr(self, 'alias_profile', ''):
                pass
            elif mode == 'generic':
                self._build_aliases_from_resources(resources)
            else:
                self._auto_select_alias_profile(resources)
        except Exception:
            pass

        try:
            if hasattr(self, 'power_seq_builder'):
                self.power_seq_builder.refresh_instr_combo()
        except Exception:
            pass

        try:
            self.statusBar().showMessage(f'Found {total_found} device(s)', 3000)
            QtCore.QTimer.singleShot(3000, lambda: self.statusBar().showMessage('Ready'))
        except Exception:
            try:
                self.statusBar().showMessage('Ready')
            except Exception:
                pass

    def on_add_selected_instrument(self):
        data = self.detected_combo.currentData()
        if not data:
            QtWidgets.QMessageBox.information(self, 'No selection', 'Select a detected device first (Scan VISA).')
            return
        try:
            resource, inst_type, alias_label = data
        except Exception:
            resource, inst_type = data
            alias_label = resource
        label = alias_label
        self.add_instrument_panel(resource, label, inst_type)
        try:
            if hasattr(self, 'power_seq_builder'):
                self.power_seq_builder.refresh_instr_combo()
        except Exception:
            pass
        self.statusBar().showMessage(f'Added {label}', 3000)

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
        try:
            if not hasattr(panel, 'resource') or not getattr(panel, 'resource'):
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

    def get_instrument_names(self):
        names = []
        for i in range(self.tabs.count()):
            names.append(self.tabs.tabText(i))
        return names

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        try:
            widget.close()
        except Exception:
            pass
        self.tabs.removeTab(index)
        self.power_seq_builder.refresh_instr_combo()

    def _on_tab_changed(self, index: int):
        try:
            active_panel = None
            try:
                w = self.tabs.widget(index)
                if isinstance(w, FieldFoxSAPanel):
                    active_panel = w
            except Exception:
                active_panel = None
            for i in range(self.tabs.count()):
                panel = self.tabs.widget(i)
                if isinstance(panel, FieldFoxSAPanel):
                    if panel is active_panel:
                        if hasattr(panel, 'stream_btn') and hasattr(panel, 'toggle_streaming'):
                            if not panel.streaming_enabled:
                                panel.stream_btn.setChecked(True)
                                panel.toggle_streaming(True)
                    else:
                        if hasattr(panel, 'stream_btn') and hasattr(panel, 'toggle_streaming'):
                            if panel.streaming_enabled:
                                panel.stream_btn.setChecked(False)
                                panel.toggle_streaming(False)
        except Exception:
            pass
