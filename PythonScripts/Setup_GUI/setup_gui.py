"""
Multi-instrument GUI: Keithley 2230 panels + Keysight EL34243A panel.
- Add instruments by typing SN or full VISA resource.
- Choose instrument type on add (Keithley or Keysight).
- Scan VISA to detect connected devices.
- Each instrument gets its own tab and independent controls.

Notes:
- Keysight EL34243A wrapper uses common SCPI patterns for electronic loads
  (INP ON/OFF, FUNC:MODE <CURR|VOLT|RES>, CURR/VOLT/RES <value>, MEAS:CURR?).
  If your model uses different commands, the wrapper will report errors and
  can be adjusted easily.
"""
import sys
import os
import datetime

from PyQt5 import QtWidgets, QtCore

from Support_Scrips.power_sequence_builder import PowerSequenceBuilder

# Mixin modules  (each adds a logical group of methods to MainWindow)
from excel_manager import ExcelMixin
from recording_manager import RecordingMixin
from config_manager import ConfigMixin
from alias_manager import AliasMixin
from notes_manager import NotesMixin
from power_manager import PowerMixin
from programming_manager import ProgrammingMixin
from instrument_manager import InstrumentMixin


def _ensure_qt_plugin_path() -> None:
    try:
        import PyQt5
        plugin_path = os.path.join(os.path.dirname(PyQt5.__file__), 'Qt5', 'plugins')
        platform_path = os.path.join(plugin_path, 'platforms')
        if os.path.exists(plugin_path):
            os.environ['QT_PLUGIN_PATH'] = plugin_path
            QtCore.QCoreApplication.addLibraryPath(plugin_path)
        if os.path.exists(platform_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = platform_path
    except Exception:
        pass


class MainWindow(
    ExcelMixin,
    RecordingMixin,
    ConfigMixin,
    AliasMixin,
    NotesMixin,
    PowerMixin,
    ProgrammingMixin,
    InstrumentMixin,
    QtWidgets.QMainWindow,
):
    # Thread-safe log signal
    log_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # Apple liquid glass design stylesheet
        self.setStyleSheet('''
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e3eafc, stop:1 #cfd9df);
            }
            QWidget {
                background: rgba(255,255,255,0.7);
                border-radius: 16px;
                font-family: "Segoe UI", "San Francisco", Arial, sans-serif;
                font-size: 15px;
                color: #222;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: rgba(255,255,255,0.6);
                border-radius: 12px;
                padding: 8px 24px;
                margin: 4px;
                font-weight: 500;
                color: #222;
                min-width: 140px; /* ensure long labels like 'Programming' are fully visible */
                border: 1px solid rgba(0,0,0,0.15); /* subtle outline for rounded tab */
            }
            QTabBar::tab:selected {
                background: rgba(255,255,255,0.85);
                color: #007aff;
                border: 1px solid #b6c2ce; 
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fafdff, stop:1 #e3eafc);
                border-radius: 12px;
                border: 1px solid #d1d5db;
                padding: 8px 20px;
                font-size: 15px;
                color: #222;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #e3eafc;
                color: #007aff;
            }
            QPushButton:pressed {
                background: #cfd9df;
                color: #007aff;
            }
            QCheckBox {
                font-size: 15px;
                padding: 4px 12px;
                border-radius: 8px;
                background: rgba(255,255,255,0.5);
            }
            QLabel {
                font-size: 15px;
                color: #222;
                background: transparent;
            }
            QLineEdit {
                background: rgba(255,255,255,0.8);
                border-radius: 8px;
                border: 1px solid #d1d5db;
                padding: 6px 12px;
                font-size: 15px;
            }
            QPlainTextEdit {
                background: rgba(255,255,255,0.8);
                border-radius: 12px;
                border: 1px solid #d1d5db;
                font-size: 15px;
                padding: 8px;
            }
            QComboBox {
                background: rgba(255,255,255,0.8);
                border-radius: 8px;
                border: 1px solid #d1d5db;
                font-size: 15px;
                padding: 6px 12px;
            }
            QStatusBar {
                background: rgba(255,255,255,0.6);
                border-top: 1px solid #d1d5db;
                font-size: 14px;
                color: #222;
            }
    ''')
        # runtime control state for sequencing/program runs
        self._sequence_abort_flag = False
        self.program_process = None
        self._program_tempfile = None
        self._logic_thread = None
        self._logic_poll_timer = None
        self._logic_abort = False
        # aliasing for portable configs
        self.alias_dir = os.path.join(os.path.dirname(__file__), 'bench alias')
        os.makedirs(self.alias_dir, exist_ok=True)
        self.alias_profile = ''
        self.alias_map = {}
        # programming logic directory (external logic files for Configure Part)
        # Force-resolve to <repo>/PythonScripts/programming logics to avoid accidental Support_Scrips pathing
        try:
            # repo_root -> two levels up from Setup_GUI
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            python_scripts_dir = os.path.join(repo_root, 'PythonScripts')
            self.program_logic_dir = os.path.join(python_scripts_dir, 'programming logics')
            os.makedirs(self.program_logic_dir, exist_ok=True)
            # Fallbacks if expected structure is not present
            if not os.path.isdir(self.program_logic_dir):
                self.program_logic_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'programming logics')
                os.makedirs(self.program_logic_dir, exist_ok=True)
        except Exception:
            # Final fallback: current module directory
            self.program_logic_dir = os.path.dirname(__file__)
        self.setWindowTitle("Instrument Controller - Multiple Instruments")
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)

        # Top-level tabs: Setup and Test
        self.top_tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.top_tabs)

        # --- Setup Tab ---
        setup_widget = QtWidgets.QWidget()
        setup_layout = QtWidgets.QVBoxLayout(setup_widget)

        # Configs folder
        self.configs_dir = os.path.join(os.path.dirname(__file__), 'configs')
        os.makedirs(self.configs_dir, exist_ok=True)

        # Top: Instrument type selector, Scan VISA, detected devices, Save/Load Config
        top_row = QtWidgets.QHBoxLayout()
        self.scan_btn = QtWidgets.QPushButton('Scan VISA')
        self.scan_btn.clicked.connect(self.on_scan_instruments)
        self.detected_combo = QtWidgets.QComboBox()
        self.detected_combo.setMinimumWidth(350)
        self.add_selected_btn = QtWidgets.QPushButton('Add Selected')
        self.add_selected_btn.clicked.connect(self.on_add_selected_instrument)
        self.save_btn = QtWidgets.QPushButton('Save Config')
        self.save_btn.clicked.connect(self.save_config_dialog)
        self.load_combo = QtWidgets.QComboBox()
        self.load_combo.setMinimumWidth(200)
        self.load_btn = QtWidgets.QPushButton('Load Config')
        self.load_btn.clicked.connect(self.load_config_dialog)
        self.refresh_configs_list()

        top_row.addWidget(self.scan_btn)
        top_row.addWidget(self.detected_combo)
        top_row.addWidget(self.add_selected_btn)
        top_row.addWidget(self.save_btn)
        top_row.addWidget(self.load_combo)
        top_row.addWidget(self.load_btn)
        setup_layout.addLayout(top_row)

        # Tabs for instruments
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        # Auto-pause FieldFox streaming when tab not active
        try:
            self.tabs.currentChanged.connect(self._on_tab_changed)
        except Exception:
            pass
        setup_layout.addWidget(self.tabs)

    # Leave status blank until the initial VISA scan completes

        self.top_tabs.addTab(setup_widget, "Setup")

        # Connect logger signal to UI appender
        try:
            self.log_signal.connect(self._append_log)
        except Exception:
            pass

        # --- Sequencing Tab ---
        test_widget = QtWidgets.QWidget()
        test_layout = QtWidgets.QVBoxLayout(test_widget)

        # Power sequence builder (wrapper)
        self.power_seq_builder = PowerSequenceBuilder(
            parent=self,
            get_instruments_callback=lambda: [self.tabs.tabText(i) for i in range(self.tabs.count())]
        )
        test_layout.addWidget(self.power_seq_builder)

        # Abort / Cancel button and run log
        abort_row = QtWidgets.QHBoxLayout()
        self.abort_btn = QtWidgets.QPushButton('Abort')
        self.abort_btn.setStyleSheet('background-color: #FF5722; color: white;')
        self.abort_btn.clicked.connect(self.on_abort_clicked)
        abort_row.addWidget(self.abort_btn)
        test_layout.addLayout(abort_row)

        # Run log is presented on the Test tab (live updates via self._log)

        self.top_tabs.addTab(test_widget, "Sequencing")

        # Ensure sequence builder combo is populated with any existing tabs
        try:
            if hasattr(self, 'power_seq_builder'):
                self.power_seq_builder.refresh_instr_combo()
        except Exception:
            pass

        # --- Programming Tab ---
        prog_widget = QtWidgets.QWidget()
        prog_layout = QtWidgets.QVBoxLayout(prog_widget)

        # Configure Part row only (select logic file and run)
        cfg_row = QtWidgets.QHBoxLayout()
        self.logic_combo = QtWidgets.QComboBox()
        self.logic_combo.setMinimumWidth(420)
        self._refresh_logic_combo()
        cfg_row.addWidget(QtWidgets.QLabel('Logic file:'))
        cfg_row.addWidget(self.logic_combo, 1)
        self.logic_browse_btn = QtWidgets.QPushButton('Browse\u2026')
        self.logic_browse_btn.clicked.connect(self._browse_logic_file)
        cfg_row.addWidget(self.logic_browse_btn)
        self.configure_part_btn = QtWidgets.QPushButton('Configure Part')
        self.configure_part_btn.clicked.connect(self.on_configure_part_clicked)
        cfg_row.addWidget(self.configure_part_btn)
        prog_layout.addLayout(cfg_row)

        # Search for new programmings row
        search_row = QtWidgets.QHBoxLayout()
        self.logic_rescan_btn = QtWidgets.QPushButton('Search for New Programmings')
        def _on_rescan_logic():
            try:
                # Refresh list
                self._refresh_logic_combo()
                # Pick the most recently modified .py in the directory
                try:
                    files = [f for f in os.listdir(self.program_logic_dir) if f.lower().endswith('.py')]
                except Exception:
                    files = []
                newest_path = ''
                newest_mtime = -1
                for f in files:
                    full = os.path.join(self.program_logic_dir, f)
                    try:
                        mt = os.path.getmtime(full)
                        if mt > newest_mtime:
                            newest_mtime = mt
                            newest_path = full
                    except Exception:
                        pass
                if newest_path:
                    self._ensure_logic_in_combo(newest_path)
                    self.statusBar().showMessage(f'Selected newest logic: {os.path.basename(newest_path)}', 4000)
                else:
                    self.statusBar().showMessage('No logic files found', 3000)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'Rescan failed', str(e))
        self.logic_rescan_btn.clicked.connect(_on_rescan_logic)
        search_row.addWidget(self.logic_rescan_btn)
        prog_layout.addLayout(search_row)

        # Programming tab run log (live)
        prog_layout.addWidget(QtWidgets.QLabel('Run Log:'))
        self.program_log = QtWidgets.QPlainTextEdit()
        self.program_log.setReadOnly(True)
        self.program_log.setMaximumHeight(220)
        prog_layout.addWidget(self.program_log)

        self.top_tabs.addTab(prog_widget, 'Programming')

        # --- Test Tab ---
        test2_widget = QtWidgets.QWidget()
        test2_layout = QtWidgets.QVBoxLayout(test2_widget)

        # Power On/Off toggle (syncs with Sequencing tab power button)
        tpower_row = QtWidgets.QHBoxLayout()
        self.test_tab_power_btn = QtWidgets.QPushButton('Power Off All')
        self.test_tab_power_btn.setCheckable(True)
        self.test_tab_power_btn.setChecked(False)
        self.test_tab_power_btn.clicked.connect(self.on_test_power_toggle)
        if hasattr(self, '_update_test_power_toggle_btn'):
            self._update_test_power_toggle_btn(False)
        tpower_row.addWidget(self.test_tab_power_btn)
        test2_layout.addLayout(tpower_row)

        # --- Unified Record Controls ---
        record_row = QtWidgets.QHBoxLayout()
        # Prime button prepares threads and enables Start
        self.prime_btn = QtWidgets.QPushButton('Prime Recorders')
        self.prime_btn.setToolTip('Prepare selected recorders and Excel file; enables Start')
        self.prime_btn.clicked.connect(self.on_prime_clicked)
        record_row.addWidget(self.prime_btn)
        self.record_btn = QtWidgets.QPushButton('Record')
        self.record_btn.setCheckable(True)
        self.record_btn.setChecked(False)
        self.record_btn.clicked.connect(self.on_record_clicked)
        # Start disabled until primed
        self.record_btn.setEnabled(False)
        record_row.addWidget(self.record_btn)
        self.supply_record_toggle = QtWidgets.QCheckBox('Supply')
        self.supply_record_toggle.setChecked(True)
        record_row.addWidget(self.supply_record_toggle)
        self.spectrum_record_toggle = QtWidgets.QCheckBox('Spectrum')
        self.spectrum_record_toggle.setChecked(False)
        record_row.addWidget(self.spectrum_record_toggle)
        # Register recording toggle
        self.register_record_toggle = QtWidgets.QCheckBox('Register')
        self.register_record_toggle.setChecked(False)
        record_row.addWidget(self.register_record_toggle)
        # Live register monitor (works while register recording is active)
        self.register_monitor_btn = QtWidgets.QPushButton('Live Monitor')
        self.register_monitor_btn.setToolTip(
            'Open a window to live-monitor selected registers from register_read_array '
            '(values update while register recording is running)')
        self.register_monitor_btn.clicked.connect(self.open_register_monitor)
        record_row.addWidget(self.register_monitor_btn)
        # Threshold (in samples) for highlighting register changes that follow
        # a prolonged constant hold. Applied to the exported Excel on stop.
        record_row.addWidget(QtWidgets.QLabel('Change-after-hold ≥'))
        self.register_change_run_spin = QtWidgets.QSpinBox()
        self.register_change_run_spin.setRange(2, 1000000)
        self.register_change_run_spin.setValue(10)
        self.register_change_run_spin.setSuffix(' samples')
        self.register_change_run_spin.setToolTip(
            'On stop, highlight (yellow) any register cell where the value '
            'changed after holding the previous value for at least this many '
            'consecutive samples.')
        self.register_change_run_spin.valueChanged.connect(
            lambda v: setattr(self, 'register_change_min_run', int(v)))
        record_row.addWidget(self.register_change_run_spin)
        self.register_change_min_run = int(self.register_change_run_spin.value())
        self.supply_read_speed_label = QtWidgets.QLabel('Supply Sample Rate: --')
        self.spectrum_read_speed_label = QtWidgets.QLabel('Spectrum Sample Rate: --')
        self.register_read_speed_label = QtWidgets.QLabel('Register Sample Rate: --')
        record_row.addWidget(self.supply_read_speed_label)
        record_row.addWidget(self.spectrum_read_speed_label)
        record_row.addWidget(self.register_read_speed_label)
        # Add more toggles here for future metrics
        test2_layout.addLayout(record_row)
        # Priming state
        self._record_primed = False

        # Soft Reset button (runs Configure Part logic)
        prog_row = QtWidgets.QHBoxLayout()
        self.program_now_btn = QtWidgets.QPushButton('Program Device / Soft Reset')
        self.program_now_btn.clicked.connect(self.soft_reset)
        prog_row.addWidget(self.program_now_btn)
        test2_layout.addLayout(prog_row)

        # Reset controls
        reset_row = QtWidgets.QHBoxLayout()
        reset_row.addWidget(QtWidgets.QLabel('Reset delay (s):'))
        self.reset_delay_edit = QtWidgets.QLineEdit('2.0')
        self.reset_delay_edit.setMaximumWidth(80)
        reset_row.addWidget(self.reset_delay_edit)
        self.reset_btn = QtWidgets.QPushButton('Hard Reset')
        self.reset_btn.clicked.connect(self.reset_part)
        reset_row.addWidget(self.reset_btn)
        test2_layout.addLayout(reset_row)

        # Live run log for Configure Part
        test2_layout.addWidget(QtWidgets.QLabel('Run Log:'))
        self.test_log = QtWidgets.QPlainTextEdit()
        self.test_log.setReadOnly(True)
        self.test_log.setMaximumHeight(220)
        test2_layout.addWidget(self.test_log)

        self.top_tabs.addTab(test2_widget, 'Test')

        # --- Notes Tab (Setup notes for DUT wiring, sources, monitoring) ---
        self._init_notes_tab()

        # --- Settings Tab (Aliases) ---
        self._init_settings_tab()

        # Prompt for aliasing mode BEFORE any VISA scan; the prompt will trigger the first scan.
        try:
            QtCore.QTimer.singleShot(0, self._prompt_alias_startup)
        except Exception:
            pass

    # ---- Logging helpers (kept in main so log_signal pyqtSignal works) ----

    def _ts(self):
        return datetime.datetime.now().strftime('%H:%M:%S')

    def _log(self, msg: str):
        # Emit through Qt signal to ensure GUI-thread-safe appending
        try:
            self.log_signal.emit(f'[{self._ts()}] {msg}')
        except Exception:
            # Fallback to status bar if no signal yet
            self.statusBar().showMessage(msg, 4000)

    @QtCore.pyqtSlot(str)
    def _append_log(self, txt: str):
        # Append to both logs if present and keep them scrolled
        try:
            if hasattr(self, 'test_log') and self.test_log is not None:
                self.test_log.appendPlainText(txt)
                try:
                    self.test_log.verticalScrollBar().setValue(self.test_log.verticalScrollBar().maximum())
                except Exception:
                    pass
            if hasattr(self, 'program_log') and self.program_log is not None:
                self.program_log.appendPlainText(txt)
                try:
                    self.program_log.verticalScrollBar().setValue(self.program_log.verticalScrollBar().maximum())
                except Exception:
                    pass
        except Exception:
            try:
                self.statusBar().showMessage(txt, 4000)
            except Exception:
                pass

    def on_abort_clicked(self):
        self._sequence_abort_flag = True
        self._log('Abort requested')

    def closeEvent(self, event):
        # Ensure all background recordings are stopped and workbook is saved before exit
        try:
            self._stop_all_recordings()
        except Exception:
            pass
        # Power off all instruments on close. Set env var
        # POWER_OFF_ON_CLOSE=0 to suppress (leave bench in last
        # commanded state for CLI debug / another GUI session).
        import os as _os
        _auto_off = _os.environ.get('POWER_OFF_ON_CLOSE', '1').strip().lower() not in ('0', 'false', 'no', 'off')
        try:
            if _auto_off and hasattr(self, 'power_off_all'):
                self.power_off_all()
                try:
                    QtWidgets.QApplication.processEvents()
                except Exception:
                    pass
        except Exception:
            pass
        # close all panels to ensure instruments are closed
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            try:
                widget.close()
            except Exception:
                pass
        event.accept()


# Application entry point
if __name__ == '__main__':
    import sys
    from PyQt5 import QtWidgets
    try:
        _ensure_qt_plugin_path()
        app = QtWidgets.QApplication(sys.argv)
        win = MainWindow()
        win.show()
        sys.exit(app.exec_())
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'Fatal startup error: {e}', file=sys.stderr)
        sys.exit(1)
