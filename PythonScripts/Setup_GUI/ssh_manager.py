"""
Raspberry Pi SSH mixin for MainWindow.

Provides SSH connect/disconnect to a Raspberry Pi, listing of programming
scripts in a remote directory, and running a chosen script with its output
streamed live into the Programming tab's Run Log.

Connection settings (host / user / port / remote script dir) are persisted to
``ssh_settings.json`` next to this module. The password is never saved.
"""
import os
import re
import json
import shlex
import datetime
import threading

from PyQt5 import QtCore, QtWidgets

try:
    import paramiko
except Exception:  # pragma: no cover - surfaced to the user at connect time
    paramiko = None


def _remote_quote(path: str) -> str:
    """Quote a remote path for the shell while preserving a leading ``~``.

    ``shlex.quote`` wraps the whole string in single quotes, which stops the
    remote shell from expanding ``~`` to the home directory. Keep the leading
    ``~/`` unquoted so it expands, and quote only the remainder.
    """
    if path == '~':
        return '~'
    if path.startswith('~/'):
        return '~/' + shlex.quote(path[2:])
    return shlex.quote(path)


class SshMixin:
    """Mixin that adds Raspberry Pi SSH control to MainWindow."""

    # ---- settings persistence -------------------------------------------
    def _ssh_settings_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), 'ssh_settings.json')

    def _load_ssh_settings(self) -> dict:
        defaults = {
            'host': 'fe80::394c:9eb6:eb65:350f%6',
            'user': 'pi',
            'port': 22,
            'script_dir': '~/pi_scripts',
            'use_sudo': False,
            'timeout': 10,
        }
        try:
            with open(self._ssh_settings_path(), 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                defaults.update({k: data[k] for k in defaults if k in data})
        except Exception:
            pass
        return defaults

    def _save_ssh_settings(self):
        try:
            payload = {
                'host': self.ssh_host_edit.text().strip(),
                'user': self.ssh_user_edit.text().strip(),
                'port': self._ssh_get_port(),
                'script_dir': self.ssh_scriptdir_edit.text().strip(),
                'use_sudo': bool(self.ssh_sudo_checkbox.isChecked()),
                'timeout': self._ssh_get_timeout(),
            }
            with open(self._ssh_settings_path(), 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    # ---- helpers --------------------------------------------------------
    def _ssh_get_port(self) -> int:
        try:
            return int(self.ssh_port_edit.text().strip() or '22')
        except Exception:
            return 22

    def _ssh_get_timeout(self) -> int:
        """Overall connection timeout in seconds (clamped to a sane range)."""
        try:
            edit = getattr(self, 'ssh_timeout_edit', None)
            val = int(edit.text().strip()) if edit is not None else 10
        except Exception:
            val = 10
        return max(2, min(val, 120))

    def _ssh_is_connected(self) -> bool:
        client = getattr(self, '_ssh_client', None)
        if client is None:
            return False
        try:
            transport = client.get_transport()
            return bool(transport and transport.is_active())
        except Exception:
            return False

    # ---- connect / disconnect ------------------------------------------
    def on_ssh_connect_clicked(self):
        if self._ssh_is_connected():
            self._ssh_disconnect()
            return
        if paramiko is None:
            QtWidgets.QMessageBox.critical(
                self, 'paramiko missing',
                'The paramiko package is not installed.\n\n'
                'Install it with:\n    pip install paramiko')
            return

        host = self.ssh_host_edit.text().strip()
        user = self.ssh_user_edit.text().strip()
        password = self.ssh_pass_edit.text()
        port = self._ssh_get_port()
        if not host or not user:
            QtWidgets.QMessageBox.information(
                self, 'Missing details', 'Please enter a host and username.')
            return

        timeout = self._ssh_get_timeout()
        self._save_ssh_settings()
        self.ssh_connect_btn.setEnabled(False)
        self._ssh_set_status('Connecting\u2026', 'orange')
        self._log(f'SSH: connecting to {user}@{host}:{port} (timeout {timeout}s) \u2026')

        self._ssh_connecting = True
        self._ssh_last_timeout = timeout
        self._ssh_connect_token = getattr(self, '_ssh_connect_token', 0) + 1
        token = self._ssh_connect_token
        self._ssh_pending_client = None

        def worker():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._ssh_pending_client = client
            try:
                # Bound every phase (TCP connect, banner, auth) by the timeout
                # so a stalled handshake cannot hang indefinitely.
                client.connect(
                    hostname=host,
                    port=port,
                    username=user,
                    password=password,
                    look_for_keys=False,
                    allow_agent=False,
                    timeout=timeout,
                    banner_timeout=timeout,
                    auth_timeout=timeout,
                )
            except Exception as e:
                self.ssh_connect_result.emit(token, None, e)
                return
            self.ssh_connect_result.emit(token, client, None)

        threading.Thread(target=worker, daemon=True).start()

        # Watchdog: if the attempt hasn't resolved shortly after the timeout,
        # forcibly abort it and reset the UI (covers cases paramiko misses).
        QtCore.QTimer.singleShot(
            int((timeout + 2) * 1000),
            lambda t=token: self._ssh_connect_watchdog(t))

    def _ssh_finish_connect(self, token, client, err):
        # Ignore results from a superseded or already-resolved attempt.
        if token != getattr(self, '_ssh_connect_token', 0) or not getattr(self, '_ssh_connecting', False):
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            return
        self._ssh_connecting = False
        self._ssh_pending_client = None
        self.ssh_connect_btn.setEnabled(True)
        if err is not None or client is None:
            self._ssh_client = None
            self._log(f'SSH: connection failed: {err}')
            self._ssh_set_status('Not connected', 'red')
            self._ssh_update_ui_state()
            QtWidgets.QMessageBox.critical(self, 'SSH connection failed', str(err))
            return
        self._ssh_client = client
        self._log('SSH: connected.')
        self._ssh_set_status('Connected', 'green')
        self._ssh_update_ui_state()
        self._refresh_pi_scripts()

    def _ssh_connect_watchdog(self, token):
        if token != getattr(self, '_ssh_connect_token', 0) or not getattr(self, '_ssh_connecting', False):
            return
        self._ssh_connecting = False
        timeout = getattr(self, '_ssh_last_timeout', 10)
        # Force-close the in-progress client to unblock the worker thread.
        pending = getattr(self, '_ssh_pending_client', None)
        self._ssh_pending_client = None
        if pending is not None:
            try:
                pending.close()
            except Exception:
                pass
        self._ssh_client = None
        self._log(f'SSH: connection attempt timed out after {timeout}s.')
        self._ssh_set_status('Not connected', 'red')
        self.ssh_connect_btn.setEnabled(True)
        self._ssh_update_ui_state()
        msg = ('Could not connect within %d seconds.\n\n'
               'Check that the Pi is powered on and reachable on this '
               'network interface, then try again.') % timeout
        QtWidgets.QMessageBox.warning(self, 'SSH connection timed out', msg)

    def _ssh_disconnect(self):
        client = getattr(self, '_ssh_client', None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        self._ssh_client = None
        self._log('SSH: disconnected.')
        self._ssh_set_status('Not connected', 'red')
        self._ssh_update_ui_state()

    # ---- remote script listing -----------------------------------------
    def _refresh_pi_scripts(self):
        if not self._ssh_is_connected():
            return
        script_dir = self.ssh_scriptdir_edit.text().strip()
        if not script_dir:
            return
        self._save_ssh_settings()
        # find files (not dirs) one level deep; %f prints the bare filename.
        cmd = (
            f"find {_remote_quote(script_dir)} -maxdepth 1 -type f "
            f"-printf '%f\\n' 2>/dev/null | sort"
        )

        def worker():
            files = []
            err_txt = ''
            try:
                _in, out, err = self._ssh_client.exec_command(cmd, timeout=15)
                files = [ln.strip() for ln in out.read().decode(errors='replace').splitlines() if ln.strip()]
                err_txt = err.read().decode(errors='replace').strip()
            except Exception as e:
                err_txt = str(e)
            self.ssh_scripts_result.emit(files, script_dir, err_txt)

        threading.Thread(target=worker, daemon=True).start()

    def _ssh_populate_scripts(self, files, script_dir, err_txt):
        try:
            self.pi_script_combo.clear()
            self.pi_script_combo.addItem('(Select a script)', '')
            for f in files:
                remote_path = script_dir.rstrip('/') + '/' + f
                self.pi_script_combo.addItem(f, remote_path)
            # Preserve the config-bound command entry across refreshes.
            spec = getattr(self, '_pi_config_spec', None)
            if isinstance(spec, dict) and spec.get('cmd'):
                label = spec.get('label') or spec.get('cmd')
                self.pi_script_combo.insertItem(1, f'[config] {label}', '__config__')
                self.pi_script_combo.setCurrentIndex(1)
            if files:
                self._log(f'SSH: found {len(files)} script(s) in {script_dir}.')
            else:
                msg = f'SSH: no scripts found in {script_dir}.'
                if err_txt:
                    msg += f' ({err_txt})'
                self._log(msg)
        except Exception:
            pass

    def _get_selected_pi_script(self) -> str:
        try:
            data = self.pi_script_combo.currentData()
            return data if isinstance(data, str) else ''
        except Exception:
            return ''

    # ---- config-bound Pi command ---------------------------------------
    def _apply_config_pi_script(self, spec):
        """Bind a loaded config's ``pi_script`` block to the SSH controls.

        ``spec`` is the dict stored in the config JSON, e.g.::

            {
              "label": "AD9082 NCO test",
              "dir":   "~/AD9082_API-Rel1.7.0/src/ad9082_app/platform/raspi",
              "build": "make all",
              "cmd":   "./build/nco_test",
              "args":  "0 100000000",
              "sudo":  true
            }

        Passing a falsy ``spec`` clears any previously bound command.
        """
        # Remove any prior config-bound entry
        try:
            for i in range(self.pi_script_combo.count()):
                if self.pi_script_combo.itemData(i) == '__config__':
                    self.pi_script_combo.removeItem(i)
                    break
        except Exception:
            pass

        if not isinstance(spec, dict) or not spec.get('cmd'):
            self._pi_config_spec = None
            return

        self._pi_config_spec = spec
        label = spec.get('label') or spec.get('cmd')
        try:
            self.pi_script_combo.insertItem(1, f'[config] {label}', '__config__')
            self.pi_script_combo.setCurrentIndex(1)
        except Exception:
            pass
        try:
            if spec.get('dir'):
                self.ssh_scriptdir_edit.setText(str(spec.get('dir')))
            self.ssh_args_edit.setText(str(spec.get('args', '')))
            self.ssh_sudo_checkbox.setChecked(bool(spec.get('sudo', False)))
        except Exception:
            pass
        self._log(f'Pi command bound from config: {label}')

    # ---- run-log helpers ------------------------------------------------
    def _pi_logs_dir(self) -> str:
        d = os.path.join(os.path.dirname(__file__), 'pi_run_logs')
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return d

    def _pi_next_run_id(self) -> str:
        """Suggest the next integer run id based on existing log files."""
        mx = 0
        try:
            for f in os.listdir(self._pi_logs_dir()):
                m = re.match(r'AD9082 Run (\d+) reg log', f)
                if m:
                    mx = max(mx, int(m.group(1)))
        except Exception:
            pass
        return str(mx + 1)

    def _sudo_wrap(self, inner: str, use_sudo: bool):
        """Return (exec_cmd, display_cmd) for optionally running under sudo.

        If sudo is requested and the SSH password is available, feed it to
        ``sudo -S`` over stdin so passworded sudo works without an interactive
        prompt. The display form hides the password so it never reaches the
        Run Log or the saved log file.
        """
        if not use_sudo:
            return inner, inner
        try:
            pw = self.ssh_pass_edit.text()
        except Exception:
            pw = ''
        if pw:
            exec_cmd = f"echo {shlex.quote(pw)} | sudo -S -p '' {inner}"
            return exec_cmd, f'sudo {inner}'
        # No password entered: fall back to passwordless (-n) sudo.
        return f'sudo -n {inner}', f'sudo -n {inner}'

    # ---- run remote script ---------------------------------------------
    def on_pi_run_script_clicked(self):
        if not self._ssh_is_connected():
            QtWidgets.QMessageBox.information(
                self, 'Not connected', 'Connect to the Raspberry Pi first.')
            return
        if getattr(self, '_ssh_run_channel', None) is not None:
            self._log('SSH: a script is already running.')
            return

        selection = self._get_selected_pi_script()
        args = self.ssh_args_edit.text().strip()
        use_sudo = bool(self.ssh_sudo_checkbox.isChecked())
        reg_work_dir = ''
        reg_log_name = ''

        if selection == '__config__' and isinstance(getattr(self, '_pi_config_spec', None), dict):
            spec = self._pi_config_spec
            work_dir = str(spec.get('dir') or '.').strip()
            build = str(spec.get('build') or '').strip()
            base_cmd = str(spec.get('cmd') or '').strip()
            label = spec.get('label') or os.path.basename(base_cmd)
            reg_work_dir = work_dir
            reg_log_name = str(spec.get('reg_log') or '').strip()
            inner = base_cmd + (f' {args}' if args else '')
            inner_exec, inner_disp = self._sudo_wrap(inner, use_sudo)
            prefix = [f'cd {_remote_quote(work_dir)}']
            if build:
                prefix.append(build)
            cmd = ' && '.join(prefix + [inner_exec])
            log_cmd = ' && '.join(prefix + [inner_disp])
        elif selection:
            remote_path = selection
            remote_dir = os.path.dirname(remote_path)
            label = os.path.basename(remote_path)
            ext = os.path.splitext(label)[1].lower()
            # Guard against running obvious non-program files (e.g. source code).
            _not_runnable = {'.c', '.h', '.cpp', '.hpp', '.cc', '.cxx', '.o',
                             '.a', '.so', '.mak', '.mk', '.md', '.txt', '.json'}
            if ext in _not_runnable or label.lower() in ('makefile', 'readme'):
                resp = QtWidgets.QMessageBox.question(
                    self, 'Run this file?',
                    f'"{label}" does not look like a runnable program.\n\n'
                    'Did you mean the compiled binary (e.g. build/nco_test) or '
                    'the "[config] AD9082 NCO test" entry?\n\nRun it anyway?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No)
                if resp != QtWidgets.QMessageBox.Yes:
                    return
            if ext == '.py':
                runner = 'python3 -u'
            elif ext == '.sh':
                runner = 'bash'
            else:
                runner = ''  # assume the file is directly executable
            inner = f'{runner} {_remote_quote(remote_path)}'.strip()
            if args:
                inner += f' {args}'
            inner_exec, inner_disp = self._sudo_wrap(inner, use_sudo)
            cmd = f'cd {_remote_quote(remote_dir)} && {inner_exec}'
            log_cmd = f'cd {_remote_quote(remote_dir)} && {inner_disp}'
        else:
            QtWidgets.QMessageBox.information(
                self, 'No script selected', 'Please choose a script to run.')
            return

        self._save_ssh_settings()

        # Ask for a run identifier so each run is saved to its own log file.
        log_path = None
        x, ok = QtWidgets.QInputDialog.getText(
            self, 'Save run log',
            'Enter run identifier X for  "AD9082 Run X reg log"\n'
            '(leave blank for a timestamp, Cancel to skip saving):',
            QtWidgets.QLineEdit.Normal, self._pi_next_run_id())
        if ok:
            x = (x or '').strip() or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            safe = ''.join(c for c in x if c not in '\\/:*?"<>|').strip() or 'run'
            fname = f'AD9082 Run {safe} reg log.txt'
            log_path = os.path.join(self._pi_logs_dir(), fname)

        reg_fetch = None
        if log_path and reg_log_name:
            reg_local = os.path.join(
                self._pi_logs_dir(), f'AD9082 Run {safe} reg log - registers.txt')
            reg_fetch = (reg_work_dir, reg_log_name, reg_local, use_sudo)

        self._ssh_run_command(cmd, label, log_path, log_cmd, reg_fetch)

    def _ssh_fetch_reg_log(self, work_dir, name, local_path, use_sudo):
        """Copy the device's register read/write log from the Pi to the PC.

        The AD9082 app writes a detailed SPI register log (e.g. nco_test.log)
        in its working directory. This retrieves that file so each run keeps
        the register-level detail alongside the API-level run log. When the
        run used sudo the log is root-owned, so the copy is read via sudo too.
        """
        try:
            # Only the cat runs under sudo; cd is a shell builtin and must stay
            # outside sudo (otherwise sudo tries to exec "cd" and fails).
            cat_inner, _ = self._sudo_wrap(f'cat -- {_remote_quote(name)}', use_sudo)
            exec_cmd = f'cd {_remote_quote(work_dir)} && {cat_inner}'
            channel = self._ssh_client.get_transport().open_session()
            try:
                channel.exec_command(exec_cmd)
                data = channel.makefile('rb').read()
                status = channel.recv_exit_status()
            finally:
                channel.close()
            if status != 0:
                self._log(f'SSH: could not read {name} on the Pi (exit {status}).')
                return
            with open(local_path, 'w', encoding='utf-8', newline='') as f:
                f.write(f'# {name} (register read/write log)\n')
                f.write(f'# fetched {datetime.datetime.now().isoformat(timespec="seconds")}\n')
                f.write(f'# source: {work_dir}/{name}\n\n')
                f.write(data.decode(errors='replace'))
            self._log(f'SSH: register log saved: {local_path}')
        except Exception as e:
            self._log(f'SSH: register log fetch error: {e}')

    def _ssh_run_command(self, cmd: str, label: str, log_path: str = None, log_cmd: str = None, reg_fetch=None):
        """Execute ``cmd`` on the Pi, streaming output into the Run Log.

        If ``log_path`` is given, every output line is also written to that
        file so each run keeps its own register-dump log. ``log_cmd`` is a
        password-free version of ``cmd`` used for display/logging. ``reg_fetch``
        is an optional ``(work_dir, name, local_path, use_sudo)`` tuple naming
        a device register log to copy back from the Pi after the run.
        """
        self._log(f'SSH: running {label} \u2026')
        if log_path:
            self._log(f'SSH: saving run log to {log_path}')
        self._ssh_set_run_active(True)

        def worker():
            channel = None
            logf = None
            try:
                if log_path:
                    try:
                        logf = open(log_path, 'w', encoding='utf-8')
                        logf.write(f'# {label}\n')
                        logf.write(f'# {datetime.datetime.now().isoformat(timespec="seconds")}\n')
                        logf.write(f'# command: {log_cmd or cmd}\n\n')
                        logf.flush()
                    except Exception as e:
                        self._log(f'SSH: could not open log file: {e}')
                        logf = None

                def _emit(text):
                    self._log(text)
                    if logf:
                        try:
                            logf.write(text + '\n')
                            logf.flush()
                        except Exception:
                            pass

                transport = self._ssh_client.get_transport()
                channel = transport.open_session()
                self._ssh_run_channel = channel
                channel.get_pty()
                channel.exec_command(cmd)
                buf = b''
                while True:
                    if channel.recv_ready():
                        data = channel.recv(4096)
                        buf += data
                        while b'\n' in buf:
                            line, buf = buf.split(b'\n', 1)
                            _emit(line.decode(errors='replace').rstrip('\r'))
                    if channel.exit_status_ready() and not channel.recv_ready():
                        break
                try:
                    while channel.recv_ready():
                        buf += channel.recv(4096)
                except Exception:
                    pass
                if buf.strip():
                    _emit(buf.decode(errors='replace').rstrip('\r\n'))
                status = channel.recv_exit_status()
                self._log(f'SSH: {label} finished (exit status {status}).')
                if logf:
                    try:
                        logf.write(f'\n# exit status {status}\n')
                        logf.flush()
                    except Exception:
                        pass
                    self._log(f'SSH: run log saved: {log_path}')
                if reg_fetch:
                    self._ssh_fetch_reg_log(*reg_fetch)
            except Exception as e:
                self._log(f'SSH: run error: {e}')
            finally:
                try:
                    if logf:
                        logf.close()
                except Exception:
                    pass
                self._ssh_run_channel = None
                self.ssh_run_active_sig.emit(False)

        self._ssh_run_thread = threading.Thread(target=worker, daemon=True)
        self._ssh_run_thread.start()

    def on_pi_abort_script_clicked(self):
        channel = getattr(self, '_ssh_run_channel', None)
        if channel is None:
            return
        try:
            # send Ctrl-C to the pty, then close the channel
            channel.send('\x03')
        except Exception:
            pass
        try:
            channel.close()
        except Exception:
            pass
        self._log('SSH: abort requested.')

    # ---- UI state -------------------------------------------------------
    def _ssh_set_status(self, text: str, color: str):
        try:
            self.ssh_status_label.setText(f'Status: {text}')
            self.ssh_status_label.setStyleSheet(f'color: {color}; font-weight: 600;')
        except Exception:
            pass

    def _ssh_update_ui_state(self):
        connected = self._ssh_is_connected()
        try:
            self.ssh_connect_btn.setText('Disconnect' if connected else 'Connect')
            self.pi_script_refresh_btn.setEnabled(connected)
            self.pi_run_btn.setEnabled(connected)
            self.pi_script_combo.setEnabled(connected)
            for w in (self.ssh_host_edit, self.ssh_user_edit,
                      self.ssh_pass_edit, self.ssh_port_edit):
                w.setEnabled(not connected)
        except Exception:
            pass

    def _ssh_set_run_active(self, active: bool):
        try:
            self.pi_run_btn.setEnabled(not active and self._ssh_is_connected())
            self.pi_abort_btn.setEnabled(active)
            self.ssh_connect_btn.setEnabled(not active)
        except Exception:
            pass
