import re

from PyQt5 import QtWidgets

class PowerSequenceBuilder(QtWidgets.QGroupBox):
    # Sequence entries for individual channels may carry optional per-step
    # voltage/current overrides encoded as a suffix, e.g.
    #   "KeithleyChannel: Keithley1 Channel 2 @ V=3.3 I=0.1"
    # When no suffix is present the value configured on the instrument tab is
    # used (backwards-compatible with older saved configs).
    @staticmethod
    def parse_item(text):
        """Split an entry into (base_label, voltage_override, current_override).

        voltage_override / current_override are floats, or None when not set."""
        if '@' not in text:
            return text.strip(), None, None
        base, _, sp = text.partition('@')
        v = i = None
        mv = re.search(r'V=([-\d.]+)', sp)
        mi = re.search(r'I=([-\d.]+)', sp)
        if mv:
            try:
                v = float(mv.group(1))
            except Exception:
                v = None
        if mi:
            try:
                i = float(mi.group(1))
            except Exception:
                i = None
        return base.strip(), v, i

    @staticmethod
    def format_item(base, v, i):
        """Rebuild an entry string from a base label and optional overrides."""
        parts = []
        if v is not None:
            parts.append(f'V={v:g}')
        if i is not None:
            parts.append(f'I={i:g}')
        if not parts:
            return base.strip()
        return f'{base.strip()} @ ' + ' '.join(parts)

    def set_sequence(self, sequence):
        self.seq_list.clear()
        for item in sequence:
            self.seq_list.addItem(item)

    def set_use_sequence(self, use_seq):
        self.enable_checkbox.setChecked(bool(use_seq))
    def __init__(self, parent=None, get_instruments_callback=None, get_channels_callback=None):
        super().__init__('Power-Up Sequence Builder', parent)
        self.get_instruments_callback = get_instruments_callback
        # Optional callback: given an instrument (tab) name, returns a list of
        # (channel_number, channel_label) tuples for multi-channel supplies.
        self.get_channels_callback = get_channels_callback
        layout = QtWidgets.QVBoxLayout(self)
        add_row = QtWidgets.QHBoxLayout()
        self.instr_combo = QtWidgets.QComboBox()
        self.refresh_instr_combo()
        add_row.addWidget(QtWidgets.QLabel('Add Instrument:'))
        add_row.addWidget(self.instr_combo)
        self.add_instr_btn = QtWidgets.QPushButton('Add')
        self.add_instr_btn.clicked.connect(self.add_instr)
        add_row.addWidget(self.add_instr_btn)
        self.add_delay_btn = QtWidgets.QPushButton('Add Delay Block')
        self.add_delay_btn.clicked.connect(self.add_delay)
        add_row.addWidget(self.add_delay_btn)
        layout.addLayout(add_row)
        self.seq_list = QtWidgets.QListWidget()
        self.seq_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.seq_list.itemDoubleClicked.connect(lambda _item: self.edit_setpoints())
        layout.addWidget(self.seq_list)
        btn_row = QtWidgets.QHBoxLayout()
        self.edit_btn = QtWidgets.QPushButton('Edit Setpoints…')
        self.edit_btn.setToolTip(
            'Set a specific voltage/current for the selected channel step. '
            'Leave blank to use the value from the instrument tab.')
        self.edit_btn.clicked.connect(self.edit_setpoints)
        btn_row.addWidget(self.edit_btn)
        self.remove_btn = QtWidgets.QPushButton('Remove Selected')
        self.remove_btn.clicked.connect(self.remove_selected)
        btn_row.addWidget(self.remove_btn)
        layout.addLayout(btn_row)
        self.enable_checkbox = QtWidgets.QCheckBox('Use Power-Up Sequence')
        self.enable_checkbox.setChecked(False)
        layout.addWidget(self.enable_checkbox)
    def refresh_instr_combo(self):
        self.instr_combo.clear()
        if self.get_instruments_callback:
            for name in self.get_instruments_callback():
                # Whole instrument
                self.instr_combo.addItem(name, ('instrument', name, None))
                # Individual Keithley channels (fixed 1-3)
                if name.startswith('Keithley'):
                    for ch in (1, 2, 3):
                        self.instr_combo.addItem(
                            f'{name} Channel {ch}', ('keithley_channel', name, ch))
                # Individual channels for other multi-channel supplies (e.g. E36233A)
                elif self.get_channels_callback:
                    try:
                        channels = self.get_channels_callback(name) or []
                    except Exception:
                        channels = []
                    for ch_num, ch_label in channels:
                        label = (str(ch_label).strip() or str(ch_num))
                        disp = f'{name} Channel {ch_num}'
                        if label and label != str(ch_num):
                            disp = f'{name} Channel {ch_num} ({label})'
                        self.instr_combo.addItem(disp, ('supply_channel', name, ch_num))
    def add_instr(self):
        data = self.instr_combo.currentData()
        if not data:
            name = self.instr_combo.currentText()
            if name:
                self.seq_list.addItem(f'Instrument: {name}')
            return
        kind, name, ch = data
        if kind == 'keithley_channel':
            self.seq_list.addItem(f'KeithleyChannel: {name} Channel {ch}')
        elif kind == 'supply_channel':
            self.seq_list.addItem(f'SupplyChannel: {name} Channel {ch}')
        else:
            self.seq_list.addItem(f'Instrument: {name}')
    def add_delay(self):
        delay, ok = QtWidgets.QInputDialog.getDouble(self, 'Add Delay', 'Delay (seconds):', 1.0, 0.1, 60.0, 1)
        if ok:
            self.seq_list.addItem(f'Delay: {delay:.1f} s')
    def remove_selected(self):
        for item in self.seq_list.selectedItems():
            self.seq_list.takeItem(self.seq_list.row(item))
    def edit_setpoints(self):
        items = self.seq_list.selectedItems()
        if not items:
            QtWidgets.QMessageBox.information(
                self, 'Edit Setpoints', 'Select a channel step first.')
            return
        item = items[0]
        base, v, i = self.parse_item(item.text())
        if not (base.startswith('KeithleyChannel:') or base.startswith('SupplyChannel:')):
            QtWidgets.QMessageBox.information(
                self, 'Edit Setpoints',
                'Voltage/current setpoints can only be set on individual power-supply '
                'channel steps (Keithley or E36233A channels). Whole-instrument and '
                'delay steps are not supported.')
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Channel Setpoints')
        form = QtWidgets.QFormLayout(dlg)
        label = QtWidgets.QLabel(base)
        label.setWordWrap(True)
        form.addRow(label)
        v_edit = QtWidgets.QLineEdit('' if v is None else f'{v:g}')
        i_edit = QtWidgets.QLineEdit('' if i is None else f'{i:g}')
        v_edit.setPlaceholderText('use instrument tab value')
        i_edit.setPlaceholderText('use instrument tab value')
        form.addRow('Voltage (V):', v_edit)
        form.addRow('Current (A):', i_edit)
        info = QtWidgets.QLabel('Leave a field blank to use the value set on the instrument tab.')
        info.setWordWrap(True)
        form.addRow(info)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        def _parse(text):
            text = text.strip()
            if not text:
                return None
            try:
                return float(text)
            except ValueError:
                return None
        new_v = _parse(v_edit.text())
        new_i = _parse(i_edit.text())
        if v_edit.text().strip() and new_v is None:
            QtWidgets.QMessageBox.warning(self, 'Edit Setpoints', 'Voltage must be a number.')
            return
        if i_edit.text().strip() and new_i is None:
            QtWidgets.QMessageBox.warning(self, 'Edit Setpoints', 'Current must be a number.')
            return
        item.setText(self.format_item(base, new_v, new_i))
    def get_sequence(self):
        return [self.seq_list.item(i).text() for i in range(self.seq_list.count())]
    def use_sequence(self):
        return self.enable_checkbox.isChecked()
