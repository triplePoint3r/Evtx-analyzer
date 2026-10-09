"""
EVTX Forensics Tool - Main GUI Application
Complete forensics workflow: Copy → Convert → Analyze Timeline
"""

import ctypes
import sys
import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDateTime, QDate, QTime

import cpy_files
import evtx_converter
import timeline_analyzer


def require_admin():
    """Check and request admin privileges on Windows"""
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False
    
    if not is_admin:        
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            " ".join(f'"{a}"' for a in sys.argv),
            None, 1
        )
        sys.exit(0)


# ==================== Worker Threads ====================

class CopyFileWorker(QThread):
    """Thread for copying EVTX file"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        self.progress.emit(f"Copying {self.path.name}...")
        result = cpy_files.process_copy(self.path)
        self.finished.emit(result)


class ConvertFileWorker(QThread):
    """Thread for converting EVTX to XML"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        self.progress.emit(f"Converting {self.path.name} to XML...")
        result = evtx_converter.process_conversion(self.path)
        self.finished.emit(result)


class AnalyzeTimelineWorker(QThread):
    """Thread for timeline analysis"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)
    progress_count = pyqtSignal(int, int)

    def __init__(self, xml_files, output_name=None, filters=None):
        super().__init__()
        self.xml_files = xml_files
        self.output_name = output_name
        self.filters = filters

    def run(self):
        self.progress.emit("Analyzing timeline...")
        
        def progress_callback(total, matched):
            self.progress_count.emit(total, matched)
        
        result = timeline_analyzer.process_timeline_analysis(
            xml_files=self.xml_files,
            output_name=self.output_name,
            filters=self.filters,
            progress_callback=progress_callback
        )
        self.finished.emit(result)


# ==================== Main Window ====================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("EVTX Forensics Analyzer - Complete Workflow")
        self.setup_ui()
        self.current_worker = None

    def setup_ui(self):
        """Setup the user interface"""
        
        # Window size
        screen = QApplication.primaryScreen()
        size = screen.size()
        self.setMinimumWidth(size.width() // 2)
        self.setMinimumHeight(size.height() // 2)
        self.showMaximized()

        # ===== Toolbar =====
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet("QToolBar { spacing: 10px; padding: 5px; }")
        self.addToolBar(toolbar)

        # Actions
        self.copy_action = QAction("📁 Copy EVTX", self)
        self.copy_action.triggered.connect(self.select_file_to_copy)
        
        self.convert_action = QAction("🔄 Convert to XML", self)
        self.convert_action.triggered.connect(self.convert_evidence_files)
        
        self.analyze_action = QAction("📊 Analyze Timeline", self)
        self.analyze_action.triggered.connect(self.analyze_timeline)
        
        self.view_timeline_action = QAction("👁️ View Timelines", self)
        self.view_timeline_action.triggered.connect(self.view_timeline)
        
        toolbar.addAction(self.copy_action)
        toolbar.addSeparator()
        toolbar.addAction(self.convert_action)
        toolbar.addSeparator()
        toolbar.addAction(self.analyze_action)
        toolbar.addSeparator()
        toolbar.addAction(self.view_timeline_action)

        # ===== Main Layout =====
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # ===== Status Label =====
        self.status_label = QLabel("Ready - Select EVTX file to begin")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background-color: #e3f2fd;
                border-radius: 5px;
            }
        """)
        main_layout.addWidget(self.status_label)

        # ===== Tabs =====
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Operation Log
        self.log_tab = QTextEdit()
        self.log_tab.setReadOnly(True)
        self.log_tab.setStyleSheet("font-family: Consolas, monospace;")
        self.tabs.addTab(self.log_tab, "📝 Operation Log")

        # Tab 2: File Manager
        self.file_manager_tab = self.create_file_manager_tab()
        self.tabs.addTab(self.file_manager_tab, "📂 File Manager")

        # Tab 3: Timeline Filters
        self.filter_tab = self.create_filter_tab()
        self.tabs.addTab(self.filter_tab, "🔍 Timeline Filters")

        # Tab 4: Statistics
        self.stats_tab = QTextEdit()
        self.stats_tab.setReadOnly(True)
        self.stats_tab.setStyleSheet("font-family: Consolas, monospace;")
        self.tabs.addTab(self.stats_tab, "📊 Statistics")

        self.manual_audit_tab = self.create_manual_audit_tab()
        self.tabs.addTab(self.manual_audit_tab, "📊 Manual audit")

        # ===== Progress Bar =====
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

    def create_file_manager_tab(self):
        """Create file manager tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Evidence files section
        evidence_group = QGroupBox("Evidence Files (EVTX)")
        evidence_layout = QVBoxLayout(evidence_group)
        
        self.evidence_list = QListWidget()
        evidence_layout.addWidget(self.evidence_list)
        
        refresh_evidence_btn = QPushButton("🔄 Refresh List")
        refresh_evidence_btn.clicked.connect(self.refresh_evidence_list)
        evidence_layout.addWidget(refresh_evidence_btn)
        
        layout.addWidget(evidence_group)

        # XML files section
        xml_group = QGroupBox("XML Files (Converted)")
        xml_layout = QVBoxLayout(xml_group)
        
        self.xml_list = QListWidget()
        self.xml_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        xml_layout.addWidget(self.xml_list)
        
        refresh_xml_btn = QPushButton("🔄 Refresh List")
        refresh_xml_btn.clicked.connect(self.refresh_xml_list)
        xml_layout.addWidget(refresh_xml_btn)
        
        layout.addWidget(xml_group)

        # Refresh lists on load
        self.refresh_evidence_list()
        self.refresh_xml_list()

        return widget

    def create_filter_tab(self):
        """Create timeline filter configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Channel filter
        channel_group = QGroupBox("Filter by Channels")
        channel_layout = QVBoxLayout(channel_group)
        
        self.channel_security = QCheckBox("Security")
        self.channel_system = QCheckBox("System")
        self.channel_application = QCheckBox("Application")
        self.channel_sysmon = QCheckBox("Microsoft-Windows-Sysmon/Operational")
        
        channel_layout.addWidget(self.channel_security)
        channel_layout.addWidget(self.channel_system)
        channel_layout.addWidget(self.channel_application)
        channel_layout.addWidget(self.channel_sysmon)
        
        layout.addWidget(channel_group)

        # Event ID filter
        eid_group = QGroupBox("Filter by Event IDs (comma-separated)")
        eid_layout = QVBoxLayout(eid_group)
        
        self.event_ids_input = QLineEdit()
        self.event_ids_input.setPlaceholderText("e.g., 4624,4625,7045")
        eid_layout.addWidget(self.event_ids_input)
        
        layout.addWidget(eid_group)

        # Time range filter
        time_group = QGroupBox("Filter by Time Range")
        time_layout = QFormLayout(time_group)
        
        self.start_time_input = QLineEdit()
        self.start_time_input.setPlaceholderText("2024-01-15 00:00:00")
        time_layout.addRow("Start Time:", self.start_time_input)
        
        self.end_time_input = QLineEdit()
        self.end_time_input.setPlaceholderText("2024-01-16 00:00:00")
        time_layout.addRow("End Time:", self.end_time_input)
        
        layout.addWidget(time_group)

        # Clear filters button
        clear_btn = QPushButton("🗑️ Clear All Filters")
        clear_btn.clicked.connect(self.clear_filters)
        layout.addWidget(clear_btn)

        layout.addStretch()

        return widget

    def create_manual_audit_tab(self):
        """Create the Manual Audit tab with read-only table and filtering controls."""
        widget = QWidget()
        outer_layout = QVBoxLayout(widget)

        # ----- Filter Controls -----
        filter_group = QGroupBox("Search & Filter")
        filter_form = QFormLayout(filter_group)

        # Keyword search (searches all visible columns)
        self._audit_keyword = QLineEdit()
        self._audit_keyword.setPlaceholderText("Enter keyword to search across all fields…")
        filter_form.addRow("Keyword:", self._audit_keyword)

        # Event ID filter
        self._audit_event_id = QLineEdit()
        self._audit_event_id.setPlaceholderText("e.g. 4624,4625")
        filter_form.addRow("Event ID(s):", self._audit_event_id)

        # Source / Channel filter
        self._audit_source = QLineEdit()
        self._audit_source.setPlaceholderText("e.g. Security, System")
        filter_form.addRow("Source/Channel:", self._audit_source)

        # Provider filter — editable combo box, auto-populated when a CSV is loaded
        self._audit_provider = QComboBox()
        self._audit_provider.setEditable(True)
        self._audit_provider.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._audit_provider.lineEdit().setPlaceholderText("All providers (type to filter or pick from list)")
        filter_form.addRow("Provider:", self._audit_provider)

        # Date-time range — date/time pickers with optional enable checkbox
        start_dt_row = QHBoxLayout()
        self._audit_start_enabled = QCheckBox("Enable")
        self._audit_start_dt = QDateTimeEdit()
        self._audit_start_dt.setCalendarPopup(True)
        self._audit_start_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._audit_start_dt.setDateTime(QDateTime(QDate(2000, 1, 1), QTime(0, 0, 0)))
        self._audit_start_dt.setEnabled(False)
        self._audit_start_enabled.toggled.connect(self._audit_start_dt.setEnabled)
        start_dt_row.addWidget(self._audit_start_enabled)
        start_dt_row.addWidget(self._audit_start_dt)
        filter_form.addRow("Start Time:", start_dt_row)

        end_dt_row = QHBoxLayout()
        self._audit_end_enabled = QCheckBox("Enable")
        self._audit_end_dt = QDateTimeEdit()
        self._audit_end_dt.setCalendarPopup(True)
        self._audit_end_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._audit_end_dt.setDateTime(QDateTime.currentDateTime())
        self._audit_end_dt.setEnabled(False)
        self._audit_end_enabled.toggled.connect(self._audit_end_dt.setEnabled)
        end_dt_row.addWidget(self._audit_end_enabled)
        end_dt_row.addWidget(self._audit_end_dt)
        filter_form.addRow("End Time:", end_dt_row)

        outer_layout.addWidget(filter_group)

        # ----- Buttons -----
        btn_row = QHBoxLayout()

        load_btn = QPushButton("📂 Load Timeline CSV")
        load_btn.setToolTip("Open a timeline CSV file produced by the Analyze Timeline step")
        load_btn.clicked.connect(self._audit_load_csv)
        btn_row.addWidget(load_btn)

        apply_btn = QPushButton("🔍 Apply Filter")
        apply_btn.setToolTip("Apply the filter controls above to the loaded timeline")
        apply_btn.clicked.connect(self._audit_apply_filters)
        btn_row.addWidget(apply_btn)

        clear_filter_btn = QPushButton("🗑️ Clear Filters")
        clear_filter_btn.clicked.connect(self._audit_clear_filters)
        btn_row.addWidget(clear_filter_btn)

        btn_row.addStretch()

        self._audit_row_count_label = QLabel("No data loaded")
        btn_row.addWidget(self._audit_row_count_label)

        outer_layout.addLayout(btn_row)

        # ----- Read-only Table -----
        self._audit_table = QTableWidget()
        # Prevent any editing
        self._audit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._audit_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._audit_table.setAlternatingRowColors(True)
        self._audit_table.setSortingEnabled(True)
        self._audit_table.horizontalHeader().setStretchLastSection(True)
        self._audit_table.setStyleSheet(
            "QTableWidget { font-family: Consolas, monospace; font-size: 11px; }"
        )
        outer_layout.addWidget(self._audit_table)

        # Internal state: populated by _audit_load_csv
        self._audit_all_rows: list = []   # list of dicts keyed by header name
        self._audit_headers: list = []    # CSV header names in order

        return widget

    # ==================== Manual Audit Helpers ====================

    # Column name constants matching timeline_analyzer CSV output
    _AUDIT_COL_TIMESTAMP = "Timestamp"
    _AUDIT_COL_CHANNEL   = "Channel"
    _AUDIT_COL_EVENTID   = "EventID"
    _AUDIT_COL_LEVEL     = "Level"
    _AUDIT_COL_COMPUTER  = "Computer"
    _AUDIT_COL_PROVIDER  = "Provider"
    _AUDIT_COL_RECORDID  = "RecordID"
    _AUDIT_COL_USER      = "User"
    _AUDIT_COL_DESC      = "Description"

    def _audit_load_csv(self):
        """Prompt the user to select a timeline CSV and load it into the audit table."""
        import csv
        timeline_dir = str(Path(__file__).parent / "timelines")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Timeline CSV",
            timeline_dir,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, newline='', encoding='utf-8', errors='replace') as fh:
                reader = csv.DictReader(fh)
                headers = list(reader.fieldnames or [])
                rows = list(reader)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to read CSV:\n{exc}")
            return

        self._audit_headers = headers
        # Pre-compute a lower-cased searchable string for each row to speed up keyword filtering
        self._audit_all_rows = [
            {**{h: row.get(h, '') for h in headers}, '_search': ' '.join(row.get(h, '') for h in headers).lower()}
            for row in rows
        ]

        # Populate provider combo box with unique values from the loaded data
        providers = sorted({
            row.get(self._AUDIT_COL_PROVIDER, '').strip()
            for row in self._audit_all_rows
            if row.get(self._AUDIT_COL_PROVIDER, '').strip()
        })
        self._audit_provider.blockSignals(True)
        self._audit_provider.clear()
        self._audit_provider.addItem("")  # blank = show all
        for p in providers:
            self._audit_provider.addItem(p)
        self._audit_provider.setCurrentIndex(0)
        self._audit_provider.blockSignals(False)

        self.log(
            f"📂 Audit: loaded {len(self._audit_all_rows):,} events "
            f"from {Path(file_path).name}"
        )
        self._audit_populate_table(self._audit_all_rows)

    def _audit_apply_filters(self):
        """Filter the loaded rows using the control values and refresh the table."""
        if not self._audit_all_rows:
            QMessageBox.information(self, "No Data", "Please load a timeline CSV first.")
            return

        keyword       = self._audit_keyword.text().strip().lower()
        event_ids     = {e.strip() for e in self._audit_event_id.text().split(',') if e.strip()}
        source_text   = self._audit_source.text().strip().lower()
        provider_text = self._audit_provider.currentText().strip().lower()

        # Read optional datetime boundaries from the date/time pickers
        start_dt = end_dt = None
        if self._audit_start_enabled.isChecked():
            start_dt = self._audit_start_dt.dateTime().toPyDateTime()
        if self._audit_end_enabled.isChecked():
            end_dt = self._audit_end_dt.dateTime().toPyDateTime()

        filtered = []
        for row in self._audit_all_rows:
            ts_str  = row.get(self._AUDIT_COL_TIMESTAMP, '')
            channel = row.get(self._AUDIT_COL_CHANNEL, '')
            eid     = row.get(self._AUDIT_COL_EVENTID, '').strip()
            prov    = row.get(self._AUDIT_COL_PROVIDER, '')

            # Event ID filter
            if event_ids and eid not in event_ids:
                continue

            # Source / Channel filter (case-insensitive substring)
            if source_text and source_text not in channel.lower():
                continue

            # Provider filter (case-insensitive substring)
            if provider_text and provider_text not in prov.lower():
                continue

            # Date-time range filter
            if start_dt or end_dt:
                try:
                    row_dt = datetime.fromisoformat(ts_str)
                    if start_dt and row_dt < start_dt:
                        continue
                    if end_dt and row_dt > end_dt:
                        continue
                except ValueError:
                    pass  # keep row if timestamp cannot be parsed

            # Keyword filter — uses pre-computed searchable text
            if keyword and keyword not in row['_search']:
                continue

            filtered.append(row)

        self._audit_populate_table(filtered)
        self.log(
            f"🔍 Audit filter: {len(filtered):,} of "
            f"{len(self._audit_all_rows):,} events match"
        )

    def _audit_clear_filters(self):
        """Reset all filter fields and show the full dataset."""
        self._audit_keyword.clear()
        self._audit_event_id.clear()
        self._audit_source.clear()
        self._audit_provider.setCurrentIndex(0)
        self._audit_start_enabled.setChecked(False)
        self._audit_start_dt.setDateTime(QDateTime(QDate(2000, 1, 1), QTime(0, 0, 0)))
        self._audit_end_enabled.setChecked(False)
        self._audit_end_dt.setDateTime(QDateTime.currentDateTime())
        if self._audit_all_rows:
            self._audit_populate_table(self._audit_all_rows)

    def _audit_populate_table(self, rows: list):
        """Populate the audit QTableWidget with *rows* (list of dicts keyed by header name)."""
        headers = self._audit_headers

        # Disable sorting while inserting rows for performance
        self._audit_table.setSortingEnabled(False)
        self._audit_table.clearContents()
        self._audit_table.setRowCount(0)
        self._audit_table.setColumnCount(len(headers))
        self._audit_table.setHorizontalHeaderLabels(headers)

        self._audit_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, header in enumerate(headers):
                cell_text = row.get(header, '')
                item = QTableWidgetItem(cell_text)
                # Make every cell individually read-only
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._audit_table.setItem(row_idx, col_idx, item)

        # Resize columns to fit content
        self._audit_table.resizeColumnsToContents()
        self._audit_table.setSortingEnabled(True)

        self._audit_row_count_label.setText(f"Showing {len(rows):,} event(s)")


    # ==================== Refresh Lists ====================

    def refresh_evidence_list(self):
        """Refresh evidence files list"""
        self.evidence_list.clear()
        files = cpy_files.get_all_evidence_files()
        for file in files:
            self.evidence_list.addItem(file.name)
        self.log(f"📁 Found {len(files)} evidence file(s)")

    def refresh_xml_list(self):
        """Refresh XML files list"""
        self.xml_list.clear()
        files = cpy_files.get_all_xml_files()
        for file in files:
            item = QListWidgetItem(file.name)
            item.setData(Qt.ItemDataRole.UserRole, str(file))
            self.xml_list.addItem(item)
        self.log(f"📄 Found {len(files)} XML file(s)")

    # ==================== Operations ====================

    def select_file_to_copy(self):
        """Select and copy EVTX file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select EVTX File",
            "",
            "EVTX Files (*.evtx);;All Files (*.*)"
        )

        if file_path:
            self.run_copy(Path(file_path))

    def run_copy(self, path):
        """Run copy operation"""
        self.disable_actions()
        self.log(f"📁 Copying: {path.name}")
        self.status_label.setText(f"Copying: {path.name}")
        
        self.current_worker = CopyFileWorker(path)
        self.current_worker.progress.connect(self.log)
        self.current_worker.finished.connect(self.on_copy_finished)
        self.current_worker.start()

    def on_copy_finished(self, result):
        """Handle copy completion"""
        self.enable_actions()
        
        if result:
            self.log("✅ Copy successful!")
            self.log(json.dumps(result, indent=2))
            self.status_label.setText("✅ Copy completed successfully")
            self.refresh_evidence_list()
        else:
            self.log("❌ Copy failed!")
            self.status_label.setText("❌ Copy failed")

    def convert_evidence_files(self):
        """Convert all evidence files to XML"""
        files = cpy_files.get_all_evidence_files()
        
        if not files:
            QMessageBox.warning(self, "No Files", "No evidence files found to convert!")
            return
        
        reply = QMessageBox.question(
            self,
            "Convert Files",
            f"Convert {len(files)} evidence file(s) to XML?\n\nThis may take some time.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.run_conversion(files)

    def run_conversion(self, files):
        """Run conversion for multiple files"""
        self.disable_actions()
        self.log(f"🔄 Converting {len(files)} file(s) to XML...")
        self.status_label.setText("Converting to XML...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(files))
        self.progress_bar.setValue(0)
        
        self.convert_queue = list(files)
        self.convert_next()

    def convert_next(self):
        """Convert next file in queue"""
        if not self.convert_queue:
            self.on_all_conversions_complete()
            return
        
        next_file = self.convert_queue.pop(0)
        remaining = len(self.convert_queue)
        
        self.log(f"🔄 Converting: {next_file.name} ({remaining} remaining)")
        
        self.current_worker = ConvertFileWorker(next_file)
        self.current_worker.progress.connect(self.log)
        self.current_worker.finished.connect(self.on_single_conversion_finished)
        self.current_worker.start()

    def on_single_conversion_finished(self, result):
        """Handle single conversion completion"""
        if result:
            self.log(f"✅ Converted: {Path(result['xml_path']).name}")
        else:
            self.log("❌ Conversion failed")
        
        self.progress_bar.setValue(self.progress_bar.value() + 1)
        self.convert_next()

    def on_all_conversions_complete(self):
        """Handle all conversions complete"""
        self.enable_actions()
        self.progress_bar.setVisible(False)
        self.log("✅ All conversions complete!")
        self.status_label.setText("✅ Conversions completed")
        self.refresh_xml_list()
        
        QMessageBox.information(self, "Complete", "All files converted successfully!")

    def analyze_timeline(self):
        """Analyze timeline from selected XML files"""
        selected_items = self.xml_list.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(
                self, 
                "No Selection", 
                "Please select at least one XML file from the File Manager tab!"
            )
            return
        
        # Get file paths
        xml_files = [Path(item.data(Qt.ItemDataRole.UserRole)) for item in selected_items]
        
        # Get filters
        filters = self.get_filters()
        
        # Confirm
        filter_desc = "No filters" if not filters else f"Filters: {len(filters)} active"
        reply = QMessageBox.question(
            self,
            "Analyze Timeline",
            f"Analyze {len(xml_files)} XML file(s)?\n{filter_desc}\n\nThis may take some time.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.run_timeline_analysis(xml_files, filters)

    def run_timeline_analysis(self, xml_files, filters):
        """Run timeline analysis"""
        self.disable_actions()
        self.log(f"📊 Analyzing timeline from {len(xml_files)} file(s)...")
        self.status_label.setText("Analyzing timeline...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)  # Indeterminate
        
        self.current_worker = AnalyzeTimelineWorker(xml_files, filters=filters)
        self.current_worker.progress.connect(self.log)
        self.current_worker.progress_count.connect(self.on_analysis_progress)
        self.current_worker.finished.connect(self.on_analysis_finished)
        self.current_worker.start()

    def on_analysis_progress(self, total, matched):
        """Update analysis progress"""
        self.log(f"⏳ Processed: {total:,} events | Matched: {matched:,}")

    def on_analysis_finished(self, result):
        """Handle analysis completion"""
        self.enable_actions()
        self.progress_bar.setVisible(False)
        
        if result:
            self.log("✅ Timeline analysis complete!")
            self.log(f"📄 Timeline saved to: {result['timeline_path']}")
            
            # Display statistics
            stats = result['stats']
            stats_text = f"""
=== Timeline Statistics ===

Total Events: {stats['total_events']:,}
Matched Events: {stats['matched_events']:,}

Channels Distribution:
"""
            for channel, count in stats['channels'].items():
                stats_text += f"  {channel}: {count:,}\n"
            
            stats_text += "\nTop Event IDs:\n"
            for eid, count in list(stats['event_ids'].items())[:10]:
                stats_text += f"  Event ID {eid}: {count:,}\n"
            
            self.stats_tab.setText(stats_text)
            self.tabs.setCurrentWidget(self.stats_tab)
            
            self.status_label.setText("✅ Timeline analysis completed")
            
            QMessageBox.information(
                self, 
                "Complete", 
                f"Timeline analysis complete!\n\nFile: {Path(result['timeline_path']).name}"
            )
        else:
            self.log("❌ Timeline analysis failed")
            self.status_label.setText("❌ Analysis failed")

    def view_timeline(self):
        """Open timeline directory"""
        timeline_dir = Path(__file__).parent / "timelines"
        if timeline_dir.exists():
            import subprocess
            try:
                subprocess.Popen(f'explorer "{str(timeline_dir)}"')
            except:
                QMessageBox.information(self, "Info", f"Timeline directory:\n{timeline_dir}")
        else:
            QMessageBox.information(self, "Info", "No timelines created yet!")

    # ==================== Filters ====================

    def get_filters(self):
        """Get current filter settings"""
        filters = {}
        
        # Channels
        channels = []
        if self.channel_security.isChecked():
            channels.append("Security")
        if self.channel_system.isChecked():
            channels.append("System")
        if self.channel_application.isChecked():
            channels.append("Application")
        if self.channel_sysmon.isChecked():
            channels.append("Microsoft-Windows-Sysmon/Operational")
        
        if channels:
            filters['channels'] = channels
        
        # Event IDs
        event_ids_text = self.event_ids_input.text().strip()
        if event_ids_text:
            event_ids = [eid.strip() for eid in event_ids_text.split(',') if eid.strip()]
            if event_ids:
                filters['event_ids'] = event_ids
        
        # Time range
        start_time = self.start_time_input.text().strip()
        if start_time:
            filters['start_time'] = start_time
        
        end_time = self.end_time_input.text().strip()
        if end_time:
            filters['end_time'] = end_time
        
        return filters if filters else None

    def clear_filters(self):
        """Clear all filters"""
        self.channel_security.setChecked(False)
        self.channel_system.setChecked(False)
        self.channel_application.setChecked(False)
        self.channel_sysmon.setChecked(False)
        self.event_ids_input.clear()
        self.start_time_input.clear()
        self.end_time_input.clear()
        self.log("🗑️ Filters cleared")

    # ==================== UI Helpers ====================

    def log(self, message):
        """Add message to log"""
        self.log_tab.append(message)

    def disable_actions(self):
        """Disable all actions during operation"""
        self.copy_action.setEnabled(False)
        self.convert_action.setEnabled(False)
        self.analyze_action.setEnabled(False)

    def enable_actions(self):
        """Enable all actions"""
        self.copy_action.setEnabled(True)
        self.convert_action.setEnabled(True)
        self.analyze_action.setEnabled(True)


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    require_admin()
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
