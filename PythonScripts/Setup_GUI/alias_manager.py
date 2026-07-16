"""
Alias / Settings-tab mixin for MainWindow.

Provides alias-profile management (save, load, delete, auto-select),
unmapped-instrument scanning, and the Settings tab UI builder.
"""
import os
import json

from PyQt5 import QtWidgets, QtCore
import pyvisa


class AliasMixin:
    """Mixin that adds alias-profile management to MainWindow."""

    # ---------- Alias profiles (Settings tab) ----------
    def _alias_profile_path(self, name: str) -> str:
        return os.path.join(self.alias_dir, f"{name}.json")

    def _list_alias_profiles(self):
        try:
            return [os.path.splitext(f)[0] for f in os.listdir(self.alias_dir) if f.lower().endswith('.json')]
        except Exception:
            return []

    def _refresh_alias_profiles(self):
        try:
            names = sorted(self._list_alias_profiles())
            self.alias_profile_combo.clear()
            for n in names:
                self.alias_profile_combo.addItem(n)
            if self.alias_profile:
                idx = self.alias_profile_combo.findText(self.alias_profile)
                if idx != -1:
                    self.alias_profile_combo.setCurrentIndex(idx)
        except Exception:
            pass

    def _apply_alias_profile_to_ui(self):
        try:
            aliases = sorted(self.alias_map.keys())
            # Suspend itemChanged while we rebuild the list programmatically
            self._suspend_alias_rename = True
            try:
                self.alias_list.clear()
                if hasattr(self, 'alias_res_list'):
                    self.alias_res_list.clear()
                for k in aliases:
                    item = QtWidgets.QListWidgetItem(k)
                    # Store the current alias name so we can detect renames
                    item.setData(QtCore.Qt.UserRole, k)
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
                    item.setToolTip('Double-click to rename this alias for this bench')
                    self.alias_list.addItem(item)
                    if hasattr(self, 'alias_res_list'):
                        self.alias_res_list.addItem(self.alias_map.get(k, ''))
            finally:
                self._suspend_alias_rename = False
            self.alias_profile_name.setText(self.alias_profile or '')
        except Exception:
            pass

    def _on_alias_item_renamed(self, item):
        """Handle inline rename of an alias in the Settings tab.

        Updates self.alias_map (preserving the VISA resource), persists to the
        current profile, and updates the detected-instrument combo so the new
        name appears immediately without a full VISA rescan.
        """
        if getattr(self, '_suspend_alias_rename', False):
            return
        try:
            new_name = (item.text() or '').strip()
            old_name = item.data(QtCore.Qt.UserRole)
        except Exception:
            return
        if not old_name:
            return
        # No-op
        if new_name == old_name:
            return

        # Validation: empty or duplicate -> revert
        def _revert(msg=None):
            self._suspend_alias_rename = True
            try:
                item.setText(old_name)
            finally:
                self._suspend_alias_rename = False
            if msg:
                try:
                    QtWidgets.QMessageBox.warning(self, 'Rename failed', msg)
                except Exception:
                    pass

        if not new_name:
            _revert('Alias name cannot be empty.')
            return
        if new_name in (self.alias_map or {}) and new_name != old_name:
            _revert(f'Alias "{new_name}" already exists in this profile.')
            return

        # Apply rename to alias_map (preserve order so the lists stay aligned)
        try:
            new_map = {}
            for k, v in (self.alias_map or {}).items():
                if k == old_name:
                    new_map[new_name] = v
                else:
                    new_map[k] = v
            self.alias_map = new_map
        except Exception:
            _revert('Internal error renaming alias.')
            return

        # Update the stored "current name" so future edits compare correctly
        try:
            item.setData(QtCore.Qt.UserRole, new_name)
        except Exception:
            pass

        # Update detected_combo so the renamed alias re-appears in the
        # "Detected" dropdown without a full VISA rescan.
        try:
            res = (self.alias_map or {}).get(new_name)
            if res and hasattr(self, 'detected_combo'):
                for i in range(self.detected_combo.count()):
                    data = self.detected_combo.itemData(i)
                    if isinstance(data, tuple) and len(data) >= 2 and data[0] == res:
                        inst_type = data[1] if len(data) > 1 else ''
                        self.detected_combo.setItemText(i, new_name)
                        self.detected_combo.setItemData(i, (res, inst_type, new_name))
                        break
        except Exception:
            pass

        # Persist to the current profile (if one is loaded)
        try:
            if getattr(self, 'alias_profile', ''):
                self._save_alias_profile(self.alias_profile)
            else:
                self.statusBar().showMessage(
                    f'Renamed "{old_name}" -> "{new_name}" (no profile loaded — Save Profile to persist)', 5000)
        except Exception:
            pass

        try:
            self.statusBar().showMessage(f'Renamed alias "{old_name}" -> "{new_name}"', 4000)
        except Exception:
            pass

    def _rename_selected_alias(self):
        """Trigger inline edit on the currently selected alias item."""
        try:
            item = self.alias_list.currentItem()
            if item is None:
                QtWidgets.QMessageBox.information(self, 'No selection',
                    'Select an alias on the left to rename, or double-click it.')
                return
            self.alias_list.editItem(item)
        except Exception:
            pass

    def _sync_alias_map_from_lists(self):
        """Rebuild alias_map from the current lists (index-aligned)."""
        try:
            if not hasattr(self, 'alias_res_list'):
                return
            new_map = {}
            n = min(self.alias_list.count(), self.alias_res_list.count())
            for i in range(n):
                alias_item = self.alias_list.item(i)
                res_item = self.alias_res_list.item(i)
                if not alias_item:
                    continue
                alias = alias_item.text()
                res = res_item.text() if res_item else ''
                new_map[alias] = res
            self.alias_map = new_map
            self.statusBar().showMessage('Updated alias mapping from drag-and-drop', 3000)
        except Exception:
            pass
        try:
            if hasattr(self, 'alias_profile_combo'):
                self._refresh_alias_profiles()
        except Exception:
            pass

    def _load_alias_profile(self, name: str):
        try:
            path = self._alias_profile_path(name)
            if not os.path.exists(path):
                return
            # Power off all instruments before loading a new alias setup so
            # we never leave outputs enabled on the previous bench mapping.
            try:
                if hasattr(self, 'power_off_all'):
                    self.power_off_all()
            except Exception:
                pass
            with open(path, 'r') as f:
                data = json.load(f)
            self.alias_profile = data.get('name', name)
            self.alias_map = data.get('aliases', {}) or {}
            self._apply_alias_profile_to_ui()
            self.statusBar().showMessage(f"Loaded alias profile: {self.alias_profile}", 4000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Alias load failed', str(e))

    def _save_alias_profile(self, name: str = None):
        try:
            name = name or self.alias_profile_name.text().strip()
            if not name:
                QtWidgets.QMessageBox.information(self, 'Missing name', 'Enter a profile name.')
                return
            payload = {'name': name, 'aliases': self.alias_map}
            path = self._alias_profile_path(name)
            with open(path, 'w') as f:
                json.dump(payload, f, indent=2)
            self.alias_profile = name
            self._refresh_alias_profiles()
            self._apply_alias_profile_to_ui()
            self.statusBar().showMessage(f"Saved alias profile: {name}", 4000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Alias save failed', str(e))

    def _delete_alias_profile(self):
        try:
            name = self.alias_profile_combo.currentText().strip()
            if not name:
                return
            resp = QtWidgets.QMessageBox.question(self, 'Delete profile', f'Delete alias profile "{name}"?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
            if resp != QtWidgets.QMessageBox.Yes:
                return
            path = self._alias_profile_path(name)
            if os.path.exists(path):
                os.remove(path)
            if self.alias_profile == name:
                self.alias_profile = ''
                self.alias_map = {}
            self._refresh_alias_profiles()
            self._apply_alias_profile_to_ui()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Alias delete failed', str(e))

    def _build_aliases_from_resources(self, resources: list):
        """Classify and assign type+index aliases for current VISA resources."""
        try:
            rm = pyvisa.ResourceManager()
        except Exception:
            rm = None
        cats = {}
        for res in resources:
            typ = 'Unknown'
            idn = ''
            try:
                if rm:
                    inst = rm.open_resource(res, timeout=1500)
                    try:
                        try:
                            inst.clear()
                        except Exception:
                            pass
                        idn = inst.query('*IDN?').upper()
                    finally:
                        try:
                            inst.close()
                        except Exception:
                            pass
            except Exception:
                idn = ''
            if 'KEITHLEY' in idn or '2230' in idn:
                typ = 'Keithley'
            elif 'EL34243' in idn or ('KEYSIGHT' in idn and 'ELECTRONIC LOAD' in idn):
                typ = 'Keysight EL'
            elif 'E36233A' in idn:
                typ = 'E36233A'
            elif 'FIELDFOX' in idn or 'N99' in idn or 'HANDHELD SPECTRUM' in idn:
                typ = 'FieldFox'
            elif 'HITTITE' in idn or 'SIG GEN' in idn:
                typ = 'Hittite'
            elif 'ROHDE' in idn or 'SCHWARZ' in idn or 'SMA' in idn:
                typ = 'RohdeSchwarz SMA'
            cats.setdefault(typ, []).append(res)
        new_map = {}
        for typ, lst in cats.items():
            for i, res in enumerate(sorted(lst)):
                if typ == 'Keithley':
                    alias = f'Keithley {i}'
                elif typ == 'FieldFox':
                    alias = f'FieldFox {i}'
                else:
                    alias = f'{typ} {i}'
                new_map[alias] = res
        self.alias_map = new_map
        self._apply_alias_profile_to_ui()

    def _refresh_unmapped_instruments(self):
        """Scan VISA and list instruments not present in current alias_map."""
        try:
            self.unmapped_list.clear()
        except Exception:
            pass
        try:
            rm = pyvisa.ResourceManager()
            resources = list(rm.list_resources())
        except Exception:
            resources = []
        mapped = set((self.alias_map or {}).values())

        def classify(res: str) -> str:
            try:
                inst = rm.open_resource(res, timeout=1200)
                try:
                    try:
                        inst.clear()
                    except Exception:
                        pass
                    idn = inst.query('*IDN?')
                finally:
                    try:
                        inst.close()
                    except Exception:
                        pass
                lidn = (idn or '').upper()
                if 'KEITHLEY' in lidn or '2230' in lidn:
                    return 'Keithley'
                if 'EL34243' in lidn or ('KEYSIGHT' in lidn and 'ELECTRONIC LOAD' in lidn):
                    return 'Keysight EL'
                if 'E36233A' in lidn:
                    return 'E36233A'
                if 'FIELDFOX' in lidn or 'N99' in lidn or 'HANDHELD SPECTRUM' in lidn:
                    return 'FieldFox'
                if 'HITTITE' in lidn or 'SIG GEN' in lidn:
                    return 'Hittite'
                if 'ROHDE' in lidn or 'SCHWARZ' in lidn or 'SMA' in lidn:
                    return 'RohdeSchwarz SMA'
                return 'Unknown'
            except Exception:
                return 'Unknown'

        try:
            for res in resources:
                if res in mapped:
                    continue
                typ = classify(res)
                short = res.split('::')[3] if '::' in res and len(res.split('::')) > 3 else res
                item = QtWidgets.QListWidgetItem(f'{short}    ({typ})\n{res}')
                item.setData(QtCore.Qt.UserRole, (res, typ))
                self.unmapped_list.addItem(item)
            self.statusBar().showMessage('Unmapped instruments list refreshed', 3000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Scan failed', str(e))

    def _add_selected_unmapped_to_profile(self, add_all: bool = False):
        """Add selected (or all) unmapped instruments into the current alias profile."""
        try:
            if not self.alias_profile:
                self.alias_profile = self.alias_profile or 'default'
        except Exception:
            pass
        try:
            items = []
            if add_all:
                for i in range(self.unmapped_list.count()):
                    items.append(self.unmapped_list.item(i))
            else:
                items = self.unmapped_list.selectedItems() or []
            if not items:
                QtWidgets.QMessageBox.information(self, 'No selection', 'No instruments selected to add.')
                return
            counters = {}
            try:
                for alias in (self.alias_map or {}).keys():
                    base = ''.join(ch for ch in alias if not ch.isdigit()).strip()
                    num = ''.join(ch for ch in alias if ch.isdigit())
                    if base:
                        counters[base] = max(counters.get(base, -1), int(num) if num.isdigit() else -1)
            except Exception:
                pass
            for it in items:
                res, typ = it.data(QtCore.Qt.UserRole)
                base = {
                    'Keithley': 'Keithley',
                    'Keysight EL': 'Keysight EL',
                    'E36233A': 'E36233A',
                    'FieldFox': 'FieldFox',
                    'Hittite': 'Hittite',
                    'RohdeSchwarz SMA': 'RohdeSchwarz SMA',
                }.get(typ, 'Unknown')
                idx = counters.get(base, -1) + 1
                counters[base] = idx
                alias = f'{base} {idx}' if base != 'Unknown' else f'Unknown {idx}'
                self.alias_map[alias] = res
            self._apply_alias_profile_to_ui()
            try:
                if self.alias_profile:
                    self._save_alias_profile(self.alias_profile)
            except Exception:
                pass
            try:
                for it in items:
                    row = self.unmapped_list.row(it)
                    self.unmapped_list.takeItem(row)
            except Exception:
                pass
            self.statusBar().showMessage('Added instrument(s) to alias profile', 3000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Add failed', str(e))

    def _suggest_aliases_from_scan(self):
        """Scan VISA and populate alias_map with suggested aliases for all detected instruments."""
        try:
            rm = pyvisa.ResourceManager()
            resources = list(rm.list_resources())
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Scan failed', str(e))
            return
        suggestion = {}
        try:
            cats = {}
            for res in resources:
                typ = 'Unknown'
                idn = ''
                try:
                    inst = rm.open_resource(res, timeout=1200)
                    try:
                        try:
                            inst.clear()
                        except Exception:
                            pass
                        idn = inst.query('*IDN?').upper()
                    finally:
                        try:
                            inst.close()
                        except Exception:
                            pass
                except Exception:
                    idn = ''
                if 'KEITHLEY' in idn or '2230' in idn:
                    typ = 'Keithley'
                elif 'EL34243' in idn or ('KEYSIGHT' in idn and 'ELECTRONIC LOAD' in idn):
                    typ = 'Keysight EL'
                elif 'E36233A' in idn:
                    typ = 'E36233A'
                elif 'FIELDFOX' in idn or 'N99' in idn or 'HANDHELD SPECTRUM' in idn:
                    typ = 'FieldFox'
                elif 'HITTITE' in idn or 'SIG GEN' in idn:
                    typ = 'Hittite'
                elif 'ROHDE' in idn or 'SCHWARZ' in idn or 'SMA' in idn:
                    typ = 'RohdeSchwarz SMA'
                cats.setdefault(typ, []).append(res)
            for typ, lst in cats.items():
                for i, res in enumerate(sorted(lst)):
                    alias = f'{typ} {i}' if typ != 'Unknown' else f'Unknown {i}'
                    suggestion[alias] = res
        except Exception:
            suggestion = {f'Resource {i}': res for i, res in enumerate(resources)}
        try:
            resp = QtWidgets.QMessageBox.question(
                self, 'Apply suggested aliases',
                'Apply suggested aliases to current profile?\nYes: merge (keep existing, add new)\nNo: replace current profile',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Yes)
        except Exception:
            resp = QtWidgets.QMessageBox.Yes
        if resp == QtWidgets.QMessageBox.Cancel:
            return
        try:
            if resp == QtWidgets.QMessageBox.No:
                self.alias_map = suggestion
            else:
                existing_res = set(self.alias_map.values()) if self.alias_map else set()
                for alias, res in suggestion.items():
                    if res in existing_res:
                        continue
                    new_alias = alias
                    k = 1
                    while new_alias in self.alias_map:
                        new_alias = f'{alias} {k}'
                        k += 1
                    self.alias_map[new_alias] = res
            self._apply_alias_profile_to_ui()
            if self.alias_profile:
                self._save_alias_profile(self.alias_profile)
            self.statusBar().showMessage('Aliases updated from scan', 3000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Apply failed', str(e))

    def _auto_select_alias_profile(self, resources: list):
        """Auto-pick the best matching alias profile based on current resources."""
        try:
            profiles = self._list_alias_profiles()
            best = None
            best_score = -1
            res_set = set(resources)
            for name in profiles:
                try:
                    with open(self._alias_profile_path(name), 'r') as f:
                        data = json.load(f)
                    amap = data.get('aliases', {}) or {}
                    vals = set(amap.values())
                    score = len(vals & res_set)
                    if vals and vals <= res_set and len(vals) == len(res_set):
                        score += 1000
                    if score > best_score:
                        best_score = score
                        best = (name, amap)
                except Exception:
                    continue
            if best and (self.alias_profile != best[0]):
                self.alias_profile = best[0]
                self.alias_map = best[1]
                self._refresh_alias_profiles()
                self._apply_alias_profile_to_ui()
                self.statusBar().showMessage(f"Auto-selected alias profile: {self.alias_profile}", 5000)
        except Exception:
            pass

    # ---------- Settings tab UI ----------
    def _init_settings_tab(self):
        settings_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(settings_widget)
        # Profile row
        prow = QtWidgets.QHBoxLayout()
        self.alias_profile_combo = QtWidgets.QComboBox()
        self.alias_profile_combo.setMinimumWidth(220)
        self.alias_profile_name = QtWidgets.QLineEdit()
        self.alias_profile_name.setPlaceholderText('Profile name')
        self._refresh_alias_profiles()
        load_btn = QtWidgets.QPushButton('Load Profile')
        load_btn.clicked.connect(lambda: self._load_alias_profile(self.alias_profile_combo.currentText()))
        save_btn = QtWidgets.QPushButton('Save Profile')
        save_btn.clicked.connect(lambda: self._save_alias_profile(self.alias_profile_name.text()))
        del_btn = QtWidgets.QPushButton('Delete Profile')
        del_btn.clicked.connect(self._delete_alias_profile)
        prow.addWidget(QtWidgets.QLabel('Profile:'))
        prow.addWidget(self.alias_profile_combo)
        prow.addWidget(QtWidgets.QLabel('Name:'))
        prow.addWidget(self.alias_profile_name)
        prow.addWidget(load_btn)
        prow.addWidget(save_btn)
        prow.addWidget(del_btn)
        layout.addLayout(prow)
        # Alias mapping area
        layout.addWidget(QtWidgets.QLabel(
            'Alias names (left, double-click to rename per-bench) — drag VISA resources (right) to align:'))
        lists_row = QtWidgets.QHBoxLayout()
        self.alias_list = QtWidgets.QListWidget()
        # Allow per-bench renaming of alias labels via inline edit.
        self.alias_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.alias_list.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
            | QtWidgets.QAbstractItemView.SelectedClicked)
        self.alias_list.setDragEnabled(False)
        self.alias_list.setAcceptDrops(False)
        try:
            self.alias_list.itemChanged.connect(self._on_alias_item_renamed)
        except Exception:
            pass
        self.alias_res_list = QtWidgets.QListWidget()
        self.alias_res_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.alias_res_list.setDragEnabled(True)
        self.alias_res_list.setAcceptDrops(True)
        self.alias_res_list.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.alias_res_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        try:
            self.alias_res_list.model().rowsMoved.connect(lambda *args: self._sync_alias_map_from_lists())
        except Exception:
            pass
        lists_row.addWidget(self.alias_list, 1)
        lists_row.addWidget(self.alias_res_list, 2)
        layout.addLayout(lists_row)
        # Unmapped instruments area
        layout.addWidget(QtWidgets.QLabel('Unmapped instruments (present on VISA but not in this alias profile):'))
        self.unmapped_list = QtWidgets.QListWidget()
        self.unmapped_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.unmapped_list)
        # Controls
        controls_row = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton('Refresh Instruments')
        refresh_btn.setToolTip('Scan VISA and list devices not currently mapped in the alias profile')
        refresh_btn.clicked.connect(self._refresh_unmapped_instruments)
        add_sel_btn = QtWidgets.QPushButton('Add Selected to Profile')
        add_sel_btn.setToolTip('Add the selected unmapped instruments to this alias profile')
        add_sel_btn.clicked.connect(self._add_selected_unmapped_to_profile)
        add_all_btn = QtWidgets.QPushButton('Add All Missing')
        add_all_btn.setToolTip('Add all unmapped instruments to this alias profile')
        add_all_btn.clicked.connect(lambda: self._add_selected_unmapped_to_profile(add_all=True))
        controls_row.addWidget(refresh_btn)
        controls_row.addWidget(add_sel_btn)
        controls_row.addWidget(add_all_btn)
        controls_row.addStretch(1)
        layout.addLayout(controls_row)
        # Utilities row
        util_row = QtWidgets.QHBoxLayout()
        suggest_btn = QtWidgets.QPushButton('Suggest Aliases')
        suggest_btn.setToolTip('Automatically generate alias names for all detected instruments')
        suggest_btn.clicked.connect(self._suggest_aliases_from_scan)
        rename_btn = QtWidgets.QPushButton('Rename Selected Alias')
        rename_btn.setToolTip('Rename the selected alias (or just double-click it). '
                              'The new name is saved to the current bench profile and '
                              'shown in the Detected dropdown.')
        rename_btn.clicked.connect(self._rename_selected_alias)
        util_row.addWidget(suggest_btn)
        util_row.addWidget(rename_btn)
        util_row.addStretch(1)
        layout.addLayout(util_row)

        self.top_tabs.addTab(settings_widget, 'Settings')

    def _prompt_alias_startup(self):
        """Prompt user at startup to choose aliasing approach before any VISA scan."""
        if getattr(self, '_alias_prompt_done', False):
            return
        self._alias_prompt_done = True
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle('Aliasing Profile')
        box.setText('Choose an aliasing profile for this session:')
        generic_btn = box.addButton('Generic (auto-suggest)', QtWidgets.QMessageBox.AcceptRole)
        preconf_btn = box.addButton('Load preconfigured…', QtWidgets.QMessageBox.ActionRole)
        box.setIcon(QtWidgets.QMessageBox.Question)
        box.exec_()

        clicked = box.clickedButton()
        if clicked is preconf_btn:
            try:
                profiles = self._list_alias_profiles() or []
            except Exception:
                profiles = []
            if not profiles:
                QtWidgets.QMessageBox.information(self, 'No profiles', 'No preconfigured profiles found. Using generic aliasing.')
                self._alias_startup_choice = 'generic'
            else:
                name, ok = QtWidgets.QInputDialog.getItem(self, 'Load Profile', 'Select a profile:', profiles, 0, False)
                if ok and name:
                    try:
                        self._load_alias_profile(name)
                        self._alias_startup_choice = 'preconfigured'
                    except Exception as e:
                        QtWidgets.QMessageBox.warning(self, 'Load failed', f'Failed to load profile: {e}\nUsing generic instead.')
                        self._alias_startup_choice = 'generic'
                else:
                    self._alias_startup_choice = 'generic'
        else:
            self._alias_startup_choice = 'generic'

        try:
            self.on_scan_instruments()
        except Exception:
            pass
