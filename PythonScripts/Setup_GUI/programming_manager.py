"""
Programming / Configure-Part mixin for MainWindow.

Provides logic-file selection, browsing, auto-selection, and the
run_configure_part background-thread execution.
"""
import os

from PyQt5 import QtWidgets, QtCore


class ProgrammingMixin:
    """Mixin that adds programming-logic management to MainWindow."""

    def _refresh_logic_combo(self):
        try:
            if not hasattr(self, 'logic_combo'):
                return
            try:
                prev_path = self.logic_combo.currentData()
                prev_path = prev_path if isinstance(prev_path, str) else ''
            except Exception:
                prev_path = ''
            self.logic_combo.clear()
            self.logic_combo.addItem('(Select a logic file)', '')
            try:
                files = [f for f in os.listdir(self.program_logic_dir) if f.lower().endswith('.py')]
            except Exception:
                files = []
            for f in sorted(files):
                full = os.path.join(self.program_logic_dir, f)
                self.logic_combo.addItem(f, full)
            if prev_path and os.path.exists(prev_path):
                found_idx = -1
                for i in range(self.logic_combo.count()):
                    if self.logic_combo.itemData(i) == prev_path:
                        found_idx = i
                        break
                if found_idx == -1:
                    self.logic_combo.addItem(os.path.basename(prev_path), prev_path)
                    found_idx = self.logic_combo.count() - 1
                if found_idx != -1:
                    self.logic_combo.setCurrentIndex(found_idx)
        except Exception:
            pass

    def _ensure_logic_in_combo(self, path: str):
        if not path:
            return
        try:
            for i in range(self.logic_combo.count()):
                if self.logic_combo.itemData(i) == path:
                    self.logic_combo.setCurrentIndex(i)
                    return
            self.logic_combo.addItem(os.path.basename(path), path)
            self.logic_combo.setCurrentIndex(self.logic_combo.count() - 1)
        except Exception:
            pass

    def _browse_logic_file(self):
        start_dir = self.program_logic_dir if os.path.isdir(self.program_logic_dir) else os.path.expanduser('~')
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select logic file', start_dir, 'Python Files (*.py)')
        if not fname:
            return
        try:
            target = os.path.join(self.program_logic_dir, os.path.basename(fname))
            if os.path.abspath(os.path.dirname(fname)) != os.path.abspath(self.program_logic_dir):
                resp = QtWidgets.QMessageBox.question(
                    self, 'Copy logic file?',
                    f'Copy selected file into:\n{self.program_logic_dir}\nfor easier reuse?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes)
                if resp == QtWidgets.QMessageBox.Yes:
                    try:
                        import shutil
                        os.makedirs(self.program_logic_dir, exist_ok=True)
                        shutil.copy2(fname, target)
                        fname = target
                    except Exception as e:
                        QtWidgets.QMessageBox.warning(self, 'Copy failed', str(e))
            self._ensure_logic_in_combo(fname)
        except Exception:
            pass

    def _get_selected_logic_path(self) -> str:
        try:
            data = self.logic_combo.currentData()
            return data if isinstance(data, str) else ''
        except Exception:
            return ''

    def _auto_select_logic_for_config(self, config_path: str, instruments: list, content: dict) -> str:
        """Heuristically pick a programming logic .py based on the config."""
        try:
            logic_dir = getattr(self, 'program_logic_dir', os.path.dirname(__file__))
            try:
                files = [f for f in os.listdir(logic_dir) if f.lower().endswith('.py')]
            except Exception:
                files = []
            if not files:
                return ''

            def _norm(s: str) -> str:
                return ''.join(ch for ch in str(s).lower() if ch.isalnum())

            cfg_base = os.path.splitext(os.path.basename(config_path or ''))[0]
            cfg_tok = _norm(cfg_base)
            if cfg_base:
                base_lower = cfg_base.lower()
                for f in files:
                    if os.path.splitext(f)[0].lower() == base_lower:
                        return os.path.join(logic_dir, f)
            tokens = set()
            if cfg_tok:
                tokens.add(cfg_tok)
            try:
                for ent in instruments or []:
                    nm = ent.get('name') if isinstance(ent, dict) else None
                    tp = ent.get('type') if isinstance(ent, dict) else None
                    if nm:
                        t = _norm(nm)
                        if t:
                            tokens.add(t)
                    if tp:
                        t = _norm(tp)
                        if t:
                            tokens.add(t)
            except Exception:
                pass
            try:
                for k in ('part', 'device', 'dut', 'design'):
                    v = content.get(k)
                    if v:
                        t = _norm(v)
                        if t:
                            tokens.add(t)
            except Exception:
                pass

            candidates = []
            for f in files:
                full = os.path.join(logic_dir, f)
                base = os.path.splitext(f)[0]
                bn = _norm(base)
                try:
                    mt = os.path.getmtime(full)
                except Exception:
                    mt = 0
                score = 0
                if bn and cfg_tok and bn == cfg_tok:
                    score = 3
                elif any(bn == t for t in tokens):
                    score = 3
                elif any((bn in t) or (t in bn) for t in tokens):
                    score = 2
                candidates.append((score, mt, full))

            candidates.sort(key=lambda x: (x[0], x[1]))
            best = candidates[-1] if candidates else None
            if best and best[0] > 0:
                return best[2]
            if len(files) == 1:
                return os.path.join(logic_dir, files[0])
            return ''
        except Exception:
            return ''

    def on_configure_part_clicked(self):
        logic_path = self._get_selected_logic_path()
        if not logic_path:
            QtWidgets.QMessageBox.information(self, 'No logic selected', 'Please select a logic .py file to run.')
            return
        if not os.path.exists(logic_path):
            QtWidgets.QMessageBox.warning(self, 'Missing file', f'Logic file not found:\n{logic_path}')
            return
        self.run_configure_part(logic_path)

    def run_configure_part(self, logic_path: str):
        """Run logic directly in a background thread."""
        if self._logic_thread is not None and self._logic_thread.is_alive():
            self._log('Configure Part is already running')
            return

        self._logic_abort = False
        self._log(f'Starting Configure Part with logic: {os.path.basename(logic_path)}')

        def post_log(msg: str):
            try:
                QtCore.QTimer.singleShot(0, lambda m=msg: self._log(m))
            except Exception:
                pass

        def worker():
            import sys as _sys
            import importlib.util as _importlib_util
            import threading as _th
            import time as _time
            import logging as _logging

            class _StreamForwarder:
                def __init__(self, cb):
                    self._cb = cb
                    self._buf = ''
                    self._lock = _th.Lock()
                def write(self, s):
                    if not s:
                        return
                    with self._lock:
                        self._buf += str(s)
                        while '\n' in self._buf:
                            line, self._buf = self._buf.split('\n', 1)
                            if line.strip():
                                try:
                                    self._cb(line)
                                except Exception:
                                    pass
                def flush(self):
                    with self._lock:
                        if self._buf.strip():
                            try:
                                self._cb(self._buf)
                            except Exception:
                                pass
                        self._buf = ''

            try:
                # Pre-load the logic module so we can check for a SKIP_ACE
                # flag. Backends that talk to their own hardware (e.g. a
                # Linduino over serial) set SKIP_ACE = True so we don't
                # require the ACE COM server to be running.
                _spec_pre = _importlib_util.spec_from_file_location(
                    'selected_logic_pre', logic_path)
                _mod_pre = _importlib_util.module_from_spec(_spec_pre)
                assert _spec_pre and _spec_pre.loader
                _spec_pre.loader.exec_module(_mod_pre)  # type: ignore
                _skip_ace = bool(getattr(_mod_pre, 'SKIP_ACE', False))

                if _skip_ace:
                    post_log('Logic declares SKIP_ACE; bypassing ACE client.')
                    client = None
                else:
                    ace_path = r'C:\\Program Files\\Analog Devices\\ACE\\Client'
                    if ace_path not in _sys.path:
                        _sys.path.append(ace_path)
                    import clr  # type: ignore
                    clr.AddReference('AnalogDevices.Csa.Remoting.Clients')
                    clr.AddReference('AnalogDevices.Csa.Remoting.Contracts')
                    from AnalogDevices.Csa.Remoting.Clients import ClientManager  # type: ignore
                    manager = ClientManager.Create()
                    client = manager.CreateRequestClient('localhost:2357')

                _old_out, _old_err = _sys.stdout, _sys.stderr
                _fw = _StreamForwarder(post_log)
                _sys.stdout = _fw
                _sys.stderr = _fw

                _log_handler = _logging.StreamHandler(_fw)
                _log_handler.setLevel(_logging.DEBUG)
                _log_handler.setFormatter(_logging.Formatter('%(message)s'))
                _root_logger = _logging.getLogger()
                _root_logger.addHandler(_log_handler)

                _stop_evt = _th.Event()
                def _periodic_flush():
                    while not _stop_evt.is_set():
                        try:
                            _fw.flush()
                        except Exception:
                            pass
                        _time.sleep(0.5)
                _flush_thread = _th.Thread(target=_periodic_flush, daemon=True)
                _flush_thread.start()

                try:
                    if _skip_ace:
                        self._log('Running logic without ACE client...')
                    else:
                        self._log('ACE connection established; running logic...')
                except Exception:
                    try:
                        if hasattr(self, 'test_log'):
                            self.test_log.appendPlainText('ACE connection established; running logic...')
                        if hasattr(self, 'program_log'):
                            self.program_log.appendPlainText('ACE connection established; running logic...')
                    except Exception:
                        pass

                spec = _importlib_util.spec_from_file_location('selected_logic', logic_path)
                mod = _importlib_util.module_from_spec(spec)
                assert spec and spec.loader
                spec.loader.exec_module(mod)  # type: ignore
                func = None
                if hasattr(mod, 'execute_macro'):
                    func = getattr(mod, 'execute_macro')
                elif hasattr(mod, 'logic'):
                    func = getattr(mod, 'logic')
                if func is None:
                    self._log('Selected logic file must define execute_macro(client) or logic(client)')
                    try:
                        _fw.flush()
                    except Exception:
                        pass
                    _sys.stdout, _sys.stderr = _old_out, _old_err
                    return
                try:
                    func(client)
                finally:
                    self._log('Configure Part finished')
                    try:
                        _fw.flush()
                    except Exception:
                        pass
                    try:
                        _stop_evt.set()
                        _flush_thread.join(timeout=1.0)
                    except Exception:
                        pass
                    try:
                        _root_logger.removeHandler(_log_handler)
                    except Exception:
                        pass
                    _sys.stdout, _sys.stderr = _old_out, _old_err
            except Exception as e:
                post_log(f'Configure Part error: {e}')

        import threading as _threading
        self._logic_thread = _threading.Thread(target=worker, daemon=True)
        self._logic_thread.start()

        try:
            if hasattr(self, 'abort_program_btn'):
                self.abort_program_btn.setEnabled(True)
            if hasattr(self, 'run_program_btn'):
                self.run_program_btn.setEnabled(False)
            if hasattr(self, 'program_now_btn'):
                self.program_now_btn.setEnabled(False)
            if hasattr(self, 'configure_part_btn'):
                self.configure_part_btn.setEnabled(False)
        except Exception:
            pass

        try:
            if self._logic_poll_timer is None:
                self._logic_poll_timer = QtCore.QTimer(self)
                self._logic_poll_timer.setInterval(300)
                self._logic_poll_timer.timeout.connect(self._on_logic_thread_check)
            if not self._logic_poll_timer.isActive():
                self._logic_poll_timer.start()
        except Exception:
            pass

    def _on_logic_thread_check(self):
        try:
            alive = self._logic_thread is not None and self._logic_thread.is_alive()
        except Exception:
            alive = False
        if not alive:
            try:
                if self._logic_poll_timer and self._logic_poll_timer.isActive():
                    self._logic_poll_timer.stop()
            except Exception:
                pass
            self._logic_thread = None
            try:
                if hasattr(self, 'run_program_btn'):
                    self.run_program_btn.setEnabled(True)
                if hasattr(self, 'abort_program_btn'):
                    self.abort_program_btn.setEnabled(False)
                if hasattr(self, 'program_now_btn'):
                    self.program_now_btn.setEnabled(True)
                if hasattr(self, 'configure_part_btn'):
                    self.configure_part_btn.setEnabled(True)
            except Exception:
                pass

    def soft_reset(self):
        """Soft Reset: run the same Configure Part logic as the Programming page."""
        logic_path = self._get_selected_logic_path()
        if not logic_path:
            QtWidgets.QMessageBox.information(self, 'No logic selected', 'Please select a logic .py file on the Programming tab.')
            return
        if not os.path.exists(logic_path):
            QtWidgets.QMessageBox.warning(self, 'Missing file', f'Logic file not found:\n{logic_path}')
            return
        self.run_configure_part(logic_path)
