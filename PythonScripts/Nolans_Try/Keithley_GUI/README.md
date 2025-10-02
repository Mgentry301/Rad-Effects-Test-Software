Keithley 2230 GUI

This folder contains a small PyQt GUI and a pyvisa wrapper to control a Keithley 2230-30-1 power supply.

Files
- keithley2230.py: minimal pyvisa wrapper for the supply
- keithley_gui.py: GUI application using PyQt5 + pyqtgraph
- requirements.txt: Python dependencies

Quick start
1. Create and activate a Python environment (3.8+ recommended).
2. Install dependencies:

   pip install -r requirements.txt

3. Run the GUI:

   python keithley_gui.py

Notes
- Update the VISA resource string in `keithley_gui.py` if your instrument enumerates differently. The default uses the serial number 9200976 you provided.
- Commands used are basic and may need small changes depending on your Keithley firmware. If a command fails, inspect the exception and consult the instrument manual.
