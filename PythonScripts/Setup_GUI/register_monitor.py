"""
Live register monitor dialog.

Displays a table of register addresses defined in the active config /
``register_read_array``. While register recording is active, the dialog
polls the latest read values that the recording worker publishes on the
MainWindow and shows them next to the EXPECTED baseline so the operator
can spot register changes (e.g. SEU/SEFI events) in real time.

The dialog is intentionally non-modal so users can keep it open while
priming/recording from the main window.
"""
from __future__ import annotations

from typing import Iterable, List

from PyQt5 import QtCore, QtGui, QtWidgets


def _coerce_addr(value) -> int | None:
    """Best-effort conversion of a register identifier to an int address."""
    try:
        if isinstance(value, str):
            return int(value, 0)
        return int(value)
    except Exception:
        return None


def _fmt_value(val) -> tuple[str, str]:
    """Return (hex_str, dec_str) for a register value.

    Non-integer values (e.g. ``"ERR:..."``) are returned as-is in the hex
    column and blank in the dec column so error strings remain visible.
    """
    if isinstance(val, int):
        return (f'0x{val:X}', str(val))
    if val is None:
        return ('', '')
    return (str(val), '')


class RegisterMonitorDialog(QtWidgets.QDialog):
    """Non-modal live monitor for selected registers."""

    COL_MONITOR = 0
    COL_ADDR = 1
    COL_HEX = 2
    COL_DEC = 3
    COL_EXPECTED = 4
    COL_STATUS = 5
    COL_UPDATED = 6

    HEADERS = [
        'Monitor', 'Address', 'Latest (hex)', 'Latest (dec)',
        'Expected (hex)', 'Status', 'Last update (s)',
    ]

    def __init__(self, parent, registers: Iterable):
        super().__init__(parent)
        self.setWindowTitle('Register Live Monitor')
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)
        self.resize(720, 420)

        self._main = parent
        self._addrs: List[int] = []
        for r in registers:
            a = _coerce_addr(r)
            if a is not None and a not in self._addrs:
                self._addrs.append(a)

        layout = QtWidgets.QVBoxLayout(self)

        # Top control row
        top = QtWidgets.QHBoxLayout()
        self.status_lbl = QtWidgets.QLabel('Idle - start register recording to see live values')
        self.status_lbl.setStyleSheet('color: #555;')
        top.addWidget(self.status_lbl, 1)

        self.only_monitored_cb = QtWidgets.QCheckBox('Show only monitored')
        self.only_monitored_cb.toggled.connect(self._apply_filter)
        top.addWidget(self.only_monitored_cb)

        self.select_all_btn = QtWidgets.QPushButton('Select All')
        self.select_all_btn.clicked.connect(lambda: self._set_all_monitored(True))
        top.addWidget(self.select_all_btn)
        self.select_none_btn = QtWidgets.QPushButton('Select None')
        self.select_none_btn.clicked.connect(lambda: self._set_all_monitored(False))
        top.addWidget(self.select_none_btn)
        layout.addLayout(top)

        # Table
        self.table = QtWidgets.QTableWidget(len(self._addrs), len(self.HEADERS), self)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_STATUS, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        for row, addr in enumerate(self._addrs):
            cb = QtWidgets.QCheckBox()
            cb.setChecked(True)
            cb.toggled.connect(self._apply_filter)
            holder = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(holder)
            hl.setContentsMargins(4, 0, 4, 0)
            hl.addWidget(cb)
            hl.addStretch(1)
            self.table.setCellWidget(row, self.COL_MONITOR, holder)
            self.table.setItem(row, self.COL_ADDR, QtWidgets.QTableWidgetItem(f'0x{addr:X}'))
            for c in (self.COL_HEX, self.COL_DEC, self.COL_EXPECTED, self.COL_STATUS, self.COL_UPDATED):
                self.table.setItem(row, c, QtWidgets.QTableWidgetItem(''))

        # Bottom row
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        self.close_btn = QtWidgets.QPushButton('Close')
        self.close_btn.clicked.connect(self.close)
        bottom.addWidget(self.close_btn)
        layout.addLayout(bottom)

        # Poll timer
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    # ---- helpers -----------------------------------------------------
    def _row_checkbox(self, row: int) -> QtWidgets.QCheckBox | None:
        holder = self.table.cellWidget(row, self.COL_MONITOR)
        if holder is None:
            return None
        return holder.findChild(QtWidgets.QCheckBox)

    def _set_all_monitored(self, state: bool):
        for row in range(self.table.rowCount()):
            cb = self._row_checkbox(row)
            if cb is not None:
                cb.setChecked(state)

    def _apply_filter(self):
        only = self.only_monitored_cb.isChecked()
        for row in range(self.table.rowCount()):
            cb = self._row_checkbox(row)
            checked = bool(cb and cb.isChecked())
            self.table.setRowHidden(row, only and not checked)

    # ---- live update -------------------------------------------------
    def _refresh(self):
        latest = getattr(self._main, '_register_latest_values', None) or {}
        baseline = getattr(self._main, '_register_baseline', None) or {}
        recording = bool(getattr(self._main, '_register_recording', False)
                         and getattr(self._main, '_register_thread_running', False))
        if recording:
            n = len(latest)
            self.status_lbl.setText(f'Recording active - {n}/{len(self._addrs)} registers updating')
            self.status_lbl.setStyleSheet('color: #2e7d32;')
        else:
            self.status_lbl.setText('Idle - start register recording to see live values')
            self.status_lbl.setStyleSheet('color: #555;')

        bad = QtGui.QColor('#FFC7CE')
        good = QtGui.QColor('#FFFFFF')
        dim = QtGui.QColor('#F0F0F0')

        for row, addr in enumerate(self._addrs):
            cb = self._row_checkbox(row)
            monitored = bool(cb and cb.isChecked())
            entry = latest.get(addr)
            if entry is None:
                hex_s, dec_s, age_s = '', '', ''
                status = '' if not recording else 'waiting...'
                cur_val = None
            else:
                cur_val, ts_str, elapsed_s = entry
                hex_s, dec_s = _fmt_value(cur_val)
                try:
                    age_s = f'{float(elapsed_s):.2f}'
                except Exception:
                    age_s = ''
                status = 'OK'

            exp_val = baseline.get(addr)
            exp_hex, _ = _fmt_value(exp_val)

            if (isinstance(cur_val, int) and isinstance(exp_val, int)
                    and cur_val != exp_val):
                status = f'MISMATCH (Δ=0x{cur_val ^ exp_val:X})'
                row_color = bad
            elif not monitored:
                row_color = dim
            else:
                row_color = good

            self.table.item(row, self.COL_HEX).setText(hex_s)
            self.table.item(row, self.COL_DEC).setText(dec_s)
            self.table.item(row, self.COL_EXPECTED).setText(exp_hex)
            self.table.item(row, self.COL_STATUS).setText(status)
            self.table.item(row, self.COL_UPDATED).setText(age_s)

            for c in range(1, self.table.columnCount()):
                item = self.table.item(row, c)
                if item is not None:
                    item.setBackground(row_color)

    def closeEvent(self, ev):
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            if getattr(self._main, '_register_monitor_dialog', None) is self:
                self._main._register_monitor_dialog = None
        except Exception:
            pass
        super().closeEvent(ev)
