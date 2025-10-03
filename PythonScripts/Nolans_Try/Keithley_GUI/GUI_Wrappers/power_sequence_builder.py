from PyQt5 import QtWidgets

class PowerSequenceBuilder(QtWidgets.QGroupBox):
    def __init__(self, parent=None, get_instruments_callback=None):
        super().__init__('Power-Up Sequence Builder', parent)
        self.get_instruments_callback = get_instruments_callback
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
                self.instr_combo.addItem(name)
    def add_instr(self):
        name = self.instr_combo.currentText()
        if name:
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