from PyQt5 import QtWidgets


class _RefreshOnOpenComboBox(QtWidgets.QComboBox):
    """A combo box that re-populates itself each time the dropdown is opened.

    This ensures the latest user-given channel names are shown even if they
    were edited after the combo was last refreshed.
    """

    def __init__(self, refresh_callback=None, parent=None):
        super().__init__(parent)
        self._refresh_callback = refresh_callback

    def showPopup(self):
        if self._refresh_callback:
            try:
                self._refresh_callback()
            except Exception:
                pass
        super().showPopup()


class PowerSequenceBuilder(QtWidgets.QGroupBox):
    def set_sequence(self, sequence):
        self.seq_list.clear()
        for item in sequence:
            self.seq_list.addItem(item)

    def set_use_sequence(self, use_seq):
        self.enable_checkbox.setChecked(bool(use_seq))
    def __init__(self, parent=None, get_instruments_callback=None):
        super().__init__('Power-Up Sequence Builder', parent)
        self.get_instruments_callback = get_instruments_callback
        layout = QtWidgets.QVBoxLayout(self)
        add_row = QtWidgets.QHBoxLayout()
        self.instr_combo = _RefreshOnOpenComboBox(refresh_callback=self.refresh_instr_combo)
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
        if not self.get_instruments_callback:
            return
        for entry in self.get_instruments_callback():
            # Each entry may be a plain name (str), a (name, n_channels) pair,
            # or a (name, [channel_label, ...]) pair.
            if isinstance(entry, (tuple, list)):
                name = entry[0]
                ch_info = entry[1] if len(entry) > 1 else 0
            else:
                name = entry
                ch_info = 0
            if not name:
                continue
            # Whole-instrument entry: display text == sequence token.
            self.instr_combo.addItem(name, name)
            # Normalize channel info into a list of display labels.
            if isinstance(ch_info, (list, tuple)):
                channel_labels = list(ch_info)
            else:
                channel_labels = [f'CH{ch}' for ch in range(1, int(ch_info) + 1)]
            # Expand multi-channel supplies into per-channel options.  The
            # display shows the user-given channel name; the item data holds the
            # canonical "Name Channel N" token the run-sequence expects.
            for idx, label in enumerate(channel_labels, start=1):
                token = f'{name} Channel {idx}'
                display = f'{name} \u2014 {label} (Ch {idx})'
                self.instr_combo.addItem(display, token)
    def add_instr(self):
        # The display text may be a friendly channel name; the canonical token
        # used by the run-sequence is stored as the combo item data.
        token = self.instr_combo.currentData()
        if token is None:
            token = self.instr_combo.currentText()
        if token:
            if 'Channel' in token:
                self.seq_list.addItem(f'KeithleyChannel: {token}')
            else:
                self.seq_list.addItem(f'Instrument: {token}')
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
