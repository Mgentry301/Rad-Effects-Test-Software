"""
Power-management mixin for MainWindow.

Handles per-panel output toggling, power on/off all, sequence execution,
reset, and related UI helpers.
"""
from typing import List, Tuple

from PyQt5 import QtWidgets, QtCore
import pyvisa

from Support_Scrips.Front_Panels.keithley_panel import KeithleyPanel
from Support_Scrips.Front_Panels.keysightEL_panel import KeysightELPanel
from Support_Scrips.Front_Panels.keysight_e36233a_panel import KeysightE36233APanel
from Support_Scrips.Front_Panels.hittite_siggen_panel import HittiteSigGenPanel
from Support_Scrips.Front_Panels.rhodeschwarz_sma_panel import RhodeSchwarzSMAPanel
from Support_Scrips.Front_Panels.fieldfox_sa_panel import FieldFoxSAPanel


class PowerMixin:
    """Mixin that adds power-management methods to MainWindow."""

    # --- Per-panel apply helpers ---
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
                    panel.output_btns[ch].setChecked(True)
                    panel.output_btns[ch].setText('Output On')
                    panel.output_btns[ch].setStyleSheet('background-color: #4CAF50; color: white;')
                else:
                    panel.inst.set_output(ch, False)
                    panel.output_btns[ch].setChecked(False)
                    panel.output_btns[ch].setText('Output Off')
                    panel.output_btns[ch].setStyleSheet('background-color: #F44336; color: white;')
            except Exception:
                pass
        panel.master_out_btn.setChecked(on)
        panel.master_out_btn.setText('All On' if on else 'All Off')

    def _keysight_el_apply_settings(self, panel: KeysightELPanel, on: bool):
        if not getattr(panel, 'dev', None):
            return
        for ch in (1, 2):
            try:
                mode = (panel.mode_combo_ch1.currentText() if ch == 1 else panel.mode_combo_ch2.currentText())
                if mode == 'Disable':
                    panel.dev.set_input(ch, False)
                    if hasattr(panel, '_set_input_toggle_ui'):
                        panel._set_input_toggle_ui(ch, False)
                    continue
                if on:
                    try:
                        value = float(panel.mode_value_ch1.text() if ch == 1 else panel.mode_value_ch2.text())
                    except Exception:
                        value = 0.0
                    panel.dev.set_mode(ch, mode)
                    ramp_enabled = panel.ramp_enable_ch1.isChecked() if ch == 1 else panel.ramp_enable_ch2.isChecked()
                    try:
                        rise_time = float(panel.rise_time_ch1.text() if ch == 1 else panel.rise_time_ch2.text())
                    except Exception:
                        rise_time = 0.0
                    panel.dev.set_input(ch, True)
                    if ramp_enabled and rise_time > 0:
                        import numpy as np
                        import time
                        steps = 20
                        for v in np.linspace(0, value, steps):
                            panel.dev.set_parameter(ch, mode, v)
                            QtWidgets.QApplication.processEvents()
                            time.sleep(rise_time / steps)
                        panel.dev.set_parameter(ch, mode, value)
                    else:
                        panel.dev.set_parameter(ch, mode, value)
                else:
                    panel.dev.set_input(ch, False)
            except Exception:
                pass
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

    def _hittite_apply_on_power(self, panel: HittiteSigGenPanel, on: bool):
        """On global Power On/Off for a Hittite sig-gen tab: auto-connect if
        the panel was loaded from an alias but never connected, push current
        UI freq/power to hardware, then toggle the output. Mirrors the
        FieldFox behavior so HT0/HT1 turn on with "Power All On" whenever
        they are present in the loaded alias/config."""
        try:
            # Auto-connect if needed (alias load defers connect for Hittite)
            if getattr(panel, 'dev', None) is None and hasattr(panel, 'on_connect'):
                try:
                    panel.on_connect()
                except Exception:
                    pass

            def _apply(attempt: int = 0):
                dev = getattr(panel, 'dev', None)
                if dev is None:
                    if attempt < 5 and hasattr(panel, 'on_connect'):
                        try:
                            panel.on_connect()
                        except Exception:
                            pass
                        QtCore.QTimer.singleShot(400, lambda: _apply(attempt + 1))
                    else:
                        try:
                            panel.status_label.setText('Not connected; cannot toggle output')
                        except Exception:
                            pass
                    return
                if on:
                    # Push current UI freq/power to hardware before enabling output
                    try:
                        if hasattr(panel, '_apply_ui_to_hw'):
                            panel._apply_ui_to_hw()
                        else:
                            try:
                                freq_val = float(panel.freq_edit.text())
                                unit = panel.freq_unit_combo.currentText()
                                mult = {'GHz': 1e9, 'MHz': 1e6, 'KHz': 1e3, 'Hz': 1}.get(unit, 1)
                                dev.set_frequency(freq_val * mult)
                            except Exception:
                                pass
                            try:
                                dev.set_power(float(panel.pow_edit.text()))
                            except Exception:
                                pass
                    except Exception:
                        pass
                try:
                    dev.set_output(on)
                except Exception as e:
                    try:
                        panel.status_label.setText(f'Failed to set output: {e}')
                    except Exception:
                        pass
                    return
                if hasattr(panel, 'output_btn'):
                    try:
                        panel.output_btn.blockSignals(True)
                        panel.output_btn.setChecked(on)
                        panel.output_btn.setText('Output On' if on else 'Output Off')
                    finally:
                        panel.output_btn.blockSignals(False)
                if hasattr(panel, '_update_output_btn_color'):
                    try:
                        panel._update_output_btn_color(on)
                    except Exception:
                        pass
                try:
                    panel.status_label.setText('Output ON' if on else 'Output OFF')
                except Exception:
                    pass

            QtCore.QTimer.singleShot(0, _apply)
        except Exception:
            pass

    def _fieldfox_apply_on_power(self, panel: FieldFoxSAPanel, on: bool):
        """On global Power On, sync FieldFox viewing window to the loaded
        alias/UI settings automatically (no need to click Apply). On Power Off,
        pause streaming so the plot stops updating."""
        try:
            if on:
                # Ensure the instrument is connected before applying settings
                if getattr(panel.sa, 'inst', None) is None and hasattr(panel, 'on_connect'):
                    try:
                        panel.on_connect()
                    except Exception:
                        pass

                def _apply(attempt: int = 0):
                    try:
                        if getattr(panel.sa, 'inst', None) is None:
                            if attempt < 5 and hasattr(panel, 'on_connect'):
                                try:
                                    panel.on_connect()
                                except Exception:
                                    pass
                                QtCore.QTimer.singleShot(500, lambda: _apply(attempt + 1))
                            return
                        # Make sure streaming is enabled so the plot refreshes
                        if hasattr(panel, 'streaming_enabled'):
                            panel.streaming_enabled = True
                        if hasattr(panel, 'stream_btn'):
                            try:
                                panel.stream_btn.blockSignals(True)
                                panel.stream_btn.setChecked(True)
                                panel.stream_btn.setText('Pause Streaming')
                            finally:
                                panel.stream_btn.blockSignals(False)
                        # Push UI values (from loaded alias) to the instrument
                        if hasattr(panel, 'apply_settings'):
                            panel.apply_settings()
                        if hasattr(panel, 'start_capture_thread'):
                            panel.start_capture_thread()
                    except Exception:
                        pass

                QtCore.QTimer.singleShot(0, _apply)
            else:
                # Pause streaming on Power Off
                if hasattr(panel, 'streaming_enabled'):
                    panel.streaming_enabled = False
                if hasattr(panel, 'stop_capture_thread'):
                    try:
                        panel.stop_capture_thread()
                    except Exception:
                        pass
                if hasattr(panel, 'stream_btn'):
                    try:
                        panel.stream_btn.blockSignals(True)
                        panel.stream_btn.setChecked(False)
                        panel.stream_btn.setText('Start Streaming')
                    finally:
                        panel.stream_btn.blockSignals(False)
        except Exception:
            pass

    # --- Auto-turn-off newly added panels ---
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

    # --- Replacement-candidate finder ---
    def _find_replacement_candidates(self, saved_resource: str, inst_type_hint: str,
                                      rm: pyvisa.ResourceManager = None) -> List[Tuple[str, str, str]]:
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

    # --- Global power on/off ---
    def power_off_all(self):
        """Turn off outputs/inputs for all instruments in tabs."""
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, KeithleyPanel):
                self._keithley_apply_settings(widget, False)
            elif isinstance(widget, HittiteSigGenPanel):
                self._hittite_apply_on_power(widget, False)
            elif isinstance(widget, KeysightELPanel):
                self._keysight_el_apply_settings(widget, False)
            elif isinstance(widget, KeysightE36233APanel):
                for ch in (1, 2):
                    self._e36233a_apply_channel(widget, ch, on=False)
            elif isinstance(widget, RhodeSchwarzSMAPanel):
                self._generic_output_toggle(widget, False)
            elif isinstance(widget, FieldFoxSAPanel):
                self._fieldfox_apply_on_power(widget, False)
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
                self._hittite_apply_on_power(widget, True)
            elif isinstance(widget, RhodeSchwarzSMAPanel):
                self._generic_output_toggle(widget, True)
            elif isinstance(widget, FieldFoxSAPanel):
                self._fieldfox_apply_on_power(widget, True)
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, KeysightELPanel):
                self._keysight_el_apply_settings(widget, True)
        if hasattr(self, 'test_power_toggle_btn'):
            self.test_power_toggle_btn.setChecked(True)
            self._update_test_power_toggle_btn(True)
        self._update_global_power_btns(True)
        self.statusBar().showMessage('All instrument outputs/inputs turned ON', 4000)

    # --- Sequence power on/off (legacy comma-separated order) ---
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
                    elif isinstance(widget, KeysightE36233APanel):
                        for ch in (1, 2):
                            self._e36233a_apply_channel(widget, ch, on=False)
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

    # --- Reset ---
    def reset_part(self):
        try:
            delay = float(self.reset_delay_edit.text())
        except Exception:
            delay = 2.0
        try:
            self._sequence_abort_flag = False
        except Exception:
            pass
        self._log(f'Reset requested: powering off, will power on in {delay} seconds')
        self.power_off_all()

        def _do_power_on():
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

    # --- Test-tab power toggle ---
    def on_test_power_toggle(self):
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
        if on is None:
            try:
                on = False
                if hasattr(self, 'test_power_toggle_btn') and self.test_power_toggle_btn.isChecked():
                    on = True
                if hasattr(self, 'test_tab_power_btn') and self.test_tab_power_btn.isChecked():
                    on = True
            except Exception:
                on = False
        try:
            if hasattr(self, 'test_power_toggle_btn'):
                self.test_power_toggle_btn.setChecked(on)
            if hasattr(self, 'test_tab_power_btn'):
                self.test_tab_power_btn.setChecked(on)
        except Exception:
            pass
        if on:
            try:
                self._update_test_power_toggle_btn(True)
            except Exception:
                pass
            try:
                self._run_power_sequence()
            except Exception:
                pass
        else:
            try:
                self._update_test_power_toggle_btn(False)
            except Exception:
                pass
            try:
                self.power_off_all()
            except Exception:
                pass

    def _update_global_power_btns(self, on):
        if hasattr(self, 'test_power_toggle_btn'):
            if on:
                self.test_power_toggle_btn.setStyleSheet('background-color: #4CAF50; color: white;')
            else:
                self.test_power_toggle_btn.setStyleSheet('background-color: #F44336; color: white;')

    def _update_test_power_toggle_btn(self, on):
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

    # --- Power-sequence execution ---
    def _seq_get_instrument_channels(self, name):
        """Return [(channel_number, channel_label), ...] for a sequenceable
        multi-channel supply identified by its tab name. Used by the power
        sequence builder to offer per-channel options."""
        try:
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == name:
                    w = self.tabs.widget(i)
                    if isinstance(w, KeysightE36233APanel):
                        labels = getattr(w, 'channel_labels', ['1', '2'])
                        out = []
                        for idx in range(2):
                            lbl = labels[idx] if idx < len(labels) else str(idx + 1)
                            out.append((idx + 1, lbl))
                        return out
        except Exception:
            pass
        return []

    def _e36233a_apply_channel(self, panel, ch, on=True):
        """Apply set-points and output state to a single E36233A channel."""
        supply = getattr(panel, 'supply', None)
        if supply is None:
            return
        try:
            if on:
                if hasattr(panel, 'sync_active_channel'):
                    panel.sync_active_channel()
                volts = getattr(panel, 'channel_voltages', ['0.0', '0.0'])
                currs = getattr(panel, 'channel_currents', ['0.0', '0.0'])
                v = volts[ch - 1] if (ch - 1) < len(volts) else '0.0'
                c = currs[ch - 1] if (ch - 1) < len(currs) else '0.0'
                supply.set_voltage(ch, v)
                supply.set_current(ch, c)
                supply.output_on(ch)
            else:
                supply.output_off(ch)
            if getattr(panel, '_active_channel_index', 0) == (ch - 1) and hasattr(panel, 'onoff_btn'):
                panel.onoff_btn.setChecked(on)
                panel.is_on = on
                if hasattr(panel, '_update_onoff_btn_color'):
                    panel._update_onoff_btn_color(on)
        except Exception:
            pass

    def _run_power_sequence(self, on_complete=None):
        """Run the configured power-up sequence."""
        sequence = self.power_seq_builder.get_sequence()
        use_seq = self.power_seq_builder.use_sequence()
        if use_seq and sequence:
            def run_step(idx):
                if getattr(self, '_sequence_abort_flag', False):
                    self._log('Sequence aborted by user')
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
                if item.startswith('KeithleyChannel: '):
                    name = item[len('KeithleyChannel: '):]
                    if 'Channel' in name:
                        parts = name.split('Channel')
                        tab_name = parts[0].strip()
                        try:
                            ch = int(parts[1].strip())
                        except Exception:
                            ch = None
                        for i in range(self.tabs.count()):
                            if self.tabs.tabText(i) == tab_name:
                                widget = self.tabs.widget(i)
                                if isinstance(widget, KeithleyPanel) and widget.inst and ch:
                                    try:
                                        V = float(widget.vol_edits[ch].text())
                                        I = float(widget.iam_edits[ch].text())
                                    except Exception:
                                        V, I = 0.0, 0.03
                                    widget.inst.set_voltage(ch, V)
                                    widget.inst.set_current(ch, I)
                                    for other_ch in (1, 2, 3):
                                        if other_ch != ch and not widget.output_btns[other_ch].isChecked():
                                            widget.inst.set_voltage(other_ch, 0.0)
                                            widget.inst.set_current(other_ch, 0.0)
                                    if not widget.output_btns[ch].isChecked():
                                        widget.inst.set_output(ch, True)
                                    widget.output_btns[ch].setChecked(True)
                                    widget.output_btns[ch].setText('Output On')
                                break
                    QtCore.QTimer.singleShot(100, lambda: run_step(idx + 1))
                elif item.startswith('SupplyChannel: '):
                    name = item[len('SupplyChannel: '):]
                    tab_name, ch = name, None
                    if 'Channel' in name:
                        parts = name.split('Channel')
                        tab_name = parts[0].strip()
                        try:
                            ch = int(parts[1].strip())
                        except Exception:
                            ch = None
                    if ch is not None:
                        for i in range(self.tabs.count()):
                            if self.tabs.tabText(i) == tab_name:
                                widget = self.tabs.widget(i)
                                if isinstance(widget, KeysightE36233APanel):
                                    self._e36233a_apply_channel(widget, ch, on=True)
                                break
                    QtCore.QTimer.singleShot(100, lambda: run_step(idx + 1))
                elif item.startswith('Instrument: '):
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
                                            widget.output_btns[ch].setChecked(True)
                                            widget.output_btns[ch].setText('Output On')
                                        except Exception:
                                            pass
                                    if hasattr(widget, 'master_out_btn'):
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
                                            mode_combo = getattr(widget, f'mode_combo_ch{ch}', None)
                                            mode_value_edit = getattr(widget, f'mode_value_ch{ch}', None)
                                            ramp_enable = getattr(widget, f'ramp_enable_ch{ch}', None)
                                            rise_time_edit = getattr(widget, f'rise_time_ch{ch}', None)
                                            input_toggle = getattr(widget, f'input_toggle_ch{ch}', None)
                                            if not mode_combo or not mode_value_edit:
                                                continue
                                            mode = mode_combo.currentText()
                                            try:
                                                value = float(mode_value_edit.text())
                                            except Exception:
                                                value = 0.0
                                            ramp_enabled = ramp_enable.isChecked() if ramp_enable else False
                                            try:
                                                rise_time = float(rise_time_edit.text()) if rise_time_edit else 0.0
                                            except Exception:
                                                rise_time = 0.0
                                            if mode == 'Disable':
                                                widget.dev.set_input(ch, False)
                                                if input_toggle:
                                                    input_toggle.setChecked(False)
                                                    input_toggle.setText('Input Off')
                                                continue
                                            widget.dev.set_mode(ch, mode)
                                            widget.dev.set_input(ch, True)
                                            if ramp_enabled and rise_time > 0:
                                                import numpy as np
                                                import time
                                                steps = 20
                                                for v in np.linspace(0, value, steps):
                                                    widget.dev.set_parameter(ch, mode, v)
                                                    QtWidgets.QApplication.processEvents()
                                                    time.sleep(rise_time / steps)
                                                widget.dev.set_parameter(ch, mode, value)
                                            else:
                                                widget.dev.set_parameter(ch, mode, value)
                                            if input_toggle:
                                                input_toggle.setChecked(True)
                                                input_toggle.setText('Input On')
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
                            elif isinstance(widget, KeysightE36233APanel):
                                for ch in (1, 2):
                                    self._e36233a_apply_channel(widget, ch, on=True)
                    QtCore.QTimer.singleShot(100, lambda: run_step(idx + 1))
                elif item.startswith('Delay: '):
                    delay_val = float(item[len('Delay: '):-3])
                    self._log(f'Waiting {delay_val} s')
                    QtCore.QTimer.singleShot(int(delay_val * 1000), lambda: run_step(idx + 1))
                else:
                    run_step(idx + 1)
            run_step(0)
        else:
            self.power_on_all()
            if on_complete:
                try:
                    QtCore.QTimer.singleShot(100, on_complete)
                except Exception:
                    try:
                        on_complete()
                    except Exception:
                        pass
