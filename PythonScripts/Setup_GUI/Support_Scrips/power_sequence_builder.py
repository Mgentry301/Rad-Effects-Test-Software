from PyQt5 import QtWidgets

class PowerSequenceBuilder(QtWidgets.QGroupBox):
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
        layout.addWidget(self.seq_list)
        self.remove_btn = QtWidgets.QPushButton('Remove Selected')
        self.remove_btn.clicked.connect(self.remove_selected)
        layout.addWidget(self.remove_btn)
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
    def get_sequence(self):
        return [self.seq_list.item(i).text() for i in range(self.seq_list.count())]
    def use_sequence(self):
        return self.enable_checkbox.isChecked()
