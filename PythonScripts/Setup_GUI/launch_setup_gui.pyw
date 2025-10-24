# Launch the Setup GUI without a console window by double-clicking this .pyw file
# It sets the working directory to the repo root, then runs setup_gui.py

import os
import runpy
from pathlib import Path


def main() -> None:
    this = Path(__file__).resolve()
    # Repo root: .../PythonScripts/Setup_GUI/ -> parents[3] = repo root
    # [0]=file, [1]=Setup_GUI, [2]=PythonScripts, [3]=repo
    repo_root = this.parents[3]
    os.chdir(str(repo_root))

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
