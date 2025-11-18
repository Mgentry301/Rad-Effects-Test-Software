"""Cleaned Excel plotter GUI (fixed copy, v2).

This file is a corrected copy with export DPI fixed to 32768 and the
Export DPI selection UI removed. Run this file directly to launch the GUI.
"""

import os
from io import BytesIO
from typing import Optional, List

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import json
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor
from PyQt5.QtPrintSupport import QPrinter


class ExcelPlotter(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Excel Plotter (fixed)')
        self.resize(1100, 720)

        # state
        self.excel: Optional[pd.ExcelFile] = None
        self.current_path: Optional[str] = None
        self.current_df: Optional[pd.DataFrame] = None
        self.capture_mode = False
        self.freq_axis: Optional[List[float]] = None
        self._ts_series: List[str] = []
        # default export DPI (fixed): use very high DPI for raster fallback
        self.export_dpi = 32768
        # track hex-converted columns for 'flag changing registers' feature
        self._hex_converted_cols: List[str] = []

        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        tabs = QtWidgets.QTabWidget()
        v.addWidget(tabs)

        # Graphing tab
        graph_tab = QtWidgets.QWidget()
        g_layout = QtWidgets.QVBoxLayout(graph_tab)

        # Top control row
        top = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(top)
        self.open_btn = QtWidgets.QPushButton('Open Excel')
        self.open_btn.clicked.connect(self.on_open_file)
        hl.addWidget(self.open_btn)
        # show currently opened file name
        self.file_label = QtWidgets.QLabel('No file')
        self.file_label.setStyleSheet('font-weight:600; margin-left:8px;')
        hl.addWidget(self.file_label)
        self.sheet_combo = QtWidgets.QComboBox()
        self.sheet_combo.currentTextChanged.connect(self.on_sheet_changed)
        hl.addWidget(self.sheet_combo)
        hl.addWidget(QtWidgets.QLabel('Plot type:'))
        self.plot_type_combo = QtWidgets.QComboBox()
        self.plot_type_combo.addItems(['Line', 'Scatter', 'FFT'])
        self.plot_type_combo.currentTextChanged.connect(self.on_plot_type_changed)
        hl.addWidget(self.plot_type_combo)
        hl.addStretch()
        hl.addWidget(QtWidgets.QLabel('X:'))
        self.x_combo = QtWidgets.QComboBox()
        hl.addWidget(self.x_combo)
        hl.addWidget(QtWidgets.QLabel('Y:'))
        # Two Y selectors: a combo for FFT timestamp selection, and a multi-select list for Line/Scatter
        self.y_combo = QtWidgets.QComboBox()
        self.y_list = QtWidgets.QListWidget()
        self.y_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.y_list.setMaximumHeight(120)
        self.y_selector_stack = QtWidgets.QStackedWidget()
        self.y_selector_stack.addWidget(self.y_combo)   # index 0: combo (used for FFT timestamps)
        self.y_selector_stack.addWidget(self.y_list)    # index 1: multi-list (used for Line/Scatter)
        hl.addWidget(self.y_selector_stack)
        hl.addWidget(QtWidgets.QLabel('X label:'))
        self.x_label_edit = QtWidgets.QLineEdit()
        hl.addWidget(self.x_label_edit)
        hl.addWidget(QtWidgets.QLabel('Y label:'))
        self.y_label_edit = QtWidgets.QLineEdit()
        hl.addWidget(self.y_label_edit)
        hl.addWidget(QtWidgets.QLabel('Line width:'))
        self.line_width_spin = QtWidgets.QDoubleSpinBox()
        self.line_width_spin.setRange(0.1, 20.0)
        self.line_width_spin.setSingleStep(0.1)
        self.line_width_spin.setValue(1.0)
        hl.addWidget(self.line_width_spin)
        # Legend toggle and Names editor
        self.legend_chk = QtWidgets.QCheckBox('Legend')
        self.legend_chk.setChecked(False)
        hl.addWidget(self.legend_chk)
        self.select_changing_btn = QtWidgets.QPushButton('Select Changing Registers')
        self.select_changing_btn.setEnabled(False)
        self.select_changing_btn.setToolTip('Select register columns (*_dec) that change values during the run')
        self.select_changing_btn.clicked.connect(self.on_select_changing_registers)
        hl.addWidget(self.select_changing_btn)
        self.names_btn = QtWidgets.QPushButton('Names...')
        self.names_btn.setToolTip('Edit series/timestamp display names for the legend')
        self.names_btn.clicked.connect(self.open_names_dialog)
        hl.addWidget(self.names_btn)
        self.colors_btn = QtWidgets.QPushButton('Colors...')
        self.colors_btn.setToolTip('Edit per-series curve colors')
        self.colors_btn.clicked.connect(self.open_colors_dialog)
        hl.addWidget(self.colors_btn)
        # Font size controls: legend, axis titles, tick labels
        hl.addWidget(QtWidgets.QLabel('Legend size:'))
        self.legend_font_spin = QtWidgets.QSpinBox()
        self.legend_font_spin.setRange(6, 48)
        self.legend_font_spin.setValue(10)
        hl.addWidget(self.legend_font_spin)

        hl.addWidget(QtWidgets.QLabel('Title size:'))
        self.title_font_spin = QtWidgets.QSpinBox()
        self.title_font_spin.setRange(6, 72)
        self.title_font_spin.setValue(12)
        hl.addWidget(self.title_font_spin)

        hl.addWidget(QtWidgets.QLabel('Tick size:'))
        self.tick_font_spin = QtWidgets.QSpinBox()
        self.tick_font_spin.setRange(6, 48)
        self.tick_font_spin.setValue(10)
        hl.addWidget(self.tick_font_spin)
        btn_plot = QtWidgets.QPushButton('Plot')
        btn_plot.clicked.connect(self.on_plot)
        hl.addWidget(btn_plot)
        g_layout.addWidget(top)

        # Figure and canvas
        self.fig = Figure(figsize=(8, 5))
        self.canvas = FigureCanvas(self.fig)
        g_layout.addWidget(NavigationToolbar(self.canvas, self))
        g_layout.addWidget(self.canvas, 1)

        # FFT statistics area (hidden unless FFT plot is shown)
        self.fft_stats_label = QtWidgets.QLabel('')
        self.fft_stats_label.setWordWrap(True)
        self.fft_stats_label.setStyleSheet('background:#fff;border:1px solid #ddd;padding:6px;font-family:monospace;')
        self.fft_stats_label.setVisible(False)
        g_layout.addWidget(self.fft_stats_label)

        # Save / layout / lines row
        sb = QtWidgets.QWidget()
        sbh = QtWidgets.QHBoxLayout(sb)
        sbh.addStretch()
        self.save_btn = QtWidgets.QPushButton('Save plot')
        self.save_btn.clicked.connect(self.on_save_plot)
        sbh.addWidget(self.save_btn)
        # Lines dialog button (placed beside Save; the small listing box was removed per request)
        self.lines_btn = QtWidgets.QPushButton('📏 Lines')
        self.lines_btn.setToolTip('Manage reference lines (horizontal / vertical)')
        self.lines_btn.clicked.connect(self.open_lines_dialog)
        sbh.addWidget(self.lines_btn)
        # Save / Load format buttons (save current plot 'template' and apply to other data)
        self.save_fmt_btn = QtWidgets.QPushButton('Save Format')
        self.save_fmt_btn.setToolTip('Save current plot format (columns, labels, lines, axis limits)')
        self.save_fmt_btn.clicked.connect(self.save_graph_format)
        sbh.addWidget(self.save_fmt_btn)
        self.load_fmt_btn = QtWidgets.QPushButton('Load Format')
        self.load_fmt_btn.setToolTip('Load a saved plot format and apply to current data')
        self.load_fmt_btn.clicked.connect(self.load_graph_format)
        sbh.addWidget(self.load_fmt_btn)
        # hidden internal list for bookkeeping (do not show as a large box in the UI)
        self.lines_list = QtWidgets.QListWidget()
        self.lines_list.setMaximumWidth(220)
        self.lines_list.setVisible(False)
        g_layout.addWidget(sb)

        # storage for reference lines
        self.h_lines = []
        self.v_lines = []
        # optional mapping of series name -> display label for legends
        self.series_labels = {}
        # optional mapping of series name -> color string (e.g. '#rrggbb')
        self.series_colors = {}
        # legend state: keep reference and preferred location
        self._legend = None
        self._legend_loc = 'best'
        self._legend_pick_cid = None
        self._legend_button_cid = None
        self._legend_release_cid = None
        # desired axis limits preserved/loaded from formats
        self.desired_xlim = None
        self.desired_ylim = None

        tabs.addTab(graph_tab, 'Graphing')

        self.setStatusBar(QtWidgets.QStatusBar(self))

    def set_status(self,text,timeout=0):
        self.statusBar().showMessage(text,timeout)

    def on_open_file(self):
        path,_ = QtWidgets.QFileDialog.getOpenFileName(self,'Open Excel file','','Excel Files (*.xlsx *.xls)')
        if not path: return
        try:
            self.excel = pd.ExcelFile(path, engine='openpyxl')
            self.current_path = path
            self.sheet_combo.clear(); self.sheet_combo.addItems(self.excel.sheet_names)
            # show filename prominently in the UI
            try:
                self.file_label.setText(os.path.basename(path))
            except Exception:
                pass
            self.set_status(f'Opened: {os.path.basename(path)}',3000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,'Open failed',str(e))

    def on_sheet_changed(self,sheet:str):
        if not sheet or self.excel is None: return
        try:
            df = self.excel.parse(sheet_name=sheet)
            self.current_df = df
            freq_candidates = self._infer_freq_axis_from_headers(df)
            after_headers = list(df.columns.astype(str))[1:]
            if ('capture' in sheet.lower()) or (freq_candidates and len(freq_candidates)>=max(3,len(after_headers)//4)):
                self.freq_axis = freq_candidates; self.capture_mode=True
                try: self._ts_series = list(df.iloc[:,0].astype(str))
                except Exception: self._ts_series=[]
            else:
                self.capture_mode=False; self.freq_axis=None; self._ts_series=[]
            # we'll populate the X/Y selectors after performing runtime column additions
            # (e.g., Noise_Floor_Median for capture data and automatic hex->decimal conversions)

            # If this looks like capture data, compute and attach a per-row noise-floor median
            if self.capture_mode:
                try:
                    median_vals = self._compute_noise_floor_median_per_row(df)
                    df['Noise_Floor_Median'] = median_vals
                    # ensure the GUI list includes the new column so it's immediately graphable
                    # we'll add this when populating the selector lists below
                except Exception:
                    # don't block loading if noise computation fails
                    pass

            # Auto-convert columns that look like hexadecimal register reads into decimal columns.
            # Heuristic: if at least ~60% of non-empty entries in a column match hex pattern (optionally
            # prefixed with 0x) and there are at least 3 non-empty entries, create a new column named
            # '<col>_dec' containing the converted integers (or NA on parse failure).
            try:
                hex_converted = []
                for col in list(df.columns):
                    try:
                        ser = df[col].astype(str).fillna('').str.strip()
                        non_empty = ser[ser != '']
                        if len(non_empty) < 3:
                            continue
                        matches = non_empty.str.match(r'^(?:0x)?[0-9A-Fa-f]+$')
                        if float(matches.sum()) / float(len(non_empty)) >= 0.6:
                            # perform conversion for the full column
                            def _to_dec(v):
                                try:
                                    s = str(v).strip()
                                    if s == '' or s.lower() in ('nan', 'none'):
                                        return pd.NA
                                    if s.lower().startswith('0x'):
                                        s2 = s[2:]
                                    else:
                                        s2 = s
                                    return int(s2, 16)
                                except Exception:
                                    return pd.NA

                            df[f"{col}_dec"] = df[col].apply(_to_dec)
                            hex_converted.append(col)
                    except Exception:
                        continue
                if hex_converted:
                    try:
                        self.set_status(f"Converted hex columns to *_dec: {', '.join(hex_converted)}", 4000)
                    except Exception:
                        pass
                # store converted column names and enable the select changing registers button
                self._hex_converted_cols = [f"{c}_dec" for c in hex_converted]
                try:
                    self.select_changing_btn.setEnabled(len(self._hex_converted_cols) > 0)
                except Exception:
                    pass
            except Exception:
                pass

            # now populate the X/Y selectors with the (possibly expanded) column list
            cols = list(df.columns.astype(str))
            self.x_combo.clear(); self.x_combo.addItems(cols)
            # populate the multi-select list with available columns
            self.y_list.clear(); self.y_list.addItems(cols)

            # choose the appropriate Y selector based on plot type
            if self.capture_mode and self.plot_type_combo.currentText().lower()=='fft' and self._ts_series:
                # switch to combo for timestamp selection
                self.y_combo.clear(); self.y_combo.addItems(self._ts_series); self.y_selector_stack.setCurrentIndex(0)
                self.x_combo.setEnabled(False)
            else:
                # use multi-select list for y columns
                self.y_selector_stack.setCurrentIndex(1)
                self.x_combo.setEnabled(True)
            self.set_status(f'Loaded sheet: {sheet}',2000)
        except Exception as e:
            self.current_df=None; self.x_combo.clear(); self.y_combo.clear(); QtWidgets.QMessageBox.warning(self,'Read failed',str(e))

    def on_plot_type_changed(self,text:str):
        if text.lower()=='fft' and self.capture_mode and self._ts_series:
            # show combo for timestamps
            self.y_combo.clear(); self.y_combo.addItems(self._ts_series); self.y_selector_stack.setCurrentIndex(0); self.x_combo.setEnabled(False)
        else:
            if self.current_df is not None:
                cols=list(self.current_df.columns.astype(str)); self.y_list.clear(); self.y_list.addItems(cols)
            self.y_selector_stack.setCurrentIndex(1)
            self.x_combo.setEnabled(True)

    def on_select_changing_registers(self):
        """Select only the hex-converted register columns that have changing values within a time range."""
        if self.current_df is None or not self._hex_converted_cols:
            return
        
        try:
            # Determine the time/index column (use current X column selection as default)
            x_col = self.x_combo.currentText()
            if not x_col or x_col not in self.current_df.columns:
                # fallback to first column if X is not selected
                x_col = self.current_df.columns[0] if len(self.current_df.columns) > 0 else None
            
            if x_col is None:
                QtWidgets.QMessageBox.warning(self, 'No time column', 'Cannot determine time/index column for filtering')
                return
            
            # Get the time range from the selected column
            try:
                time_series = pd.to_numeric(self.current_df[x_col], errors='coerce')
                if time_series.isna().all():
                    # try datetime parsing
                    time_series = pd.to_datetime(self.current_df[x_col], errors='coerce')
                    if time_series.notna().any():
                        # convert to elapsed seconds from first timestamp
                        first = time_series.dropna().iloc[0]
                        time_series = (time_series - first).dt.total_seconds()
                
                valid_times = time_series.dropna()
                if len(valid_times) == 0:
                    QtWidgets.QMessageBox.warning(self, 'No valid times', f'Column {x_col} has no valid numeric/datetime values')
                    return
                
                time_min = float(valid_times.min())
                time_max = float(valid_times.max())
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'Time parsing failed', f'Could not parse time column {x_col}: {e}')
                return
            
            # Show dialog to get time range from user
            dlg = TimeRangeDialog(self, time_min, time_max, x_col)
            if dlg.exec_() != QtWidgets.QDialog.Accepted:
                return
            
            start_time, end_time = dlg.get_range()
            
            # Filter DataFrame to the selected time range
            mask = (time_series >= start_time) & (time_series <= end_time)
            df_filtered = self.current_df[mask]
            
            if len(df_filtered) == 0:
                QtWidgets.QMessageBox.warning(self, 'Empty range', 'No data points in the selected time range')
                return
            
            # Determine which *_dec columns have changing values in the filtered range
            changing_cols = []
            for col in self._hex_converted_cols:
                if col not in df_filtered.columns:
                    continue
                try:
                    # drop NA and get unique values in the filtered range
                    unique_vals = df_filtered[col].dropna().unique()
                    if len(unique_vals) > 1:
                        changing_cols.append(col)
                except Exception:
                    continue
            
            # Select (highlight) these columns in the Y-list
            for i in range(self.y_list.count()):
                item = self.y_list.item(i)
                item.setSelected(item.text() in changing_cols)
            
            # Show status
            if changing_cols:
                self.set_status(f"Selected {len(changing_cols)} changing register(s) in range [{start_time:.3g}, {end_time:.3g}]: {', '.join(changing_cols)}", 5000)
            else:
                self.set_status(f"No changing registers found in range [{start_time:.3g}, {end_time:.3g}] (all have constant values)", 3000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Select changing failed', str(e))

    def _infer_freq_axis_from_headers(self,df:pd.DataFrame) -> Optional[List[float]]:
        headers = list(df.columns.astype(str))[1:]
        freqs=[]
        for h in headers:
            hstr=str(h).strip()
            try:
                freqs.append(float(hstr)); continue
            except Exception:
                pass
            hs=''.join(ch for ch in hstr if (ch.isdigit() or ch in '.eE+-'))
            try:
                if hs: freqs.append(float(hs))
            except Exception:
                continue
        return freqs if freqs else None

    def _compute_noise_rms_per_row(self, df: pd.DataFrame):
        """Compute noise RMS for each row of capture-style DataFrame.

        Assumes first column is timestamp and remaining columns are FFT amplitude samples.
        Returns a list of floats (noise RMS), one per row. If computation fails for a row, np.nan is used.
        """
        out = []
        try:
            data = df.iloc[:, 1:]
        except Exception:
            return [np.nan] * len(df)

        for i in range(len(data)):
            try:
                row = pd.to_numeric(data.iloc[i, :], errors='coerce').dropna().astype(float).values
                if row.size <= 1:
                    out.append(np.nan)
                    continue
                # exclude the max-abs peak
                peak_idx = int(np.nanargmax(np.abs(row)))
                vals = np.delete(row, peak_idx)
                # RMS of residuals
                rms = float(np.sqrt(np.mean(np.square(vals))))
                out.append(rms)
            except Exception:
                out.append(np.nan)
        return out

    def _compute_noise_floor_median_per_row(self, df: pd.DataFrame):
        """Compute per-row noise floor median (preserve sign) excluding the dominant peak.

        Returns a list of medians, one per row. Uses columns after the first as FFT bins.
        """
        out = []
        try:
            data = df.iloc[:, 1:]
        except Exception:
            return [np.nan] * len(df)

        for i in range(len(data)):
            try:
                row = pd.to_numeric(data.iloc[i, :], errors='coerce').dropna().astype(float).values
                if row.size <= 1:
                    out.append(np.nan)
                    continue
                peak_idx = int(np.nanargmax(np.abs(row)))
                vals = np.delete(row, peak_idx)
                med = float(np.median(vals))
                out.append(med)
            except Exception:
                out.append(np.nan)
        return out

    def on_plot(self):
        if self.current_df is None:
            QtWidgets.QMessageBox.warning(self,'No data','Open a file and select a sheet first'); return
        plot_type=self.plot_type_combo.currentText().lower(); df=self.current_df
        if plot_type=='fft':
            if not self.capture_mode or not self.freq_axis:
                QtWidgets.QMessageBox.warning(self,'FFT not available','Could not detect frequency axis in this sheet'); return
            sel_ts=self.y_combo.currentText();
            if not sel_ts: QtWidgets.QMessageBox.warning(self,'No timestamp','Select a timestamp to plot its FFT'); return
            ts_col=df.iloc[:,0].astype(str); matches=ts_col[ts_col==sel_ts]
            if matches.empty:
                idxs = ts_col[ts_col.str.contains(sel_ts, na=False)]
            if matches.empty and (idxs.empty): QtWidgets.QMessageBox.warning(self,'Timestamp not found','Selected timestamp row not found'); return
            row_idx = matches.index[0] if not matches.empty else idxs.index[0]
            amp = pd.to_numeric(df.iloc[row_idx,1:], errors='coerce')
            freqs=self.freq_axis; n=min(len(freqs),len(amp)); x=pd.Series(freqs[:n]); y=amp.iloc[:n]
            self.fig.clear(); ax=self.fig.add_subplot(111)
            # font sizes from UI
            legend_font = int(self.legend_font_spin.value()) if hasattr(self, 'legend_font_spin') else 10
            title_font = int(self.title_font_spin.value()) if hasattr(self, 'title_font_spin') else 12
            tick_font = int(self.tick_font_spin.value()) if hasattr(self, 'tick_font_spin') else 10
            lw = float(self.line_width_spin.value()) if hasattr(self, 'line_width_spin') else 1.0
            # label the FFT series with the timestamp or a user-provided display name so it can appear in the legend
            fft_label = (self.series_labels.get(sel_ts) or sel_ts) if hasattr(self, 'series_labels') else sel_ts
            ax.plot(x, y, marker='o', linestyle='-', color='#1f77b4', markersize=4, linewidth=lw, label=fft_label)
            # apply per-series color override if provided
            try:
                fft_color = self.series_colors.get(sel_ts)
                if fft_color:
                    for line in ax.get_lines()[-1:]:
                        try:
                            line.set_color(fft_color)
                        except Exception:
                            pass
            except Exception:
                pass
            ax.set_xlabel(self.x_label_edit.text() or 'Frequency', fontsize=title_font)
            ax.set_ylabel(self.y_label_edit.text() or 'Amplitude', fontsize=title_font)
            ax.grid(True)
            try:
                ax.tick_params(axis='both', labelsize=int(tick_font))
            except Exception:
                pass
            try:
                xmin = float(min(x)); xmax_f = float(max(x))
            except Exception:
                xmin = None
            if xmin is not None and xmax_f > xmin:
                ax.set_xlim(xmin, xmax_f)

            # Compute FFT statistics to display below the plot
            try:
                yv = pd.to_numeric(y.dropna(), errors='coerce').astype(float).values
                if yv.size > 3:
                    # peak frequency and level
                    peak_idx = int(np.nanargmax(yv))
                    peak_freq = float(x.iloc[peak_idx])
                    peak_level = float(yv[peak_idx])

                    # noise floor estimate: median of residuals excluding the peak (preserve sign)
                    vals = np.copy(yv)
                    vals = np.delete(vals, peak_idx)
                    noise_floor = float(np.median(vals))
                    # noise magnitude for SNR: RMS of residuals (always positive)
                    noise_rms = float(np.sqrt(np.mean(np.square(vals))))

                    # SNR in dB using peak amplitude vs noise RMS
                    snr_db = 20.0 * np.log10((abs(peak_level) / (noise_rms + 1e-12)))

                    stats_text = (
                        f'Peak freq: {peak_freq:.6g}   Peak level: {peak_level:.6g}\n'
                        f'Noise floor (median): {noise_floor:.6g}   Noise RMS: {noise_rms:.6g}\n'
                        f'SNR: {snr_db:.1f} dB'
                    )
                else:
                    stats_text = 'FFT: insufficient points for stats'
            except Exception as e:
                stats_text = f'FFT stats error: {e}'

            self.fft_stats_label.setText(stats_text)
            self.fft_stats_label.setVisible(True)
            # draw reference lines (if any) so they appear on FFT plots too
            try:
                for h in getattr(self, 'h_lines', []):
                    if isinstance(h, dict):
                        lab = h.get('label') if h.get('label') else None
                        ax.axhline(h.get('value'), color=h.get('color', '#d62728'), linestyle=h.get('linestyle', '--'), linewidth=h.get('linewidth', 1), label=lab)
                    else:
                        ax.axhline(h, color='#d62728', linestyle='--', linewidth=1)
                for v in getattr(self, 'v_lines', []):
                    if isinstance(v, dict):
                        lab = v.get('label') if v.get('label') else None
                        ax.axvline(v.get('value'), color=v.get('color', '#2ca02c'), linestyle=v.get('linestyle', '--'), linewidth=v.get('linewidth', 1), label=lab)
                    else:
                        ax.axvline(v, color='#2ca02c', linestyle='--', linewidth=1)
            except Exception:
                pass
            # apply saved axis limits if present
            try:
                if getattr(self, 'desired_xlim', None) is not None:
                    ax.set_xlim(tuple(self.desired_xlim))
                if getattr(self, 'desired_ylim', None) is not None:
                    ax.set_ylim(tuple(self.desired_ylim))
            except Exception:
                pass
            # draw reference lines (if any) so they appear on FFT plots too
            self._h_line_artists = []
            self._v_line_artists = []
            try:
                for ih, h in enumerate(getattr(self, 'h_lines', [])):
                    if isinstance(h, dict):
                        lab = h.get('label') if h.get('label') else None
                        art = ax.axhline(h.get('value'), color=h.get('color', '#d62728'), linestyle=h.get('linestyle', '--'), linewidth=h.get('linewidth', 1), label=lab)
                        self._h_line_artists.append(art)
                    else:
                        art = ax.axhline(h, color='#d62728', linestyle='--', linewidth=1)
                        self._h_line_artists.append(art)
                for iv, v in enumerate(getattr(self, 'v_lines', [])):
                    if isinstance(v, dict):
                        lab = v.get('label') if v.get('label') else None
                        art = ax.axvline(v.get('value'), color=v.get('color', '#2ca02c'), linestyle=v.get('linestyle', '--'), linewidth=v.get('linewidth', 1), label=lab)
                        self._v_line_artists.append(art)
                    else:
                        art = ax.axvline(v, color='#2ca02c', linestyle='--', linewidth=1)
                        self._v_line_artists.append(art)
            except Exception:
                pass

            # show legend if user requested it; build legend from current handles/labels so reference lines are included
            try:
                if getattr(self, 'legend_chk', None) and self.legend_chk.isChecked():
                    try:
                        handles, labels = ax.get_legend_handles_labels()
                        if getattr(self, '_legend_loc', 'best') == 'outside_right':
                            leg = ax.legend(handles, labels, loc='center left', bbox_to_anchor=(1.02, 0.5), borderaxespad=0., prop={'size': int(legend_font)})
                        else:
                            leg = ax.legend(handles, labels, loc=getattr(self, '_legend_loc', 'best'), prop={'size': int(legend_font)})
                    except Exception:
                        leg = ax.legend(loc=getattr(self, '_legend_loc', 'best'))
                    try:
                        self._connect_legend_handlers(leg)
                    except Exception:
                        pass
            except Exception:
                pass
            self.canvas.draw()
            self.set_status(f'Plotted FFT @ {sel_ts}', 3000)
            return
        # (reference lines are drawn after each axis is created so they're visible on the plot)
        # For non-FFT plotting allow multiple Y columns via y_list
        x_col = self.x_combo.currentText()
        # get selected Y columns from list
        y_items = [it.text() for it in self.y_list.selectedItems()]
        if not y_items:
            # fallback to first selected in combo/list if none explicitly selected
            if self.y_selector_stack.currentIndex() == 0:
                # combo shown (unlikely here), use combo single value
                y_items = [self.y_combo.currentText()]
            else:
                # use all items in the list if none selected
                y_items = [self.y_list.item(i).text() for i in range(self.y_list.count())]

        if not x_col or not y_items:
            QtWidgets.QMessageBox.warning(self,'No columns','Select X and at least one Y column to plot'); return

        # If user requested the Noise_Floor_Median column but it's not present or not numeric,
        # compute it on-demand so it becomes graphable.
        for ycol in list(y_items):
            if ycol == 'Noise_Floor_Median':
                need_compute = False
                if 'Noise_Floor_Median' not in df.columns:
                    need_compute = True
                else:
                    # check numeric
                    try:
                        if not pd.api.types.is_numeric_dtype(df['Noise_Floor_Median']):
                            need_compute = True
                    except Exception:
                        need_compute = True
                if need_compute:
                    try:
                        median_vals = self._compute_noise_floor_median_per_row(df)
                        df['Noise_Floor_Median'] = median_vals
                        # ensure the multi-select list shows the new column
                        if self.y_selector_stack.currentIndex() == 1:
                            # add item if not already present
                            existing = [self.y_list.item(i).text() for i in range(self.y_list.count())]
                            if 'Noise_Floor_Median' not in existing:
                                self.y_list.addItem('Noise_Floor_Median')
                    except Exception:
                        # if it fails, warn and continue (plot will likely skip)
                        QtWidgets.QMessageBox.warning(self,'Noise compute failed','Failed to compute Noise_Floor_Median')
        try:
            x_series = pd.to_numeric(df[x_col], errors='coerce')
        except Exception:
            x_series = pd.Series([pd.NA] * len(df))
        x=x_series
        try:
            non_na=x.dropna(); need_dt=(len(non_na)==0) or (non_na.size/max(1,len(x))<0.5)
        except Exception:
            need_dt=True
        if need_dt:
            try:
                x_dt=pd.to_datetime(df[x_col],errors='coerce')
                if x_dt.notna().sum()>0:
                    first=x_dt.dropna().iloc[0]; x=(x_dt-first).dt.total_seconds(); x_label=f'Elapsed (s) from {first.strftime("%Y-%m-%d %H:%M:%S")} '
                else: x=x_series; x_label=x_col
            except Exception:
                x=x_series; x_label=x_col
        else:
            x_label=x_col
        # Plot each selected Y column
        self.fig.clear(); ax = self.fig.add_subplot(111)
        # font sizes from UI
        legend_font = int(self.legend_font_spin.value()) if hasattr(self, 'legend_font_spin') else 10
        title_font = int(self.title_font_spin.value()) if hasattr(self, 'title_font_spin') else 12
        tick_font = int(self.tick_font_spin.value()) if hasattr(self, 'tick_font_spin') else 10
        plotted_any = False
        # store mapping of plotted series keys -> artist for interactive legend renaming
        self._plotted_keys = []
        self._plotted_artists = []
        # clear previous legend pick connection id
        try:
            if hasattr(self, '_legend_pick_cid') and getattr(self, 'canvas', None) is not None:
                try:
                    self.canvas.mpl_disconnect(self._legend_pick_cid)
                except Exception:
                    pass
                self._legend_pick_cid = None
        except Exception:
            pass

        for yi, ycol in enumerate(y_items):
            try:
                y_series = pd.to_numeric(df[ycol], errors='coerce')
            except Exception:
                y_series = df[ycol]
            mask = x.notna() & pd.Series(y_series).notna()
            xp = x[mask]; yp = pd.Series(y_series)[mask]
            if len(xp) == 0 or len(yp) == 0:
                continue
            plotted_any = True
            # determine display label from custom mapping if provided
            disp_label = (self.series_labels.get(ycol) or ycol) if hasattr(self, 'series_labels') else ycol
            if plot_type == 'line':
                lw = float(self.line_width_spin.value()) if hasattr(self, 'line_width_spin') else 1.0
                color = self.series_colors.get(ycol) if getattr(self, 'series_colors', None) else None
                if color:
                    artist, = ax.plot(xp, yp, marker='o', linestyle='-', markersize=4, linewidth=lw, label=disp_label, color=color)
                else:
                    artist, = ax.plot(xp, yp, marker='o', linestyle='-', markersize=4, linewidth=lw, label=disp_label)
                # remember the original series key so legend interactions can map back
                self._plotted_keys.append(ycol)
                self._plotted_artists.append(artist)
            else:
                color = self.series_colors.get(ycol) if getattr(self, 'series_colors', None) else None
                if color:
                    artist = ax.scatter(xp, yp, s=30, label=disp_label, color=color)
                else:
                    artist = ax.scatter(xp, yp, s=30, label=disp_label)
                self._plotted_keys.append(ycol)
                self._plotted_artists.append(artist)
        if not plotted_any:
            QtWidgets.QMessageBox.warning(self,'No data','No valid (X,Y) pairs to plot'); return
        ax.set_xlabel(self.x_label_edit.text() or x_label, fontsize=title_font)
        ax.set_ylabel(self.y_label_edit.text() or ','.join(y_items), fontsize=title_font)
        ax.grid(True)
        try:
            ax.tick_params(axis='both', labelsize=int(tick_font))
        except Exception:
            pass
        # show legend if requested (this will include plotted series and any named reference lines)
        try:
            if getattr(self, 'legend_chk', None) and self.legend_chk.isChecked():
                try:
                    leg = ax.legend(loc=getattr(self, '_legend_loc', 'best'), prop={'size': int(legend_font)})
                except Exception:
                    leg = ax.legend(loc=getattr(self, '_legend_loc', 'best'))
                # connect pick and right-click handlers
                try:
                    self._connect_legend_handlers(leg)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if pd.api.types.is_numeric_dtype(x):
                xmax=float(x.max()) if len(x)>0 else 0.0
                if xmax>1e-9: ax.set_xlim(0.0,xmax)
        except Exception:
            pass
        # draw any stored reference lines
        # draw any stored reference lines and keep their artist handles
        self._h_line_artists = []
        self._v_line_artists = []
        try:
            for ih, h in enumerate(getattr(self, 'h_lines', [])):
                if isinstance(h, dict):
                    lab = h.get('label') if h.get('label') else None
                    art = ax.axhline(h.get('value'), color=h.get('color', '#d62728'), linestyle=h.get('linestyle', '--'), linewidth=h.get('linewidth', 1), label=lab)
                    self._h_line_artists.append(art)
                else:
                    art = ax.axhline(h, color='#d62728', linestyle='--', linewidth=1)
                    self._h_line_artists.append(art)
            for iv, v in enumerate(getattr(self, 'v_lines', [])):
                if isinstance(v, dict):
                    lab = v.get('label') if v.get('label') else None
                    art = ax.axvline(v.get('value'), color=v.get('color', '#2ca02c'), linestyle=v.get('linestyle', '--'), linewidth=v.get('linewidth', 1), label=lab)
                    self._v_line_artists.append(art)
                else:
                    art = ax.axvline(v, color='#2ca02c', linestyle='--', linewidth=1)
                    self._v_line_artists.append(art)
        except Exception:
            pass

        # build legend from handles/labels so reference lines and plotted series are included
        try:
            if getattr(self, 'legend_chk', None) and self.legend_chk.isChecked():
                try:
                    handles, labels = ax.get_legend_handles_labels()
                    if getattr(self, '_legend_loc', 'best') == 'outside_right':
                        leg = ax.legend(handles, labels, loc='center left', bbox_to_anchor=(1.02, 0.5), borderaxespad=0., prop={'size': int(legend_font)})
                    else:
                        leg = ax.legend(handles, labels, loc=getattr(self, '_legend_loc', 'best'), prop={'size': int(legend_font)})
                except Exception:
                    leg = ax.legend(loc=getattr(self, '_legend_loc', 'best'))
                try:
                    self._connect_legend_handlers(leg)
                except Exception:
                    pass
        except Exception:
            pass
        # apply saved axis limits if present
        try:
            if getattr(self, 'desired_xlim', None) is not None:
                ax.set_xlim(tuple(self.desired_xlim))
            if getattr(self, 'desired_ylim', None) is not None:
                ax.set_ylim(tuple(self.desired_ylim))
        except Exception:
            pass
        self.canvas.draw(); self.set_status(f'Plotted {",".join(y_items)} vs {x_col}',3000)

    def add_hline(self):
        try:
            val = float(self.h_spin.value())
        except Exception:
            return
        self.h_lines.append(val)
        self.lines_list.addItem(f'H: {val}')
        # refresh plot if present
        try:
            self.on_plot()
        except Exception:
            pass

    def add_vline(self):
        try:
            val = float(self.v_spin.value())
        except Exception:
            return
        self.v_lines.append(val)
        self.lines_list.addItem(f'V: {val}')
        try:
            self.on_plot()
        except Exception:
            pass

    def remove_selected_line(self):
        items = self.lines_list.selectedItems()
        for it in items:
            txt = it.text()
            try:
                if txt.startswith('H:'):
                    val = float(txt.split(':',1)[1].strip())
                    if val in self.h_lines:
                        self.h_lines.remove(val)
                elif txt.startswith('V:'):
                    val = float(txt.split(':',1)[1].strip())
                    if val in self.v_lines:
                        self.v_lines.remove(val)
            except Exception:
                pass
            self.lines_list.takeItem(self.lines_list.row(it))
        try:
            self.on_plot()
        except Exception:
            pass

    def clear_lines(self):
        self.h_lines.clear(); self.v_lines.clear(); self.lines_list.clear()
        try:
            self.on_plot()
        except Exception:
            pass

    def open_lines_dialog(self):
        dlg = ReferenceLinesDialog(self, list(self.h_lines), list(self.v_lines))
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            # update lists and refresh
            self.h_lines = dlg.h_lines
            self.v_lines = dlg.v_lines
            # update lines_list widget to reflect new set
            self.lines_list.clear()
            for h in self.h_lines:
                self.lines_list.addItem(f'H: {h}')
            for v in self.v_lines:
                self.lines_list.addItem(f'V: {v}')
            try:
                self.on_plot()
            except Exception:
                pass
    def _normalize_lines_for_save(self, lines):
        out = []
        for l in lines:
            if isinstance(l, dict):
                entry = {
                    'value': float(l.get('value')),
                    'color': str(l.get('color')) if l.get('color') is not None else None,
                    'linewidth': float(l.get('linewidth')) if l.get('linewidth') is not None else None,
                    'linestyle': str(l.get('linestyle')) if l.get('linestyle') is not None else None,
                    'label': str(l.get('label')) if l.get('label') is not None else None,
                }
                out.append(entry)
            else:
                try:
                    out.append({'value': float(l), 'color': None, 'linewidth': None, 'linestyle': None, 'label': None})
                except Exception:
                    out.append({'value': None, 'color': None, 'linewidth': None, 'linestyle': None, 'label': str(l)})
        return out

    def save_graph_format(self):
        # Save current plot settings to a JSON file
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save plot format', '', 'JSON (*.json)')
        if not path:
            return
        try:
            fmt = {
                'plot_type': self.plot_type_combo.currentText(),
                'sheet': self.sheet_combo.currentText(),
                'x_col': self.x_combo.currentText(),
                'y_items': [self.y_list.item(i).text() for i in range(self.y_list.count()) if self.y_list.item(i).isSelected()] or [self.y_list.item(i).text() for i in range(self.y_list.count())],
                'x_label': self.x_label_edit.text(),
                'y_label': self.y_label_edit.text(),
                'line_width': float(self.line_width_spin.value()),
                'legend': bool(self.legend_chk.isChecked()) if getattr(self, 'legend_chk', None) else False,
                'series_labels': dict(self.series_labels) if getattr(self, 'series_labels', None) else {},
                'series_colors': dict(self.series_colors) if getattr(self, 'series_colors', None) else {},
                'legend_font': int(self.legend_font_spin.value()) if getattr(self, 'legend_font_spin', None) else None,
                'title_font': int(self.title_font_spin.value()) if getattr(self, 'title_font_spin', None) else None,
                'tick_font': int(self.tick_font_spin.value()) if getattr(self, 'tick_font_spin', None) else None,
                'legend_loc': getattr(self, '_legend_loc', 'best'),
                'h_lines': self._normalize_lines_for_save(getattr(self, 'h_lines', [])),
                'v_lines': self._normalize_lines_for_save(getattr(self, 'v_lines', [])),
                'xlim': list(self.desired_xlim) if self.desired_xlim is not None else None,
                'ylim': list(self.desired_ylim) if self.desired_ylim is not None else None,
            }
            # ensure .json extension
            if not path.lower().endswith('.json'):
                path = path + '.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(fmt, f, indent=2, ensure_ascii=False)
            self.set_status(f'Saved format: {path}', 3000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Save format failed', str(e))

    def _prompt_map(self, missing_name, available_cols):
        # Prompt user to choose a replacement for missing column
        items = ['<none>'] + available_cols
        choice, ok = QtWidgets.QInputDialog.getItem(self, 'Map column', f"Map '{missing_name}' to:", items, 0, False)
        if not ok:
            return None
        if choice == '<none>':
            return None
        return choice

    def _on_legend_pick(self, event):
        """Handle pick events on legend texts to allow in-place renaming of plotted series."""
        try:
            artist = event.artist
            # only handle Text picks we mapped
            key = None
            try:
                key = self._legend_text_map.get(artist)
            except Exception:
                key = None
            if not key:
                return
            current = artist.get_text()
            # prompt user for a new display name
            new, ok = QtWidgets.QInputDialog.getText(self, 'Rename series', f"Rename '{key}' to:", text=current)
            if not ok:
                return
            new = new.strip()
            if not new:
                return
            # store mapping and update legend text and underlying artist label
            try:
                self.series_labels[key] = new
            except Exception:
                pass
            try:
                artist.set_text(new)
            except Exception:
                pass
            # also update the actual plotted artist label so future legends match
            try:
                # find the plotted artist corresponding to key
                for k, a in zip(getattr(self, '_plotted_keys', []), getattr(self, '_plotted_artists', [])):
                    if k == key:
                        try:
                            a.set_label(new)
                        except Exception:
                            pass
                        break
            except Exception:
                pass
            try:
                self.canvas.draw()
            except Exception:
                pass
        except Exception:
            return

    def _connect_legend_handlers(self, leg):
        """Ensure legend pick and button handlers are connected and map texts to keys."""
        # disconnect existing handlers first
        try:
            if getattr(self, '_legend_pick_cid', None) is not None:
                try:
                    self.canvas.mpl_disconnect(self._legend_pick_cid)
                except Exception:
                    pass
                self._legend_pick_cid = None
        except Exception:
            pass
        try:
            if getattr(self, '_legend_button_cid', None) is not None:
                try:
                    self.canvas.mpl_disconnect(self._legend_button_cid)
                except Exception:
                    pass
                self._legend_button_cid = None
        except Exception:
            pass

        self._legend = leg
        # build mapping of legend text objects -> original series keys (for plotted series)
        self._legend_text_map = {}
        try:
            texts = leg.get_texts()
            # build a reverse map of display label -> original series key where possible
            inv_series = {}
            try:
                for k, v in (self.series_labels.items() if getattr(self, 'series_labels', None) else []):
                    inv_series[v] = k
            except Exception:
                # older mapping style: self.series_labels may be dict original->display
                try:
                    inv_series = {v: k for k, v in (self.series_labels.items() if getattr(self, 'series_labels', None) else [])}
                except Exception:
                    inv_series = {}

            for t in texts:
                try:
                    t.set_picker(True)
                except Exception:
                    pass
                lab = t.get_text()
                key = None
                # prefer mapping from display name to original series key
                try:
                    if lab in inv_series:
                        key = ('series', inv_series[lab])
                except Exception:
                    key = None
                # fallback: if the label exactly matches an original plotted key
                if key is None:
                    try:
                        if lab in getattr(self, '_plotted_keys', []):
                            key = ('series', lab)
                    except Exception:
                        pass
                # fallback: match reference line labels
                if key is None:
                    try:
                        for idx, hv in enumerate(getattr(self, 'h_lines', [])):
                            labv = hv.get('label') if isinstance(hv, dict) else None
                            if labv and labv == lab:
                                key = ('h', idx); break
                    except Exception:
                        pass
                if key is None:
                    try:
                        for idx, vv in enumerate(getattr(self, 'v_lines', [])):
                            labv = vv.get('label') if isinstance(vv, dict) else None
                            if labv and labv == lab:
                                key = ('v', idx); break
                    except Exception:
                        pass
                if key is not None:
                    try:
                        self._legend_text_map[t] = key
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            self._legend_pick_cid = self.canvas.mpl_connect('pick_event', self._on_legend_pick)
        except Exception:
            self._legend_pick_cid = None
        try:
            self._legend_button_cid = self.canvas.mpl_connect('button_press_event', self._on_legend_button_press)
        except Exception:
            self._legend_button_cid = None
        # make the legend draggable and watch for release to snap to right
        try:
            if getattr(self, '_legend', None) is not None:
                try:
                    self._legend.set_draggable(True)
                except Exception:
                    try:
                        self._legend.set_draggable(True, use_blit=False)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            # disconnect previous release handler
            if getattr(self, '_legend_release_cid', None) is not None:
                try:
                    self.canvas.mpl_disconnect(self._legend_release_cid)
                except Exception:
                    pass
                self._legend_release_cid = None
        except Exception:
            pass
        try:
            self._legend_release_cid = self.canvas.mpl_connect('button_release_event', self._on_legend_release)
        except Exception:
            self._legend_release_cid = None

    def _on_legend_button_press(self, event):
        """Handle right-clicks on the legend: show context menu for Rename / Move."""
        try:
            # only interested in right-clicks
            if getattr(event, 'button', None) != 3:
                return
            if getattr(self, '_legend', None) is None:
                return
            # determine renderer and legend bounds
            try:
                renderer = self.canvas.get_renderer()
            except Exception:
                try:
                    renderer = self.canvas.figure.canvas.get_renderer()
                except Exception:
                    renderer = None
            if renderer is None:
                return
            try:
                bbox = self._legend.get_window_extent(renderer)
                if not bbox.contains(event.x, event.y):
                    return
            except Exception:
                return

            # find which legend text (if any) was clicked
            clicked_text = None
            try:
                for t in self._legend.get_texts():
                    try:
                        tb = t.get_window_extent(renderer)
                        if tb.contains(event.x, event.y):
                            clicked_text = t
                            break
                    except Exception:
                        continue
            except Exception:
                clicked_text = None

            # Build a Qt menu at cursor
            menu = QtWidgets.QMenu(self)
            rename_act = None
            if clicked_text is not None:
                rename_act = menu.addAction('Rename entry')
            size_act = menu.addAction('Legend size...')
            move_menu = menu.addMenu('Move legend')
            locs = [
                ('Best', 'best'), ('Upper Right', 'upper right'), ('Upper Left', 'upper left'),
                ('Lower Right', 'lower right'), ('Lower Left', 'lower left'), ('Center Left', 'center left'),
                ('Center Right', 'center right'), ('Upper Center', 'upper center'), ('Lower Center', 'lower center'),
                ('Center', 'center')
            ]
            for lab, loc in locs:
                a = move_menu.addAction(lab)
                a.setData(loc)
            # add an 'Outside Right' placement that anchors the legend outside the axes on the right
            out_act = move_menu.addAction('Outside Right')
            out_act.setData('outside_right')

            # determine global position for the menu
            try:
                qpos = event.guiEvent.globalPos()
            except Exception:
                try:
                    qpos = self.canvas.mapToGlobal(QtCore.QPoint(int(event.x), int(event.y)))
                except Exception:
                    qpos = QtCore.QPoint(100, 100)

            act = menu.exec_(qpos)
            if act is None:
                return

            # Rename action
            if act == rename_act:
                if clicked_text is None:
                    return
                key = None
                try:
                    key = self._legend_text_map.get(clicked_text)
                except Exception:
                    key = None
                current = clicked_text.get_text()
                new, ok = QtWidgets.QInputDialog.getText(self, 'Rename series', f"Rename '{key or current}' to:", text=current)
                if not ok:
                    return
                new = new.strip()
                if not new:
                    return
                try:
                    if key:
                        self.series_labels[key] = new
                        # update underlying plotted artist label
                        for k, a in zip(getattr(self, '_plotted_keys', []), getattr(self, '_plotted_artists', [])):
                            if k == key:
                                try:
                                    a.set_label(new)
                                except Exception:
                                    pass
                                break
                    else:
                        # fallback: update matched legend handle
                        try:
                            handles = self._legend.legendHandles
                            texts = self._legend.get_texts()
                            for h, t in zip(handles, texts):
                                if t == clicked_text:
                                    try:
                                        h.set_label(new)
                                    except Exception:
                                        pass
                                    break
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    # replot to ensure persistent mapping
                    self.on_plot()
                except Exception:
                    try:
                        self.canvas.draw()
                    except Exception:
                        pass
                return

            # Legend size action
            if act == size_act:
                try:
                    cur = int(self.legend_font_spin.value()) if getattr(self, 'legend_font_spin', None) else 10
                except Exception:
                    cur = 10
                val, ok = QtWidgets.QInputDialog.getInt(self, 'Legend font size', 'Legend font size:', value=cur, min=6, max=72)
                if not ok:
                    return
                try:
                    if getattr(self, 'legend_font_spin', None):
                        self.legend_font_spin.setValue(int(val))
                except Exception:
                    pass
                try:
                    self.on_plot()
                except Exception:
                    try:
                        self.canvas.draw()
                    except Exception:
                        pass
                return

            # Move action
            try:
                loc = act.data()
            except Exception:
                loc = None
            if loc:
                try:
                    self._legend_loc = loc
                except Exception:
                    self._legend_loc = 'best'
                try:
                    self.on_plot()
                except Exception:
                    try:
                        self.canvas.draw()
                    except Exception:
                        pass
                return
        except Exception:
            return

    def _on_legend_release(self, event):
        """Handle legend drag-release: snap to right outside area if legend was dragged outside axes."""
        try:
            if getattr(self, '_legend', None) is None:
                return
            # need renderer
            try:
                renderer = self.canvas.get_renderer()
            except Exception:
                try:
                    renderer = self.canvas.figure.canvas.get_renderer()
                except Exception:
                    renderer = None
            if renderer is None:
                return
            # legend bbox in window coords
            try:
                lbbox = self._legend.get_window_extent(renderer)
            except Exception:
                return
            # get the axes the legend is attached to
            try:
                ax = self._legend.axes
            except Exception:
                # fallback to first axes on figure
                try:
                    ax = self.fig.axes[0]
                except Exception:
                    ax = None
            if ax is None:
                return
            try:
                abbox = ax.get_window_extent(renderer)
            except Exception:
                return
            # if legend was moved to the right of the axes, snap to outside_right
            # use a small tolerance
            tol = 8
            if lbbox.x0 > (abbox.x1 - tol):
                try:
                    self._legend_loc = 'outside_right'
                    # replot to enforce anchored outside placement
                    self.on_plot()
                except Exception:
                    try:
                        self.canvas.draw()
                    except Exception:
                        pass
                return
            # otherwise if legend is fully inside axes, clear outside_right
            if lbbox.x0 >= abbox.x0 and lbbox.x1 <= abbox.x1 and lbbox.y0 >= abbox.y0 and lbbox.y1 <= abbox.y1:
                try:
                    self._legend_loc = 'best'
                except Exception:
                    pass
        except Exception:
            return

    def load_graph_format(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load plot format', '', 'JSON (*.json)')
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                fmt = json.load(f)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Load failed', str(e)); return

        # Ensure we have data loaded to map columns
        if self.current_df is None:
            QtWidgets.QMessageBox.warning(self, 'No data', 'Open an Excel sheet first so columns can be mapped.'); return

        # Build a view of available columns for the current sheet and for all sheets
        available = list(self.current_df.columns.astype(str))

        # detect saved plot type to pick appropriate mapping domain for Y (columns vs timestamps)
        saved_plot_type = (fmt.get('plot_type') or '').lower()

        # Map x_col and y_items using case-insensitive auto-mapping where possible.
        x_col = fmt.get('x_col')
        y_items = fmt.get('y_items') or []

        # Gather columns and (for capture sheets) timestamp values from every sheet so mapping choices
        # can include columns from any tab. Choices are returned in the form 'SheetName::ColumnName'
        all_choices = []
        avail_map_all = {}
        sheet_choices_map = {}
        sheet_ts_map = {}
        try:
            for sheet in (self.excel.sheet_names or []):
                try:
                    df_sheet = self.excel.parse(sheet_name=sheet)
                    # For the currently-selected sheet, prefer runtime DataFrame (which may include
                    # calculated columns like 'Noise_Floor_Median') so mapping choices include those.
                    if sheet == (self.sheet_combo.currentText() or '') and getattr(self, 'current_df', None) is not None:
                        # ensure runtime-calculated columns are present (e.g., Noise_Floor_Median)
                        cols_df = self.current_df
                        try:
                            if 'Noise_Floor_Median' not in cols_df.columns and getattr(self, 'capture_mode', False):
                                try:
                                    median_vals = self._compute_noise_floor_median_per_row(cols_df)
                                    cols_df = cols_df.copy()
                                    cols_df['Noise_Floor_Median'] = median_vals
                                    # update the stored current_df so subsequent UI sees the column
                                    self.current_df = cols_df
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        cols = list(cols_df.columns.astype(str))
                    else:
                        cols = list(df_sheet.columns.astype(str))
                    sheet_choices = []
                    for c in cols:
                        key = f"{sheet}::{c}"
                        sheet_choices.append(key)
                        all_choices.append(key)
                        avail_map_all[c.strip().lower()] = key
                    sheet_choices_map[sheet] = sheet_choices
                    # detect capture-style sheet to include timestamp values as mapping choices
                    try:
                        # For current sheet prefer self._ts_series if present (it may include runtime computed rows)
                        if sheet == (self.sheet_combo.currentText() or '') and getattr(self, '_ts_series', None):
                            ts_vals = list(self._ts_series)
                        else:
                            freq_candidates = self._infer_freq_axis_from_headers(df_sheet)
                            after_headers = list(df_sheet.columns.astype(str))[1:]
                            if ('capture' in sheet.lower()) or (freq_candidates and len(freq_candidates) >= max(3, len(after_headers) // 4)):
                                try:
                                    ts_vals = list(df_sheet.iloc[:, 0].astype(str))
                                except Exception:
                                    ts_vals = []
                            else:
                                ts_vals = []

                        if ts_vals:
                            ts_keys = [f"{sheet}::ts::{t}" for t in ts_vals]
                            sheet_ts_map[sheet] = ts_vals
                            all_choices.extend(ts_keys)
                            # map by lower-case ts text as well (may be long)
                            for t in ts_vals:
                                try:
                                    avail_map_all[str(t).strip().lower()] = f"{sheet}::ts::{t}"
                                except Exception:
                                    pass
                    except Exception:
                        pass
                except Exception:
                    continue
        except Exception:
            pass

        # Determine mapping domain for Y (timestamps vs columns) for preferred auto-mapping
        if saved_plot_type == 'fft' and getattr(self, 'capture_mode', False) and getattr(self, '_ts_series', None):
            # prefer timestamps from current sheet, but allow choices from all sheets
            y_domain = list(self._ts_series)
        else:
            y_domain = available

        # Build lowercase lookup for current-sheet columns and for all-sheet columns
        avail_map = {c.strip().lower(): c for c in available}
        ymap = {c.strip().lower(): c for c in y_domain}

        mapped_y = []
        # try to auto-map X by exact or case-insensitive match (first prefer current sheet, then any sheet)
        mapped_x = None
        if x_col in available:
            mapped_x = x_col
        else:
            try:
                key = x_col.strip().lower() if isinstance(x_col, str) else None
            except Exception:
                key = None
            if key and key in avail_map:
                mapped_x = avail_map[key]
            elif key and key in avail_map_all:
                mapped_x = avail_map_all[key]  # this is 'Sheet::Column' or 'Sheet::ts::val'

        # Try to auto-map Y items where possible (exact or case-insensitive). Collect those that remain unmatched.
        unmatched = {}
        for yi in y_items:
            # exact match in current sheet
            if yi in y_domain:
                mapped_y.append(yi)
                continue
            try:
                key = yi.strip().lower() if isinstance(yi, str) else None
            except Exception:
                key = None
            # try current sheet mapping
            if key and key in ymap:
                mapped_y.append(ymap[key]); continue
            # try any-sheet mapping
            if key and key in avail_map_all:
                mapped_y.append(avail_map_all[key]); continue
            # otherwise mark as unmatched and include choices from all sheets appropriate to plot type
            if saved_plot_type == 'fft':
                # timestamp choices across all sheets
                choices = []
                for sh, tsvals in sheet_ts_map.items():
                    for t in tsvals:
                        choices.append(f"{sh}::ts::{t}")
                unmatched[yi] = choices
            else:
                unmatched[yi] = all_choices

        # If x wasn't auto-mapped and it's missing, add to unmatched mapping choices (allow any-sheet choices)
        if mapped_x is None and x_col is not None and x_col not in available:
            # prefer any-sheet column choices
            unmatched[x_col] = all_choices

        # If anything remains unmatched, prompt the user once with MapAllDialog
        if unmatched:
            dlg = MapAllDialog(self, unmatched)
            if dlg.exec_() != QtWidgets.QDialog.Accepted:
                QtWidgets.QMessageBox.information(self, 'Mapping', 'Mapping cancelled; aborting load')
                return
            mapping = dlg.get_result()

            # After mapping, determine if mappings reference multiple different sheets. We only support switching
            # to a single sheet for applying the format; if user selected columns from multiple sheets, abort.
            referenced_sheets = set()
            for k, v in mapping.items():
                if isinstance(v, str) and '::' in v:
                    sh = v.split('::', 1)[0]
                    referenced_sheets.add(sh)
            # include mapped_x if it is a sheet-prefixed string
            if isinstance(mapped_x, str) and '::' in str(mapped_x):
                referenced_sheets.add(mapped_x.split('::', 1)[0])

            if len(referenced_sheets) > 1:
                QtWidgets.QMessageBox.warning(self, 'Mapping', 'Selected mappings reference multiple different sheets.\nPlease choose columns from a single sheet or save formats per-sheet.'); return

            # If a sheet was chosen via mappings, switch to it before applying column selections
            target_sheet = None
            if len(referenced_sheets) == 1:
                target_sheet = list(referenced_sheets)[0]
            # apply mapping for x if needed
            if mapped_x is None and x_col in unmatched:
                if x_col in mapping:
                    mapped_x = mapping.get(x_col)
                else:
                    QtWidgets.QMessageBox.information(self, 'Mapping', f'X column {x_col} not mapped; aborting load'); return
            # apply mappings for remaining y items
            for yi in y_items:
                if yi in mapped_y:
                    continue
                if yi in mapping:
                    mapped_y.append(mapping.get(yi))
                else:
                    # skip if still unmapped
                    pass

            # If a target_sheet was selected, switch to it now so subsequent UI updates use its columns
            if target_sheet and target_sheet != self.sheet_combo.currentText():
                try:
                    idx = self.sheet_combo.findText(target_sheet)
                    if idx >= 0:
                        self.sheet_combo.setCurrentIndex(idx)
                    else:
                        # try to select by exact match in the excel file
                        if target_sheet in (self.excel.sheet_names or []):
                            # set index directly
                            try:
                                self.sheet_combo.setCurrentText(target_sheet)
                            except Exception:
                                pass
                except Exception:
                    pass

        # finalize x_col
        if mapped_x is None:
            x_col = x_col
        else:
            x_col = mapped_x

        # apply format to UI
        try:
            # plot type
            pt = fmt.get('plot_type') or 'Line'
            # set plot type combo safely
            for i in range(self.plot_type_combo.count()):
                if self.plot_type_combo.itemText(i).lower() == pt.lower():
                    self.plot_type_combo.setCurrentIndex(i); break

            # set x and y
            if x_col in available:
                # set current x combobox
                ix = self.x_combo.findText(x_col)
                if ix >= 0:
                    self.x_combo.setCurrentIndex(ix)
            # ensure y selections depending on plot type
            if saved_plot_type == 'fft' and getattr(self, 'capture_mode', False) and mapped_y:
                # switch to timestamp combo and set to first mapped timestamp
                try:
                    # make sure timestamp combo is populated
                    if getattr(self, 'y_combo', None) is not None and getattr(self, '_ts_series', None):
                        self.y_combo.clear(); self.y_combo.addItems(list(self._ts_series))
                        # pick the first mapped timestamp if present
                        try:
                            idx = self.y_combo.findText(mapped_y[0])
                            if idx >= 0:
                                self.y_combo.setCurrentIndex(idx)
                        except Exception:
                            pass
                    self.y_selector_stack.setCurrentIndex(0)
                except Exception:
                    pass
            else:
                # ensure y list selections for non-FFT
                for i in range(self.y_list.count()):
                    it = self.y_list.item(i)
                    it.setSelected(it.text() in mapped_y)

            # labels and width
            self.x_label_edit.setText(fmt.get('x_label') or '')
            self.y_label_edit.setText(fmt.get('y_label') or '')
            try:
                self.line_width_spin.setValue(float(fmt.get('line_width') or 1.0))
            except Exception:
                pass
            # legend
            try:
                if getattr(self, 'legend_chk', None):
                    self.legend_chk.setChecked(bool(fmt.get('legend')))
            except Exception:
                pass

            # series labels
            self.series_labels = fmt.get('series_labels') or {}
            # series colors
            try:
                self.series_colors = fmt.get('series_colors') or {}
            except Exception:
                self.series_colors = {}
            # font sizes
            try:
                lf = fmt.get('legend_font')
                if lf is not None and getattr(self, 'legend_font_spin', None):
                    try:
                        self.legend_font_spin.setValue(int(lf))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                tf = fmt.get('title_font')
                if tf is not None and getattr(self, 'title_font_spin', None):
                    try:
                        self.title_font_spin.setValue(int(tf))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                tk = fmt.get('tick_font')
                if tk is not None and getattr(self, 'tick_font_spin', None):
                    try:
                        self.tick_font_spin.setValue(int(tk))
                    except Exception:
                        pass
            except Exception:
                pass
            # legend location
            try:
                ll = fmt.get('legend_loc')
                if ll:
                    self._legend_loc = ll
            except Exception:
                pass
            # series colors
            try:
                self.series_colors = fmt.get('series_colors') or {}
            except Exception:
                self.series_colors = {}

            # lines
            def _convert_loaded(lines):
                out = []
                for l in lines or []:
                    if not isinstance(l, dict):
                        continue
                    entry = {'value': float(l.get('value')) if l.get('value') is not None else None,
                             'color': l.get('color'), 'linewidth': float(l.get('linewidth')) if l.get('linewidth') is not None else None,
                             'linestyle': l.get('linestyle'), 'label': l.get('label')}
                    out.append(entry)
                return out

            self.h_lines = _convert_loaded(fmt.get('h_lines'))
            self.v_lines = _convert_loaded(fmt.get('v_lines'))

            # axis limits
            self.desired_xlim = tuple(fmt.get('xlim')) if fmt.get('xlim') else None
            self.desired_ylim = tuple(fmt.get('ylim')) if fmt.get('ylim') else None

            # refresh the internal lines_list bookkeeping
            self.lines_list.clear()
            for h in self.h_lines:
                self.lines_list.addItem(f"H: {h.get('value')}")
            for v in self.v_lines:
                self.lines_list.addItem(f"V: {v.get('value')}")

            # trigger a plot redraw
            try:
                self.on_plot()
            except Exception:
                pass
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Apply format failed', str(e))
    def open_names_dialog(self):
        # Build a list of candidate series (available Y columns or timestamps)
        candidates = []
        if self.capture_mode and self.plot_type_combo.currentText().lower() == 'fft':
            # For FFT allow editing timestamps; present all timestamps
            candidates = list(self._ts_series)
        else:
            # Prefer currently selected Y columns (the ones being plotted). If none selected, show all.
            sel = [it.text() for it in self.y_list.selectedItems()]
            if sel:
                candidates = sel
            else:
                candidates = [self.y_list.item(i).text() for i in range(self.y_list.count())]

        dlg = SeriesNamesDialog(self, dict(self.series_labels), candidates)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.series_labels = dlg.get_result()
            # redraw plot to update legend labels
            try:
                self.on_plot()
            except Exception:
                pass

    def open_colors_dialog(self):
        # Build a list of candidate series (available Y columns or timestamps)
        candidates = []
        if self.capture_mode and self.plot_type_combo.currentText().lower() == 'fft':
            candidates = list(self._ts_series)
        else:
            sel = [it.text() for it in self.y_list.selectedItems()]
            if sel:
                candidates = sel
            else:
                candidates = [self.y_list.item(i).text() for i in range(self.y_list.count())]

        dlg = SeriesColorsDialog(self, dict(self.series_colors), candidates)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.series_colors = dlg.get_result()
            try:
                self.on_plot()
            except Exception:
                pass
    def on_save_plot(self):
        path,_=QtWidgets.QFileDialog.getSaveFileName(self,'Save plot image','','PNG Image (*.png);;PDF (*.pdf)')
        if not path: return
        try:
            self.fig.savefig(path,dpi=150,bbox_inches='tight'); self.set_status(f'Saved plot: {path}',3000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,'Save failed',str(e))


class ReferenceLinesDialog(QtWidgets.QDialog):
    """Dialog to add/remove horizontal and vertical reference lines.

    It operates on copies of the parent's lists and returns accepted lists on OK.
    """
    def __init__(self, parent: QtWidgets.QWidget, h_lines=None, v_lines=None):
        super().__init__(parent)
        self.setWindowTitle('Reference Lines')
        self.setModal(True)
        self.h_lines = list(h_lines or [])
        self.v_lines = list(v_lines or [])

        v = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QWidget()
        fh = QtWidgets.QHBoxLayout(form)
        # H-line controls
        fh.addWidget(QtWidgets.QLabel('H-line (Y):'))
        self.h_spin = QtWidgets.QDoubleSpinBox()
        self.h_spin.setRange(-1e12, 1e12)
        self.h_spin.setDecimals(6)
        fh.addWidget(self.h_spin)
        btn_h = QtWidgets.QPushButton('Add H')
        btn_h.clicked.connect(self._add_h)
        fh.addWidget(btn_h)
        fh.addWidget(QtWidgets.QLabel('Color:'))
        self._h_color = '#d62728'
        self.h_color_btn = QtWidgets.QPushButton(' ')
        self.h_color_btn.setFixedWidth(28)
        self.h_color_btn.setStyleSheet(f'background:{self._h_color}')
        self.h_color_btn.clicked.connect(self._choose_color_h)
        fh.addWidget(self.h_color_btn)
        fh.addWidget(QtWidgets.QLabel('Width:'))
        self.h_width = QtWidgets.QDoubleSpinBox()
        self.h_width.setRange(0.1, 20.0)
        self.h_width.setDecimals(2)
        self.h_width.setValue(1.0)
        fh.addWidget(self.h_width)
        fh.addWidget(QtWidgets.QLabel('Style:'))
        self.h_style = QtWidgets.QComboBox()
        self.h_style.addItems(['Solid', 'Dashed', 'DashDot', 'Dotted'])
        fh.addWidget(self.h_style)
        fh.addWidget(QtWidgets.QLabel('Name:'))
        self.h_name = QtWidgets.QLineEdit()
        self.h_name.setPlaceholderText('optional name')
        fh.addWidget(self.h_name)
        # Update H button (disabled until an H is selected)
        self.update_h_btn = QtWidgets.QPushButton('Update H')
        self.update_h_btn.setEnabled(False)
        self.update_h_btn.clicked.connect(self._update_selected)
        fh.addWidget(self.update_h_btn)

        # V-line controls
        fh.addSpacing(8)
        fh.addWidget(QtWidgets.QLabel('V-line (X):'))
        self.v_spin = QtWidgets.QDoubleSpinBox()
        self.v_spin.setRange(-1e12, 1e12)
        self.v_spin.setDecimals(6)
        fh.addWidget(self.v_spin)
        btn_v = QtWidgets.QPushButton('Add V')
        btn_v.clicked.connect(self._add_v)
        fh.addWidget(btn_v)
        fh.addWidget(QtWidgets.QLabel('Color:'))
        self._v_color = '#2ca02c'
        self.v_color_btn = QtWidgets.QPushButton(' ')
        self.v_color_btn.setFixedWidth(28)
        self.v_color_btn.setStyleSheet(f'background:{self._v_color}')
        self.v_color_btn.clicked.connect(self._choose_color_v)
        fh.addWidget(self.v_color_btn)
        fh.addWidget(QtWidgets.QLabel('Width:'))
        self.v_width = QtWidgets.QDoubleSpinBox()
        self.v_width.setRange(0.1, 20.0)
        self.v_width.setDecimals(2)
        self.v_width.setValue(1.0)
        fh.addWidget(self.v_width)
        fh.addWidget(QtWidgets.QLabel('Style:'))
        self.v_style = QtWidgets.QComboBox()
        self.v_style.addItems(['Solid', 'Dashed', 'DashDot', 'Dotted'])
        fh.addWidget(self.v_style)
        fh.addWidget(QtWidgets.QLabel('Name:'))
        self.v_name = QtWidgets.QLineEdit()
        self.v_name.setPlaceholderText('optional name')
        fh.addWidget(self.v_name)
        # Update V button (disabled until a V is selected)
        self.update_v_btn = QtWidgets.QPushButton('Update V')
        self.update_v_btn.setEnabled(False)
        self.update_v_btn.clicked.connect(self._update_selected)
        fh.addWidget(self.update_v_btn)

        v.addWidget(form)

        self.listw = QtWidgets.QListWidget()
        v.addWidget(self.listw)
        self._refresh_list()

        btns = QtWidgets.QWidget()
        bh = QtWidgets.QHBoxLayout(btns)
        self.btn_remove = QtWidgets.QPushButton('Remove Selected')
        self.btn_remove.clicked.connect(self._remove_selected)
        bh.addWidget(self.btn_remove)
        self.btn_clear = QtWidgets.QPushButton('Clear')
        self.btn_clear.clicked.connect(self._clear)
        bh.addWidget(self.btn_clear)
        bh.addStretch()
        self.btn_ok = QtWidgets.QPushButton('OK')
        self.btn_ok.clicked.connect(self.accept)
        bh.addWidget(self.btn_ok)
        self.btn_cancel = QtWidgets.QPushButton('Cancel')
        self.btn_cancel.clicked.connect(self.reject)
        bh.addWidget(self.btn_cancel)
        v.addWidget(btns)
        # when selection changes in the list, populate controls
        try:
            self.listw.itemSelectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass

    def _refresh_list(self):
        self.listw.clear()
        for h in self.h_lines:
            if isinstance(h, dict):
                txt = f"H: {h.get('value')}  {h.get('color','#')} lw={h.get('linewidth',1)} {h.get('linestyle','--')}"
                it = QtWidgets.QListWidgetItem(txt)
                it.setData(QtCore.Qt.UserRole, h)
            else:
                it = QtWidgets.QListWidgetItem(f'H: {h}')
                it.setData(QtCore.Qt.UserRole, h)
            self.listw.addItem(it)
        for vv in self.v_lines:
            if isinstance(vv, dict):
                txt = f"V: {vv.get('value')}  {vv.get('color','#')} lw={vv.get('linewidth',1)} {vv.get('linestyle','--')}"
                it = QtWidgets.QListWidgetItem(txt)
                it.setData(QtCore.Qt.UserRole, vv)
            else:
                it = QtWidgets.QListWidgetItem(f'V: {vv}')
                it.setData(QtCore.Qt.UserRole, vv)
            self.listw.addItem(it)

    def _add_h(self):
        try:
            v = float(self.h_spin.value())
        except Exception:
            return
        style_map = {'Solid': '-', 'Dashed': '--', 'DashDot': '-.', 'Dotted': ':'}
        entry = {'value': v, 'color': getattr(self, '_h_color', '#d62728'), 'linewidth': float(self.h_width.value()), 'linestyle': style_map.get(self.h_style.currentText(), '--'), 'label': (self.h_name.text() or None)}
        self.h_lines.append(entry)
        # update the dialog list; parent will be updated only on OK
        self._refresh_list()

    def _add_v(self):
        try:
            v = float(self.v_spin.value())
        except Exception:
            return
        style_map = {'Solid': '-', 'Dashed': '--', 'DashDot': '-.', 'Dotted': ':'}
        entry = {'value': v, 'color': getattr(self, '_v_color', '#2ca02c'), 'linewidth': float(self.v_width.value()), 'linestyle': style_map.get(self.v_style.currentText(), '-.'), 'label': (self.v_name.text() or None)}
        self.v_lines.append(entry)
        # update the dialog list; parent will be updated only on OK
        self._refresh_list()

    def _remove_selected(self):
        items = list(self.listw.selectedItems())
        for it in items:
            data = it.data(QtCore.Qt.UserRole)
            txt = it.text()
            try:
                if isinstance(data, dict):
                    # remove matching dict from dialog lists
                    if txt.startswith('H:'):
                        for h in list(self.h_lines):
                            if isinstance(h, dict) and h == data:
                                self.h_lines.remove(h)
                                break
                    elif txt.startswith('V:'):
                        for vv in list(self.v_lines):
                            if isinstance(vv, dict) and vv == data:
                                self.v_lines.remove(vv)
                                break
                    # remove from parent's hidden lines_list if present
                    # parent will be updated on OK; do not modify parent here
                    pass
                else:
                    # legacy numeric handling
                    try:
                        if txt.startswith('H:'):
                            val = float(txt.split(':',1)[1].strip())
                            if val in self.h_lines:
                                self.h_lines.remove(val)
                            # parent updated on OK
                        elif txt.startswith('V:'):
                            val = float(txt.split(':',1)[1].strip())
                            if val in self.v_lines:
                                self.v_lines.remove(val)
                            # parent updated on OK
                    except Exception:
                        pass
            except Exception:
                pass
        self._refresh_list()
        # parent plot will be refreshed when dialog is accepted

    def _clear(self):
        self.h_lines.clear(); self.v_lines.clear(); self._refresh_list()
        # parent will be updated on OK

    def _choose_color_h(self):
        col = QtWidgets.QColorDialog.getColor(QtCore.Qt.red, self, 'Choose H-line color')
        if col.isValid():
            self._h_color = col.name()
            self.h_color_btn.setStyleSheet(f'background:{self._h_color}')

    def _choose_color_v(self):
        col = QtWidgets.QColorDialog.getColor(QtCore.Qt.green, self, 'Choose V-line color')
        if col.isValid():
            self._v_color = col.name()
            self.v_color_btn.setStyleSheet(f'background:{self._v_color}')

    def _on_selection_changed(self):
        """Populate the dialog controls with the first selected item's values."""
        items = list(self.listw.selectedItems())
        if not items:
            try:
                self.btn_update.setEnabled(False)
            except Exception:
                pass
            return
        it = items[0]
        txt = it.text()
        data = it.data(QtCore.Qt.UserRole)
        # detect H or V based on text prefix
        try:
            if txt.startswith('H:'):
                # populate H controls
                if isinstance(data, dict):
                    self.h_spin.setValue(float(data.get('value') or 0.0))
                    self._h_color = data.get('color') or getattr(self, '_h_color', '#d62728')
                    try:
                        self.h_color_btn.setStyleSheet(f'background:{self._h_color}')
                    except Exception:
                        pass
                    try:
                        self.h_width.setValue(float(data.get('linewidth') or 1.0))
                    except Exception:
                        pass
                    # reverse map linestyle to friendly name
                    ls = data.get('linestyle') or '--'
                    style_name = 'Dashed'
                    if ls == '-':
                        style_name = 'Solid'
                    elif ls == '-.':
                        style_name = 'DashDot'
                    elif ls == ':':
                        style_name = 'Dotted'
                    try:
                        idx = self.h_style.findText(style_name)
                        if idx >= 0:
                            self.h_style.setCurrentIndex(idx)
                    except Exception:
                        pass
                    try:
                        self.h_name.setText(data.get('label') or '')
                    except Exception:
                        pass
                else:
                    # legacy numeric
                    try:
                        self.h_spin.setValue(float(data))
                    except Exception:
                        pass
                try:
                    # enable the H update button and disable V update
                    try:
                        self.update_h_btn.setEnabled(True)
                    except Exception:
                        pass
                    try:
                        self.update_v_btn.setEnabled(False)
                    except Exception:
                        pass
                except Exception:
                    pass
            elif txt.startswith('V:'):
                # populate V controls
                if isinstance(data, dict):
                    self.v_spin.setValue(float(data.get('value') or 0.0))
                    self._v_color = data.get('color') or getattr(self, '_v_color', '#2ca02c')
                    try:
                        self.v_color_btn.setStyleSheet(f'background:{self._v_color}')
                    except Exception:
                        pass
                    try:
                        self.v_width.setValue(float(data.get('linewidth') or 1.0))
                    except Exception:
                        pass
                    ls = data.get('linestyle') or '-.'
                    style_name = 'DashDot'
                    if ls == '-':
                        style_name = 'Solid'
                    elif ls == '--':
                        style_name = 'Dashed'
                    elif ls == ':':
                        style_name = 'Dotted'
                    try:
                        idx = self.v_style.findText(style_name)
                        if idx >= 0:
                            self.v_style.setCurrentIndex(idx)
                    except Exception:
                        pass
                    try:
                        self.v_name.setText(data.get('label') or '')
                    except Exception:
                        pass
                else:
                    try:
                        self.v_spin.setValue(float(data))
                    except Exception:
                        pass
                try:
                    # enable the V update button and disable H update
                    try:
                        self.update_v_btn.setEnabled(True)
                    except Exception:
                        pass
                    try:
                        self.update_h_btn.setEnabled(False)
                    except Exception:
                        pass
                except Exception:
                    pass
            else:
                try:
                    try:
                        self.update_h_btn.setEnabled(False)
                    except Exception:
                        pass
                    try:
                        self.update_v_btn.setEnabled(False)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            try:
                self.btn_update.setEnabled(False)
            except Exception:
                pass

    def _update_selected(self):
        """Update the currently-selected list entry with values from the controls."""
        items = list(self.listw.selectedItems())
        if not items:
            return
        it = items[0]
        txt = it.text()
        data = it.data(QtCore.Qt.UserRole)
        style_map = {'Solid': '-', 'Dashed': '--', 'DashDot': '-.', 'Dotted': ':'}
        try:
            if txt.startswith('H:'):
                entry = {'value': float(self.h_spin.value()), 'color': getattr(self, '_h_color', '#d62728'), 'linewidth': float(self.h_width.value()), 'linestyle': style_map.get(self.h_style.currentText(), '--'), 'label': (self.h_name.text() or None)}
                # find and replace matching item in self.h_lines
                replaced = False
                for idx, h in enumerate(list(self.h_lines)):
                    try:
                        if isinstance(h, dict) and h == data:
                            self.h_lines[idx] = entry; replaced = True; break
                        elif not isinstance(h, dict) and float(h) == float(data):
                            self.h_lines[idx] = entry; replaced = True; break
                    except Exception:
                        continue
                if not replaced:
                    # fallback: append
                    self.h_lines.append(entry)
            elif txt.startswith('V:'):
                entry = {'value': float(self.v_spin.value()), 'color': getattr(self, '_v_color', '#2ca02c'), 'linewidth': float(self.v_width.value()), 'linestyle': style_map.get(self.v_style.currentText(), '-.'), 'label': (self.v_name.text() or None)}
                replaced = False
                for idx, v in enumerate(list(self.v_lines)):
                    try:
                        if isinstance(v, dict) and v == data:
                            self.v_lines[idx] = entry; replaced = True; break
                        elif not isinstance(v, dict) and float(v) == float(data):
                            self.v_lines[idx] = entry; replaced = True; break
                    except Exception:
                        continue
                if not replaced:
                    self.v_lines.append(entry)
            else:
                return
        except Exception:
            return
        # refresh list and keep selection on the updated entry
        self._refresh_list()
        # try to re-select the updated entry by matching value and label
        try:
            for i in range(self.listw.count()):
                it2 = self.listw.item(i)
                d2 = it2.data(QtCore.Qt.UserRole)
                if isinstance(d2, dict) and isinstance(entry, dict) and float(d2.get('value') or 0.0) == float(entry.get('value') or 0.0):
                    it2.setSelected(True); break
                elif not isinstance(d2, dict) and float(d2) == float(entry.get('value') or 0.0):
                    it2.setSelected(True); break
        except Exception:
            pass


class SeriesNamesDialog(QtWidgets.QDialog):
    """Dialog to edit display names for plotted series/timestamps.

    The dialog presents a simple two-column form: original series name and an
    editable display name. get_result() returns a mapping of original -> display
    name for non-empty edits.
    """
    def __init__(self, parent: QtWidgets.QWidget, initial_map: dict, candidates: list):
        super().__init__(parent)
        self.setWindowTitle('Edit Series Names')
        self.setModal(True)
        self._edits = {}

        v = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QWidget()
        fl = QtWidgets.QFormLayout(form)
        for name in candidates:
            le = QtWidgets.QLineEdit()
            # prefill with any existing mapping
            if initial_map and name in initial_map and initial_map.get(name):
                le.setText(initial_map.get(name))
            fl.addRow(QtWidgets.QLabel(name), le)
            self._edits[name] = le
        v.addWidget(form)

        btns = QtWidgets.QWidget()
        bh = QtWidgets.QHBoxLayout(btns)
        bh.addStretch()
        btn_ok = QtWidgets.QPushButton('OK')
        btn_ok.clicked.connect(self.accept)
        bh.addWidget(btn_ok)
        btn_cancel = QtWidgets.QPushButton('Cancel')
        btn_cancel.clicked.connect(self.reject)
        bh.addWidget(btn_cancel)
        v.addWidget(btns)

    def get_result(self) -> dict:
        out = {}
        for k, le in self._edits.items():
            txt = le.text().strip()
            if txt:
                out[k] = txt
        return out


class SeriesColorsDialog(QtWidgets.QDialog):
    """Dialog to edit per-series colors. Presents a list of series and a color button for each.

    get_result() returns a mapping series_name -> color hex string (e.g. '#rrggbb').
    """
    def __init__(self, parent: QtWidgets.QWidget, initial_map: dict, candidates: list):
        super().__init__(parent)
        self.setWindowTitle('Edit Series Colors')
        self.setModal(True)
        self._buttons = {}
        self._colors = dict(initial_map or {})

        v = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QWidget()
        fl = QtWidgets.QFormLayout(form)
        for name in candidates:
            btn = QtWidgets.QPushButton(' ')
            btn.setFixedWidth(48)
            # get initial color if present
            col = None
            if initial_map and name in initial_map and initial_map.get(name):
                col = initial_map.get(name)
            if col:
                try:
                    btn.setStyleSheet(f'background:{col}')
                except Exception:
                    pass
            # bind
            btn.clicked.connect(self._make_pick_handler(name, btn))
            fl.addRow(QtWidgets.QLabel(name), btn)
            self._buttons[name] = btn
        v.addWidget(form)

        btns = QtWidgets.QWidget()
        bh = QtWidgets.QHBoxLayout(btns)
        bh.addStretch()
        btn_ok = QtWidgets.QPushButton('OK')
        btn_ok.clicked.connect(self.accept)
        bh.addWidget(btn_ok)
        btn_cancel = QtWidgets.QPushButton('Cancel')
        btn_cancel.clicked.connect(self.reject)
        bh.addWidget(btn_cancel)
        v.addWidget(btns)

    def _make_pick_handler(self, name, btn):
        def handler():
            col = QtWidgets.QColorDialog.getColor(QtCore.Qt.white, self, f'Choose color for {name}')
            if col.isValid():
                hexc = col.name()
                try:
                    btn.setStyleSheet(f'background:{hexc}')
                except Exception:
                    pass
                self._colors[name] = hexc
        return handler

    def get_result(self) -> dict:
        return dict(self._colors)


class MapAllDialog(QtWidgets.QDialog):
    """Dialog to map multiple saved names to available current columns/timestamps at once.

    Provide a dict of name -> list_of_choices. The dialog shows a row per name with a QComboBox
    letting the user choose one of the choices or '<none>'. get_result() returns a mapping of
    name->chosen (omitting entries mapped to '<none>').
    """
    def __init__(self, parent: QtWidgets.QWidget, choices_map: dict):
        super().__init__(parent)
        self.setWindowTitle('Map saved names to current sheet')
        self.setModal(True)
        self._combos = {}

        v = QtWidgets.QVBoxLayout(self)
        w = QtWidgets.QWidget(); fl = QtWidgets.QFormLayout(w)
        for name, choices in choices_map.items():
            cb = QtWidgets.QComboBox()
            items = ['<none>'] + list(choices)
            cb.addItems(items)
            fl.addRow(QtWidgets.QLabel(name), cb)
            self._combos[name] = cb
        v.addWidget(w)

        btns = QtWidgets.QWidget(); bh = QtWidgets.QHBoxLayout(btns)
        bh.addStretch()
        ok = QtWidgets.QPushButton('OK'); ok.clicked.connect(self.accept); bh.addWidget(ok)
        cancel = QtWidgets.QPushButton('Cancel'); cancel.clicked.connect(self.reject); bh.addWidget(cancel)
        v.addWidget(btns)

    def get_result(self) -> dict:
        out = {}
        for name, cb in self._combos.items():
            val = cb.currentText()
            if val and val != '<none>':
                out[name] = val
        return out


class TimeRangeDialog(QtWidgets.QDialog):
    """Dialog to select a time range for filtering changing registers.
    
    Shows start and end time fields pre-filled with the full data range.
    User can adjust to a shorter range if desired.
    """
    def __init__(self, parent: QtWidgets.QWidget, time_min: float, time_max: float, time_col_name: str):
        super().__init__(parent)
        self.setWindowTitle('Select Time Range')
        self.setModal(True)
        
        v = QtWidgets.QVBoxLayout(self)
        
        # Info label
        info = QtWidgets.QLabel(f"Select time range from column '{time_col_name}' to check for changing registers:")
        info.setWordWrap(True)
        v.addWidget(info)
        
        # Form for start/end times
        form = QtWidgets.QWidget()
        fl = QtWidgets.QFormLayout(form)
        
        self.start_spin = QtWidgets.QDoubleSpinBox()
        self.start_spin.setRange(-1e15, 1e15)
        self.start_spin.setDecimals(6)
        self.start_spin.setValue(time_min)
        fl.addRow(QtWidgets.QLabel('Start time:'), self.start_spin)
        
        self.end_spin = QtWidgets.QDoubleSpinBox()
        self.end_spin.setRange(-1e15, 1e15)
        self.end_spin.setDecimals(6)
        self.end_spin.setValue(time_max)
        fl.addRow(QtWidgets.QLabel('End time:'), self.end_spin)
        
        v.addWidget(form)
        
        # Buttons
        btns = QtWidgets.QWidget()
        bh = QtWidgets.QHBoxLayout(btns)
        bh.addStretch()
        ok = QtWidgets.QPushButton('OK')
        ok.clicked.connect(self.accept)
        bh.addWidget(ok)
        cancel = QtWidgets.QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        bh.addWidget(cancel)
        v.addWidget(btns)
    
    def get_range(self):
        """Return (start_time, end_time) tuple."""
        return (float(self.start_spin.value()), float(self.end_spin.value()))


if __name__ == '__main__':
    import sys
    app=QtWidgets.QApplication(sys.argv)
    w=ExcelPlotter(); w.show(); sys.exit(app.exec_())
