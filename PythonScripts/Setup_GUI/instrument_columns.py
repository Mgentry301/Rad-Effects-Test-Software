"""
Column-based instrument container.

Presents every instrument/supply panel side-by-side in its own column on a
single scrollable page, instead of one panel per tab. This lets the user see
and change voltages/currents/frequencies for all instruments at once without
switching tabs.

``InstrumentColumnsWidget`` is a drop-in replacement for the ``QTabWidget`` the
rest of the app expects: it exposes the same subset of the ``QTabWidget`` API
that the codebase uses -- ``count()``, ``widget(i)``, ``indexOf(w)``,
``tabText(i)``, ``setTabText(i, text)``, ``setTabsClosable(bool)``,
``addTab(widget, label)``, ``removeTab(i)`` -- plus the ``tabCloseRequested``
and ``currentChanged`` signals. Because the public surface matches, the other
mixins (config/power/recording/etc.) keep working without changes.
"""
from PyQt5 import QtWidgets, QtCore


class InstrumentColumnsWidget(QtWidgets.QScrollArea):
    """A horizontally scrolling row of instrument-panel columns.

    Mimics the small ``QTabWidget`` API used throughout the app so it can be
    substituted for ``self.tabs`` with no other code changes.
    """

    # Same signal names/signatures as QTabWidget so existing connections work.
    tabCloseRequested = QtCore.pyqtSignal(int)
    currentChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

        # Parallel lists kept in index order (index == "tab" index).
        self._panels = []       # instrument panel widgets
        self._labels = []       # str labels shown in each column header
        self._columns = []      # the column container frames
        self._title_labels = []  # QLabel in each header
        self._close_btns = []   # close (x) buttons in each header
        self._closable = False
        self._current = -1

        self._container = QtWidgets.QWidget()
        self._row = QtWidgets.QHBoxLayout(self._container)
        self._row.setContentsMargins(8, 8, 8, 8)
        self._row.setSpacing(12)
        self._row.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        # Trailing stretch so columns pack to the left and extra width is absorbed.
        self._row.addStretch(1)
        self.setWidget(self._container)

    # ------------------------------------------------------------------
    # QTabWidget-compatible API
    # ------------------------------------------------------------------
    def count(self):
        return len(self._panels)

    def widget(self, index):
        if 0 <= index < len(self._panels):
            return self._panels[index]
        return None

    def indexOf(self, widget):
        try:
            return self._panels.index(widget)
        except ValueError:
            return -1

    def tabText(self, index):
        if 0 <= index < len(self._labels):
            return self._labels[index]
        return ''

    def setTabText(self, index, text):
        if 0 <= index < len(self._labels):
            self._labels[index] = text
            self._title_labels[index].setText(text)

    def setTabsClosable(self, closable):
        self._closable = bool(closable)
        for btn in self._close_btns:
            btn.setVisible(self._closable)

    def currentIndex(self):
        return self._current

    def setCurrentIndex(self, index):
        if 0 <= index < len(self._panels) and index != self._current:
            self._current = index
            self._refresh_highlight()
            self.currentChanged.emit(index)

    def addTab(self, widget, label):
        index = len(self._panels)

        column = QtWidgets.QFrame()
        column.setObjectName('instrColumn')
        column.setProperty('active', False)
        col_layout = QtWidgets.QVBoxLayout(column)
        col_layout.setContentsMargins(8, 6, 8, 8)
        col_layout.setSpacing(6)

        # Header: instrument name + close button.
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        title = QtWidgets.QLabel(label)
        title.setObjectName('instrColumnTitle')
        title.setStyleSheet('font-weight: 600; font-size: 15px; color: #007aff;')
        close_btn = QtWidgets.QToolButton()
        close_btn.setText('\u2715')  # ✕
        close_btn.setToolTip('Remove this instrument')
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setAutoRaise(True)
        close_btn.setVisible(self._closable)
        # Resolve the current index at click time (indices shift on removal).
        close_btn.clicked.connect(
            lambda _=False, w=widget: self.tabCloseRequested.emit(self.indexOf(w))
        )
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(close_btn)
        col_layout.addLayout(header)

        col_layout.addWidget(widget)
        col_layout.addStretch(1)

        column.setStyleSheet('''
            QFrame#instrColumn {
                background: rgba(255,255,255,0.55);
                border: 1px solid rgba(0,0,0,0.12);
                border-radius: 14px;
            }
            QFrame#instrColumn[active="true"] {
                border: 1px solid #007aff;
                background: rgba(255,255,255,0.8);
            }
        ''')
        # Clicking anywhere in a column makes it the "current" one.
        column.installEventFilter(self)

        # Insert before the trailing stretch (which is the last layout item).
        self._row.insertWidget(self._row.count() - 1, column)

        self._panels.append(widget)
        self._labels.append(label)
        self._columns.append(column)
        self._title_labels.append(title)
        self._close_btns.append(close_btn)

        if self._current == -1:
            self._current = index
            self._refresh_highlight()
            self.currentChanged.emit(index)

        return index

    def removeTab(self, index):
        if not (0 <= index < len(self._panels)):
            return
        panel = self._panels.pop(index)
        self._labels.pop(index)
        column = self._columns.pop(index)
        self._title_labels.pop(index)
        self._close_btns.pop(index)

        # Detach the panel so it is not destroyed with the column (matches
        # QTabWidget.removeTab, which keeps the widget alive).
        try:
            panel.setParent(None)
        except Exception:
            pass
        self._row.removeWidget(column)
        column.deleteLater()

        # Recompute current index similar to QTabWidget behaviour.
        new_count = len(self._panels)
        if new_count == 0:
            self._current = -1
            self.currentChanged.emit(-1)
        else:
            if self._current > index:
                self._current -= 1
            elif self._current == index:
                self._current = min(index, new_count - 1)
            self._refresh_highlight()
            self.currentChanged.emit(self._current)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress and obj in self._columns:
            self.setCurrentIndex(self._columns.index(obj))
        return super().eventFilter(obj, event)

    def _refresh_highlight(self):
        for i, column in enumerate(self._columns):
            active = (i == self._current)
            if column.property('active') != active:
                column.setProperty('active', active)
                # Re-polish so the [active] stylesheet selector re-applies.
                column.style().unpolish(column)
                column.style().polish(column)
