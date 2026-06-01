# Launch the Setup GUI without a console window by double-clicking this .pyw file
# It sets the working directory to the repo root, then runs setup_gui.py

import os
import sys
import runpy
import subprocess
from pathlib import Path


def _reexec_in_venv(repo_root: Path) -> bool:
    """Re-launch this script using the project's .venv interpreter.

    Double-clicking a .pyw uses whatever Python is associated with the file
    type (often the system/Microsoft Store Python). The Store Python is
    sandboxed and cannot load the Keysight VISA DLLs from Program Files, so
    instrument scanning fails there. Re-launch into the bundled .venv so the
    GUI always runs in the environment it was set up for.

    Returns True if a new process was launched (caller should exit), else False.
    """
    if os.environ.get('RADTEST_IN_VENV') == '1':
        return False
    venv_dir = repo_root / '.venv'
    venv_pyw = venv_dir / 'Scripts' / 'pythonw.exe'
    venv_py = venv_dir / 'Scripts' / 'python.exe'
    target = venv_pyw if venv_pyw.exists() else venv_py
    if not target.exists():
        return False  # no venv found; fall back to current interpreter
    try:
        # Already running from inside the .venv? Then don't re-launch.
        if venv_dir.resolve() in Path(sys.executable).resolve().parents:
            return False
    except Exception:
        pass
    env = dict(os.environ)
    env['RADTEST_IN_VENV'] = '1'
    this = str(Path(__file__).resolve())
    # os.execve is unreliable on Windows; use subprocess and let this process end.
    subprocess.Popen([str(target), this], env=env, cwd=str(repo_root))
    return True


def _find_repo_root(start: Path) -> Path:
    """Walk upward from this file to find the repo root (the dir with .venv).

    Falls back to the third parent if no .venv is found, matching the known
    layout .../<repo>/PythonScripts/Setup_GUI/launch_setup_gui.pyw.
    """
    for parent in start.parents:
        if (parent / '.venv').is_dir():
            return parent
    # Fallback: .../<repo>/PythonScripts/Setup_GUI/<file>
    return start.parents[2]


def main() -> None:
    this = Path(__file__).resolve()
    repo_root = _find_repo_root(this)
    os.chdir(str(repo_root))

    # Ensure we run inside the project's virtual environment.
    if _reexec_in_venv(repo_root):
        return  # handed off to the .venv interpreter

    gui_script = this.with_name("setup_gui.py")
    if not gui_script.exists():
        raise FileNotFoundError(f"GUI script not found: {gui_script}")

    # Execute as if run directly
    runpy.run_path(str(gui_script), run_name="__main__")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # Show a message box so errors aren't silent under pythonw
        try:
            import ctypes
            msg = (
                "Failed to launch Setup GUI:\n"
                f"{e.__class__.__name__}: {e}\n\n"
                "Run the script from a console for full traceback."
            )
            ctypes.windll.user32.MessageBoxW(0, msg, "Launch error", 0x10)
        except Exception:
            pass
        # Do not re-raise; nothing listens under pythonw
