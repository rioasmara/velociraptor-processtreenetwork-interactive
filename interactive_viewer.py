import sys
import json
import glob
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView, QLineEdit, QLabel,
    QHBoxLayout, QComboBox, QPushButton, QTabWidget, QTextEdit,
    QSplitter, QTreeWidget, QTreeWidgetItem, QGroupBox, QFrame,
    QScrollArea, QGridLayout, QListWidget, QListWidgetItem, QMessageBox,
    QTreeWidgetItemIterator, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QPalette, QIcon, QBrush, QCursor
from collections import defaultdict

# Try to import charts
try:
    from PyQt6.QtCharts import (
        QChart, QChartView, QPieSeries, QBarSeries, QBarSet,
        QBarCategoryAxis, QValueAxis
    )
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False


class DataSignals(QObject):
    """Signals for cross-tab communication"""
    process_selected = pyqtSignal(str)  # PID
    connection_selected = pyqtSignal(dict)  # Connection data
    filter_by_process = pyqtSignal(str)  # Process name
    filter_by_user = pyqtSignal(str)  # Username
    highlight_external = pyqtSignal()
    highlight_untrusted = pyqtSignal()


class ClickableMetricCard(QFrame):
    """Interactive metric card that can be clicked"""
    def __init__(self, title, value, subtitle="", color="#3498db", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.color = color

        self.setStyleSheet(f"""
            ClickableMetricCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {color}, stop:1 {self.darken_color(color)});
                border-radius: 10px;
                border: 2px solid {self.darken_color(color, 0.3)};
                padding: 15px;
            }}
            ClickableMetricCard:hover {{
                border: 3px solid white;
            }}
        """)

        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        layout.addWidget(title_label)

        # Value
        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        layout.addWidget(self.value_label)

        # Subtitle
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 11px;")
            layout.addWidget(subtitle_label)

        # Click hint
        hint_label = QLabel("🖱️ Click to filter")
        hint_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 9px; font-style: italic;")
        layout.addWidget(hint_label)

        layout.addStretch()

    def darken_color(self, color, factor=0.2):
        """Darken a hex color"""
        color = color.lstrip('#')
        r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        return f'#{r:02x}{g:02x}{b:02x}'

    def update_value(self, value):
        """Update the card's value"""
        self.value_label.setText(str(value))


class ClickableConnectionCard(QFrame):
    """Clickable connection card"""
    clicked = pyqtSignal(dict)

    def __init__(self, connection_data, process_info, parent=None):
        super().__init__(parent)
        self.connection_data = connection_data
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.setStyleSheet("""
            ClickableConnectionCard {
                background-color: white;
                border-radius: 8px;
                border: 2px solid #ddd;
                padding: 10px;
            }
            ClickableConnectionCard:hover {
                border: 3px solid #3498db;
                background-color: #e8f4f8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # Header
        header_layout = QHBoxLayout()
        proc_name = QLabel(f"🔷 {connection_data.get('Name', 'Unknown')}")
        proc_name.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        header_layout.addWidget(proc_name)

        # Status badge
        status = connection_data.get('Status', '')
        status_badge = QLabel(status)
        if status == 'ESTAB':
            status_badge.setStyleSheet("""
                background-color: #27ae60; color: white;
                padding: 3px 8px; border-radius: 10px; font-size: 10px;
            """)
        elif status == 'LISTEN':
            status_badge.setStyleSheet("""
                background-color: #3498db; color: white;
                padding: 3px 8px; border-radius: 10px; font-size: 10px;
            """)
        header_layout.addWidget(status_badge)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Connection info
        conn_type = connection_data.get('Type', 'N/A')
        local = f"{connection_data.get('Laddr', '')}:{connection_data.get('Lport', '')}"
        remote = f"{connection_data.get('Raddr', '')}:{connection_data.get('Rport', '')}"

        info_label = QLabel(f"<b>{conn_type}</b> | {local} → {remote}")
        info_label.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(info_label)

        # User
        username = process_info.get('Username', connection_data.get('Username', ''))
        if username:
            user_label = QLabel(f"👤 {username}")
            user_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
            layout.addWidget(user_label)

        # PID
        pid_label = QLabel(f"PID: {connection_data.get('Pid', 'N/A')}")
        pid_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        layout.addWidget(pid_label)

        # Click hint
        hint = QLabel("🖱️ Click for details")
        hint.setStyleSheet("color: #bdc3c7; font-size: 9px; font-style: italic;")
        layout.addWidget(hint)

        self.setMaximumHeight(140)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.connection_data)
        super().mousePressEvent(event)


class InteractiveNetworkViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.network_data = []
        self.process_data = []
        self.process_map = {}
        self.filtered_data = []

        # Create signals object for cross-tab communication
        self.signals = DataSignals()

        # Connect signals
        self.signals.process_selected.connect(self.on_process_selected)
        self.signals.connection_selected.connect(self.on_connection_selected)
        self.signals.filter_by_process.connect(self.on_filter_by_process)
        self.signals.filter_by_user.connect(self.on_filter_by_user)
        self.signals.highlight_external.connect(self.on_highlight_external)
        self.signals.highlight_untrusted.connect(self.on_highlight_untrusted)

        self.initUI()
        self.load_data()
        self.apply_theme()

        # Status bar for showing context
        self.statusBar().showMessage("Ready | Click on any metric, process, or connection to navigate")

    def initUI(self):
        self.setWindowTitle('🔗 Interactive Network & Process Intelligence')
        self.setGeometry(50, 50, 1900, 1000)

        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add breadcrumb navigation
        self.breadcrumb = QLabel("📍 Dashboard")
        self.breadcrumb.setStyleSheet("""
            background-color: #34495e;
            color: white;
            padding: 10px;
            font-size: 13px;
            font-weight: bold;
        """)
        layout.addWidget(self.breadcrumb)

        # Create tabs
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: #f5f6fa;
            }
            QTabBar::tab {
                background-color: #ecf0f1;
                padding: 10px 20px;
                margin: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #3498db;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #5dade2;
                color: white;
            }
        """)

        layout.addWidget(self.tabs)

        # Create tabs
        self.create_dashboard_tab()
        self.create_network_grid_tab()
        self.create_process_intel_tab()
        self.create_security_tab()
        self.create_interactive_tree_tab()
        self.create_timeline_view_tab()
        self.create_advanced_table_tab()

    def apply_theme(self):
        """Apply modern theme"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
            QLabel {
                color: #2c3e50;
            }
            QLineEdit {
                padding: 8px;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QComboBox {
                padding: 5px;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f8f9fa;
                gridline-color: #ecf0f1;
                border: none;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QTreeWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            QTreeWidget::item:hover {
                background-color: #e8f4f8;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QStatusBar {
                background-color: #ecf0f1;
                color: #2c3e50;
                font-weight: bold;
            }
        """)

    def create_dashboard_tab(self):
        """Executive dashboard"""
        dashboard = QWidget()
        layout = QVBoxLayout(dashboard)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Title
        title = QLabel("📊 Network Security Dashboard")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(title)

        # Metric cards
        self.metrics_layout = QGridLayout()
        self.metrics_layout.setSpacing(15)
        layout.addLayout(self.metrics_layout)

        # Charts
        if CHARTS_AVAILABLE:
            charts_container = QWidget()
            charts_layout = QHBoxLayout(charts_container)

            self.dashboard_chart1 = QChartView()
            self.dashboard_chart1.setRenderHint(QChartView.RenderHint.Antialiasing)
            charts_layout.addWidget(self.dashboard_chart1)

            self.dashboard_chart2 = QChartView()
            self.dashboard_chart2.setRenderHint(QChartView.RenderHint.Antialiasing)
            charts_layout.addWidget(self.dashboard_chart2)

            layout.addWidget(charts_container)

        # Activity feed
        activity_group = QGroupBox("🔔 Recent Network Activity")
        activity_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
        """)
        activity_layout = QVBoxLayout(activity_group)

        self.activity_list = QListWidget()
        self.activity_list.setStyleSheet("border: none;")
        self.activity_list.itemDoubleClicked.connect(self.on_activity_clicked)
        activity_layout.addWidget(self.activity_list)

        layout.addWidget(activity_group)
        layout.addStretch()

        self.tabs.addTab(dashboard, "📊 Dashboard")

    def create_network_grid_tab(self):
        """Card-based grid view"""
        grid_tab = QWidget()
        layout = QVBoxLayout(grid_tab)
        layout.setContentsMargins(15, 15, 15, 15)

        # Filters
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: white; border-radius: 8px; padding: 10px;")
        filter_layout = QHBoxLayout(filter_frame)

        filter_layout.addWidget(QLabel("🔍"))
        self.grid_search = QLineEdit()
        self.grid_search.setPlaceholderText("Search connections...")
        self.grid_search.textChanged.connect(self.update_network_grid)
        filter_layout.addWidget(self.grid_search)

        filter_layout.addWidget(QLabel("Protocol:"))
        self.grid_protocol = QComboBox()
        self.grid_protocol.addItems(['All', 'TCP', 'UDP'])
        self.grid_protocol.currentTextChanged.connect(self.update_network_grid)
        filter_layout.addWidget(self.grid_protocol)

        filter_layout.addWidget(QLabel("Status:"))
        self.grid_status = QComboBox()
        self.grid_status.addItem('All')
        self.grid_status.currentTextChanged.connect(self.update_network_grid)
        filter_layout.addWidget(self.grid_status)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_grid_filters)
        filter_layout.addWidget(clear_btn)

        layout.addWidget(filter_frame)

        # Count
        self.grid_count_label = QLabel("Showing 0 connections")
        self.grid_count_label.setStyleSheet("font-weight: bold; margin: 5px;")
        layout.addWidget(self.grid_count_label)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: transparent;")

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)

        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll)

        self.tabs.addTab(grid_tab, "🎯 Network Grid")

    def create_process_intel_tab(self):
        """Process intelligence"""
        intel_tab = QWidget()
        layout = QVBoxLayout(intel_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Compact header with buttons
        header_layout = QHBoxLayout()
        header = QLabel("🧠 Process Intelligence & Hierarchy")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Splitter - this will expand to fill available space
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(3)

        # Tree
        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(3)

        tree_label = QLabel("📁 Process Tree (Double-click to navigate)")
        tree_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-bottom: 2px;")
        tree_layout.addWidget(tree_label)

        self.intel_tree = QTreeWidget()
        self.intel_tree.setHeaderLabels(['Process', 'PID', 'User', 'Connections', 'Start Time'])
        self.intel_tree.setColumnWidth(0, 350)
        self.intel_tree.setColumnWidth(1, 80)
        self.intel_tree.setColumnWidth(2, 200)
        self.intel_tree.setColumnWidth(3, 100)
        self.intel_tree.setMinimumWidth(600)
        self.intel_tree.setMinimumHeight(500)  # Set minimum height
        self.intel_tree.itemClicked.connect(self.on_intel_tree_clicked)
        self.intel_tree.itemDoubleClicked.connect(self.on_intel_tree_double_clicked)
        tree_layout.addWidget(self.intel_tree, 1)  # Stretch factor of 1

        splitter.addWidget(tree_container)

        # Details
        details_container = QWidget()
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(3)

        details_header_layout = QHBoxLayout()
        details_label = QLabel("📋 Process Details")
        details_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-bottom: 2px;")
        details_header_layout.addWidget(details_label)
        details_header_layout.addStretch()

        # Add action buttons to header
        filter_proc_btn = QPushButton("🔍 Filter")
        filter_proc_btn.setMaximumWidth(80)
        filter_proc_btn.clicked.connect(self.filter_by_selected_process)
        details_header_layout.addWidget(filter_proc_btn)

        goto_tree_btn = QPushButton("🌳 Tree")
        goto_tree_btn.setMaximumWidth(70)
        goto_tree_btn.clicked.connect(self.filter_by_selected_process)
        details_header_layout.addWidget(goto_tree_btn)

        goto_table_btn = QPushButton("📋 Table")
        goto_table_btn.setMaximumWidth(70)
        goto_table_btn.clicked.connect(self.filter_by_selected_process)
        details_header_layout.addWidget(goto_table_btn)

        details_layout.addLayout(details_header_layout)

        self.intel_details = QTextEdit()
        self.intel_details.setReadOnly(True)
        self.intel_details.setMinimumWidth(500)
        self.intel_details.setMinimumHeight(500)  # Set minimum height
        self.intel_details.setStyleSheet("""
            background-color: #2c3e50;
            color: #ecf0f1;
            font-family: 'Courier New';
            font-size: 11px;
            border-radius: 5px;
            padding: 10px;
        """)
        details_layout.addWidget(self.intel_details, 1)  # Stretch factor of 1

        splitter.addWidget(details_container)

        # Set proportions: 55% tree, 45% details
        splitter.setSizes([1100, 900])
        splitter.setStretchFactor(0, 55)
        splitter.setStretchFactor(1, 45)

        # Add splitter with stretch to fill vertical space
        layout.addWidget(splitter, 1)

        self.tabs.addTab(intel_tab, "🧠 Process Intel")

    def create_security_tab(self):
        """Security analysis"""
        security_tab = QWidget()
        layout = QVBoxLayout(security_tab)
        layout.setContentsMargins(15, 15, 15, 15)

        header = QLabel("🛡️ Security Analysis & Threat Detection")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #e74c3c; margin-bottom: 10px;")
        layout.addWidget(header)

        # Metrics
        self.security_metrics_layout = QHBoxLayout()
        layout.addLayout(self.security_metrics_layout)

        # Threat list
        threat_group = QGroupBox("⚠️ Potential Security Indicators (Click items for details)")
        threat_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e74c3c;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fff5f5;
            }
        """)
        threat_layout = QVBoxLayout(threat_group)

        self.threat_list = QListWidget()
        self.threat_list.itemDoubleClicked.connect(self.on_threat_clicked)
        threat_layout.addWidget(self.threat_list)

        layout.addWidget(threat_group)

        # External connections
        external_group = QGroupBox("🌐 External Connections (Double-click for details)")
        external_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f39c12;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fffbf0;
            }
        """)
        external_layout = QVBoxLayout(external_group)

        self.external_table = QTableWidget()
        self.external_table.setColumnCount(6)
        self.external_table.setHorizontalHeaderLabels([
            'Process', 'PID', 'Remote IP', 'Remote Port', 'Protocol', 'User'
        ])
        self.external_table.cellDoubleClicked.connect(self.on_external_table_clicked)
        external_layout.addWidget(self.external_table)

        layout.addWidget(external_group)

        self.tabs.addTab(security_tab, "🛡️ Security")

    def create_interactive_tree_tab(self):
        """Interactive process tree"""
        tree_tab = QWidget()
        layout = QVBoxLayout(tree_tab)
        layout.setContentsMargins(15, 15, 15, 15)

        header = QLabel("🌳 Interactive Process Tree")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #27ae60; margin-bottom: 10px;")
        layout.addWidget(header)

        # Controls
        controls = QHBoxLayout()

        controls.addWidget(QLabel("🔍"))
        self.tree_search = QLineEdit()
        self.tree_search.setPlaceholderText("Search process...")
        self.tree_search.textChanged.connect(self.filter_tree)
        controls.addWidget(self.tree_search)

        expand_btn = QPushButton("Expand All")
        expand_btn.clicked.connect(lambda: self.process_tree.expandAll())
        controls.addWidget(expand_btn)

        collapse_btn = QPushButton("Collapse All")
        collapse_btn.clicked.connect(lambda: self.process_tree.collapseAll())
        controls.addWidget(collapse_btn)

        controls.addStretch()
        layout.addLayout(controls)

        # Legend
        legend = QHBoxLayout()
        legend.addWidget(QLabel("Legend:"))
        legend.addWidget(QLabel("■ Network Activity"))
        legend.addWidget(QLabel("✓ Trusted"))
        legend.addWidget(QLabel("✗ Untrusted"))
        legend.addStretch()
        layout.addLayout(legend)

        # Tree
        self.process_tree = QTreeWidget()
        self.process_tree.setHeaderLabels([
            'Process (PID)', 'Username', 'Connections', 'Start Time', 'Status'
        ])
        self.process_tree.setColumnWidth(0, 400)
        self.process_tree.setAlternatingRowColors(True)
        self.process_tree.itemDoubleClicked.connect(self.on_tree_double_clicked)
        layout.addWidget(self.process_tree)

        self.tabs.addTab(tree_tab, "🌳 Process Tree")

    def create_timeline_view_tab(self):
        """Timeline view"""
        timeline_tab = QWidget()
        layout = QVBoxLayout(timeline_tab)
        layout.setContentsMargins(15, 15, 15, 15)

        header = QLabel("⏱️ Process & Network Timeline")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #9b59b6; margin-bottom: 10px;")
        layout.addWidget(header)

        self.timeline_table = QTableWidget()
        self.timeline_table.setColumnCount(9)
        self.timeline_table.setHorizontalHeaderLabels([
            'Time', 'Event', 'Process', 'PID', 'User',
            'Network Conns', 'Listening', 'Established', 'Call Chain'
        ])
        self.timeline_table.setAlternatingRowColors(True)
        self.timeline_table.setSortingEnabled(True)
        self.timeline_table.cellDoubleClicked.connect(self.on_timeline_clicked)

        header = self.timeline_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        layout.addWidget(self.timeline_table)

        self.tabs.addTab(timeline_tab, "⏱️ Timeline")

    def create_advanced_table_tab(self):
        """Advanced table view"""
        table_tab = QWidget()
        layout = QVBoxLayout(table_tab)
        layout.setContentsMargins(15, 15, 15, 15)

        header = QLabel("📋 Advanced Connection Table")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #34495e; margin-bottom: 10px;")
        layout.addWidget(header)

        # Filters
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: white; border-radius: 8px; padding: 10px;")
        filter_layout = QHBoxLayout(filter_frame)

        filter_layout.addWidget(QLabel("🔍"))
        self.table_search = QLineEdit()
        self.table_search.setPlaceholderText("Search...")
        self.table_search.textChanged.connect(self.apply_table_filters)
        filter_layout.addWidget(self.table_search, 3)

        self.table_protocol = QComboBox()
        self.table_protocol.addItems(['All Protocols', 'TCP', 'UDP'])
        self.table_protocol.currentTextChanged.connect(self.apply_table_filters)
        filter_layout.addWidget(self.table_protocol)

        self.table_status = QComboBox()
        self.table_status.addItem('All Status')
        self.table_status.currentTextChanged.connect(self.apply_table_filters)
        filter_layout.addWidget(self.table_status)

        self.table_user = QComboBox()
        self.table_user.addItem('All Users')
        self.table_user.currentTextChanged.connect(self.apply_table_filters)
        filter_layout.addWidget(self.table_user)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_table_filters)
        filter_layout.addWidget(clear_btn)

        layout.addWidget(filter_frame)

        # Count
        self.table_count = QLabel("Results: 0")
        self.table_count.setStyleSheet("font-weight: bold; margin: 5px;")
        layout.addWidget(self.table_count)

        # Table
        self.advanced_table = QTableWidget()
        self.advanced_table.setColumnCount(15)
        self.advanced_table.setHorizontalHeaderLabels([
            'PID', 'Process', 'Protocol', 'Status', 'Local Addr', 'L.Port',
            'Remote Addr', 'R.Port', 'Username', 'Start Time', 'Uptime',
            'Parent Chain', 'Trusted', 'Conn.Time', 'PPID'
        ])

        self.advanced_table.setAlternatingRowColors(True)
        self.advanced_table.setSortingEnabled(True)
        self.advanced_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.advanced_table.cellDoubleClicked.connect(self.on_table_double_clicked)

        header = self.advanced_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        layout.addWidget(self.advanced_table)

        self.tabs.addTab(table_tab, "📋 Table View")

    def load_data(self):
        """Load data from all JSON files in the directory and auto-detect their type."""
        self.network_data = []
        self.process_data = []
        self.process_map = {}

        # Use glob to find all .json files in the current directory
        json_files = glob.glob('*.json')

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Read the first line to detect file type
                    first_line = f.readline()
                    if not first_line.strip():
                        continue
                    
                    try:
                        first_obj = json.loads(first_line)
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode first line of {file_path}. Skipping.")
                        continue

                    if not isinstance(first_obj, dict):
                        print(f"Warning: First line of {file_path} is not a JSON object. Skipping.")
                        continue

                    # Rewind to process the whole file
                    f.seek(0)

                    # Detect file type based on keys in the first object
                    if 'Laddr' in first_obj and 'Raddr' in first_obj:  # Likely network data
                        print(f"Processing {file_path} as network data...")
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    obj = json.loads(line)
                                    if isinstance(obj, dict):
                                        self.network_data.append(obj)
                                except json.JSONDecodeError:
                                    continue
                    elif 'Ppid' in first_obj and 'CommandLine' in first_obj:  # Likely process data
                        print(f"Processing {file_path} as process data...")
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    obj = json.loads(line)
                                    if isinstance(obj, dict):
                                        self.process_data.append(obj)
                                        self.process_map[str(obj.get('Pid', ''))] = obj
                                except json.JSONDecodeError:
                                    continue
                    else:
                        print(f"Warning: Could not determine data type for {file_path}. Skipping.")

            except Exception as e:
                QMessageBox.warning(self, "File Load Error", f"Error processing file {file_path}:\n{e}")

        # Brute-force removal of any None or non-dictionary values that might have slipped through
        self.network_data = [item for item in self.network_data if isinstance(item, dict)]
        self.process_data = [item for item in self.process_data if isinstance(item, dict)]

        try:
            self.filtered_data = self.network_data.copy()

            # Populate filters
            if self.network_data:
                statuses = sorted(set(item.get('Status', '') for item in self.network_data if item.get('Status')))
                self.grid_status.addItems(statuses)
                self.table_status.addItems(statuses)

            if self.process_data:
                users = sorted(set(p.get('Username', '') for p in self.process_data if p.get('Username')))
                self.table_user.addItems(users)

            # Populate all views
            self.populate_dashboard()
            self.populate_network_grid()
            self.populate_process_intel()
            self.populate_security_analysis()
            self.populate_process_tree()
            self.populate_timeline()
            self.populate_advanced_table()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to populate views with loaded data: {e}")

    def populate_dashboard(self):
        """Populate dashboard"""
        # Clear existing
        for i in reversed(range(self.metrics_layout.count())):
            self.metrics_layout.itemAt(i).widget().setParent(None)

        # Calculate metrics
        total_conns = len(self.network_data)
        total_procs = len(self.process_data)
        tcp_count = sum(1 for n in self.network_data if n.get('Type') == 'TCP')
        udp_count = sum(1 for n in self.network_data if n.get('Type') == 'UDP')
        listening = sum(1 for n in self.network_data if n.get('Status') == 'LISTEN')
        established = sum(1 for n in self.network_data if n.get('Status') == 'ESTAB')

        external = sum(1 for n in self.network_data
                      if n.get('Status') == 'ESTAB' and n.get('Raddr', '').strip()
                      and not n.get('Raddr', '').startswith('127.')
                      and not n.get('Raddr', '').startswith('::1'))

        procs_with_net = len(set(str(n.get('Pid')) for n in self.network_data))

        # Create clickable metric cards
        class CardWithAction(ClickableMetricCard):
            def __init__(self, title, value, subtitle, color, action, parent=None):
                super().__init__(title, value, subtitle, color, parent)
                self.action = action

            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    self.action()
                super().mousePressEvent(event)

        self.total_conn_card = CardWithAction("Total Connections", total_conns, f"{tcp_count} TCP, {udp_count} UDP", "#3498db", lambda: self.tabs.setCurrentIndex(6))
        self.metrics_layout.addWidget(self.total_conn_card, 0, 0)

        self.total_proc_card = CardWithAction("Total Processes", total_procs, f"{procs_with_net} with network", "#9b59b6", lambda: self.tabs.setCurrentIndex(2))
        self.metrics_layout.addWidget(self.total_proc_card, 0, 1)

        self.listening_card = CardWithAction("Listening Ports", listening, "Click to view", "#27ae60", lambda: self.filter_by_status('LISTEN'))
        self.metrics_layout.addWidget(self.listening_card, 0, 2)

        self.estab_card = CardWithAction("Established", established, f"{external} external", "#e67e22", lambda: self.filter_by_status('ESTAB'))
        self.metrics_layout.addWidget(self.estab_card, 0, 3)

        # Unsigned/untrusted
        unsigned = sum(1 for n in self.network_data
                      if not n.get('Authenticode') or n.get('Authenticode', {}).get('Trusted') != 'trusted')

        def goto_security():
            self.tabs.setCurrentIndex(3)
            self.signals.highlight_untrusted.emit()

        self.unsigned_card = CardWithAction("Unsigned/Untrusted", unsigned, "Click to analyze", "#e74c3c", goto_security)
        self.metrics_layout.addWidget(self.unsigned_card, 1, 0, 1, 2)

        # External IPs
        remote_ips = set(n.get('Raddr') for n in self.network_data
                        if n.get('Raddr') and n.get('Raddr') not in ['', '0.0.0.0', '::'])

        def goto_external():
            self.tabs.setCurrentIndex(3)
            self.signals.highlight_external.emit()

        self.remote_card = CardWithAction("Unique Remote IPs", len(remote_ips), "Click to view", "#16a085", goto_external)
        self.metrics_layout.addWidget(self.remote_card, 1, 2, 1, 2)

        # Activity feed
        self.activity_list.clear()
        recent = sorted(self.network_data, key=lambda x: x.get('Timestamp', ''), reverse=True)[:15]
        for conn in recent:
            status = conn.get('Status', '')
            icon = "🟢" if status == 'ESTAB' else "🔵" if status == 'LISTEN' else "⚪"
            text = f"{icon} {conn.get('Name')} ({conn.get('Pid')}) - {conn.get('Type')} {status}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, conn)
            self.activity_list.addItem(item)

        # Charts
        if CHARTS_AVAILABLE:
            self.create_dashboard_charts(tcp_count, udp_count)

    def create_dashboard_charts(self, tcp_count, udp_count):
        """Create dashboard charts"""
        # Pie chart
        series = QPieSeries()
        slice_tcp = series.append(f'TCP ({tcp_count})', tcp_count)
        slice_tcp.setBrush(QColor("#3498db"))
        slice_udp = series.append(f'UDP ({udp_count})', udp_count)
        slice_udp.setBrush(QColor("#e67e22"))

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle('Protocol Distribution')
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

        self.dashboard_chart1.setChart(chart)

        # Bar chart
        proc_counts = defaultdict(int)
        for n in self.network_data:
            proc_counts[n.get('Name', 'Unknown')] += 1

        top_10 = sorted(proc_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        set0 = QBarSet('Connections')
        set0.setColor(QColor("#9b59b6"))
        categories = []

        for name, count in top_10:
            set0.append(count)
            categories.append(name[:15])

        series = QBarSeries()
        series.append(set0)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle('Top Processes')

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(False)

        self.dashboard_chart2.setChart(chart)

    def populate_network_grid(self):
        """Populate network grid"""
        for i in reversed(range(self.grid_layout.count())):
            self.grid_layout.itemAt(i).widget().setParent(None)

        search = self.grid_search.text().lower()
        protocol = self.grid_protocol.currentText()
        status = self.grid_status.currentText()

        filtered = []
        for net in self.network_data:
            if protocol != 'All' and net.get('Type') != protocol:
                continue
            if status != 'All' and net.get('Status') != status:
                continue
            if search:
                searchable = f"{net.get('Name', '')} {net.get('Pid', '')} {net.get('Laddr', '')} {net.get('Raddr', '')}".lower()
                if search not in searchable:
                    continue
            filtered.append(net)

        cols = 3
        for idx, conn in enumerate(filtered[:50]):
            pid = str(conn.get('Pid', ''))
            proc_info = self.process_map.get(pid, {})
            card = ClickableConnectionCard(conn, proc_info)
            card.clicked.connect(self.on_card_clicked)
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

        self.grid_count_label.setText(f"Showing {min(len(filtered), 50)} of {len(filtered)} connections")

    def populate_process_intel(self):
        """Populate process intel tree"""
        self.intel_tree.clear()

        children_map = defaultdict(list)
        all_pids = set(str(p.get('Pid', '')) for p in self.process_data)

        for proc in self.process_data:
            ppid = str(proc.get('Ppid', ''))
            if ppid:
                children_map[ppid].append(proc)

        root_procs = [p for p in self.process_data
                     if str(p.get('Ppid', '')) not in all_pids or not p.get('Ppid')]

        def add_node(parent, proc):
            pid = str(proc.get('Pid', ''))
            conns = [n for n in self.network_data if str(n.get('Pid')) == pid]
            start = proc.get('StartTime', '')[:19].replace('T', ' ') if proc.get('StartTime') else ''

            item = QTreeWidgetItem([
                proc.get('Name', ''),
                pid,
                proc.get('Username', ''),
                str(len(conns)),
                start
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, proc)

            if len(conns) > 0:
                item.setBackground(0, QColor(255, 244, 179))

            if parent:
                parent.addChild(item)
            else:
                self.intel_tree.addTopLevelItem(item)

            for child in children_map.get(pid, []):
                add_node(item, child)

        for proc in root_procs:
            add_node(None, proc)

        self.intel_tree.expandAll()

    def populate_security_analysis(self):
        """Populate security tab"""
        for i in reversed(range(self.security_metrics_layout.count())):
            self.security_metrics_layout.itemAt(i).widget().setParent(None)

        unsigned = [n for n in self.network_data
                   if not n.get('Authenticode') or n.get('Authenticode', {}).get('Trusted') != 'trusted']

        external = [n for n in self.network_data
                   if n.get('Status') == 'ESTAB' and n.get('Raddr', '').strip()
                   and not n.get('Raddr', '').startswith('127.')
                   and not n.get('Raddr', '').startswith('::1')]

        high_ports = [n for n in self.network_data if n.get('Lport', 0) > 49152]

        cards = [
            ("Unsigned", len(set(n.get('Name') for n in unsigned)), "processes", "#e74c3c"),
            ("External", len(external), "connections", "#f39c12"),
            ("High Ports", len(high_ports), "> 49152", "#95a5a6"),
        ]

        for idx, (title, value, subtitle, color) in enumerate(cards):
            card = ClickableMetricCard(title, value, subtitle, color)
            self.security_metrics_layout.addWidget(card)

        # Threat list
        self.threat_list.clear()
        if unsigned:
            for proc_name in sorted(set(n.get('Name') for n in unsigned)):
                count = sum(1 for n in unsigned if n.get('Name') == proc_name)
                item = QListWidgetItem(f"🔴 {proc_name} ({count} unsigned connections)")
                item.setData(Qt.ItemDataRole.UserRole, proc_name)
                self.threat_list.addItem(item)

        # External table
        self.external_table.setRowCount(len(external))
        for row, conn in enumerate(external):
            pid = str(conn.get('Pid', ''))
            proc = self.process_map.get(pid, {})

            self.external_table.setItem(row, 0, QTableWidgetItem(conn.get('Name', '')))
            self.external_table.setItem(row, 1, QTableWidgetItem(pid))
            self.external_table.setItem(row, 2, QTableWidgetItem(conn.get('Raddr', '')))

            port_item = QTableWidgetItem(str(conn.get('Rport', '')))
            port_item.setData(Qt.ItemDataRole.UserRole, conn)
            self.external_table.setItem(row, 3, port_item)

            self.external_table.setItem(row, 4, QTableWidgetItem(conn.get('Type', '')))
            self.external_table.setItem(row, 5, QTableWidgetItem(proc.get('Username', '')))

        self.external_table.resizeColumnsToContents()

    def populate_process_tree(self):
        """Populate interactive tree"""
        self.process_tree.clear()

        children_map = defaultdict(list)
        all_pids = set(str(p.get('Pid', '')) for p in self.process_data)

        for proc in self.process_data:
            ppid = str(proc.get('Ppid', ''))
            if ppid:
                children_map[ppid].append(proc)

        root_procs = [p for p in self.process_data
                     if str(p.get('Ppid', '')) not in all_pids or not p.get('Ppid')]

        def add_node(parent, proc):
            pid = str(proc.get('Pid', ''))
            conns = [n for n in self.network_data if str(n.get('Pid')) == pid]
            start = proc.get('StartTime', '')[:19].replace('T', ' ') if proc.get('StartTime') else ''

            sample_conn = next((n for n in conns), None)
            auth_info = sample_conn.get('Authenticode') if sample_conn else None
            trusted = "✓" if auth_info and auth_info.get('Trusted') == 'trusted' else "✗"

            item = QTreeWidgetItem([
                f"{proc.get('Name', '')} ({pid})",
                proc.get('Username', ''),
                str(len(conns)),
                start,
                trusted
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, proc)

            if len(conns) > 0:
                item.setForeground(0, QBrush(QColor("#f39c12")))
                item.setBackground(0, QColor(255, 250, 230))

            if trusted == "✓":
                item.setForeground(4, QBrush(QColor("#27ae60")))
            else:
                item.setForeground(4, QBrush(QColor("#e74c3c")))

            if parent:
                parent.addChild(item)
            else:
                self.process_tree.addTopLevelItem(item)

            for child in children_map.get(pid, []):
                add_node(item, child)

        for proc in root_procs:
            add_node(None, proc)

        self.process_tree.expandToDepth(1)

    def populate_timeline(self):
        """Populate timeline"""
        sorted_procs = sorted(self.process_data, key=lambda x: x.get('StartTime', ''), reverse=True)

        self.timeline_table.setRowCount(len(sorted_procs))

        for row, proc in enumerate(sorted_procs):
            pid = str(proc.get('Pid', ''))
            conns = [n for n in self.network_data if str(n.get('Pid')) == pid]
            listening = sum(1 for c in conns if c.get('Status') == 'LISTEN')
            established = sum(1 for c in conns if c.get('Status') == 'ESTAB')

            start = proc.get('StartTime', '')[:19].replace('T', ' ') if proc.get('StartTime') else ''

            time_item = QTableWidgetItem(start)
            time_item.setData(Qt.ItemDataRole.UserRole, proc)
            self.timeline_table.setItem(row, 0, time_item)

            self.timeline_table.setItem(row, 1, QTableWidgetItem("🔷 Process Start"))
            self.timeline_table.setItem(row, 2, QTableWidgetItem(proc.get('Name', '')))
            self.timeline_table.setItem(row, 3, QTableWidgetItem(pid))
            self.timeline_table.setItem(row, 4, QTableWidgetItem(proc.get('Username', '')))

            conn_item = QTableWidgetItem(str(len(conns)))
            if len(conns) > 0:
                conn_item.setBackground(QColor(255, 244, 179))
            self.timeline_table.setItem(row, 5, conn_item)

            self.timeline_table.setItem(row, 6, QTableWidgetItem(str(listening)))
            self.timeline_table.setItem(row, 7, QTableWidgetItem(str(established)))
            self.timeline_table.setItem(row, 8, QTableWidgetItem(proc.get('CallChain', '')))

        self.timeline_table.resizeColumnsToContents()

    def populate_advanced_table(self):
        """Populate advanced table"""
        self.filtered_data = self.network_data.copy()
        self.update_advanced_table()

    def update_advanced_table(self):
        """Update advanced table"""
        self.advanced_table.setSortingEnabled(False)
        self.advanced_table.setRowCount(len(self.filtered_data))

        for row, net in enumerate(self.filtered_data):
            pid = str(net.get('Pid', ''))
            proc = self.process_map.get(pid, {})

            pid_item = QTableWidgetItem(pid)
            pid_item.setData(Qt.ItemDataRole.UserRole, net)
            self.advanced_table.setItem(row, 0, pid_item)

            self.advanced_table.setItem(row, 1, QTableWidgetItem(net.get('Name', '')))
            self.advanced_table.setItem(row, 2, QTableWidgetItem(net.get('Type', '')))

            status_item = QTableWidgetItem(net.get('Status', ''))
            if net.get('Status') == 'ESTAB':
                status_item.setBackground(QColor(144, 238, 144))
            elif net.get('Status') == 'LISTEN':
                status_item.setBackground(QColor(173, 216, 230))
            self.advanced_table.setItem(row, 3, status_item)

            self.advanced_table.setItem(row, 4, QTableWidgetItem(net.get('Laddr', '')))

            lport_item = QTableWidgetItem()
            lport_item.setData(Qt.ItemDataRole.DisplayRole, net.get('Lport', 0))
            self.advanced_table.setItem(row, 5, lport_item)

            self.advanced_table.setItem(row, 6, QTableWidgetItem(net.get('Raddr', '')))

            rport_item = QTableWidgetItem()
            rport_item.setData(Qt.ItemDataRole.DisplayRole, net.get('Rport', 0))
            self.advanced_table.setItem(row, 7, rport_item)

            username = proc.get('Username', net.get('Username', ''))
            self.advanced_table.setItem(row, 8, QTableWidgetItem(username))

            start = proc.get('StartTime', '')[:19].replace('T', ' ') if proc.get('StartTime') else 'N/A'
            self.advanced_table.setItem(row, 9, QTableWidgetItem(start))

            uptime = self.calculate_uptime(proc.get('StartTime', ''))
            self.advanced_table.setItem(row, 10, QTableWidgetItem(uptime))

            chain = proc.get('CallChain', '')
            if chain:
                parts = chain.split(' -> ')
                if len(parts) > 3:
                    chain = '...' + ' -> '.join(parts[-3:])
            self.advanced_table.setItem(row, 11, QTableWidgetItem(chain))

            auth = net.get('Authenticode')
            trusted_item = QTableWidgetItem()
            if auth and auth.get('Trusted') == 'trusted':
                trusted_item.setText('✓')
                trusted_item.setForeground(QBrush(QColor("#27ae60")))
            else:
                trusted_item.setText('✗')
                trusted_item.setForeground(QBrush(QColor("#e74c3c")))
            self.advanced_table.setItem(row, 12, trusted_item)

            conn_time = net.get('Timestamp', '')[:19].replace('T', ' ') if net.get('Timestamp') else ''
            self.advanced_table.setItem(row, 13, QTableWidgetItem(conn_time))

            self.advanced_table.setItem(row, 14, QTableWidgetItem(str(proc.get('Ppid', ''))))

        self.advanced_table.setSortingEnabled(True)
        self.table_count.setText(f"Results: {len(self.filtered_data)} / {len(self.network_data)}")
        self.advanced_table.resizeColumnsToContents()

    # Event handlers for interactivity
    def on_tab_changed(self, index):
        """Update breadcrumb when tab changes"""
        tab_names = ["Dashboard", "Network Grid", "Process Intel", "Security", "Process Tree", "Timeline", "Table View"]
        if index < len(tab_names):
            self.breadcrumb.setText(f"📍 {tab_names[index]}")

    def on_card_clicked(self, conn_data):
        """Handle connection card click"""
        self.signals.connection_selected.emit(conn_data)

    def on_connection_selected(self, conn_data):
        """Handle connection selection"""
        pid = str(conn_data.get('Pid', ''))
        proc = self.process_map.get(pid, {})

        # Show details in message box
        details = f"""
Connection Details:

Process: {conn_data.get('Name')}
PID: {pid}
User: {proc.get('Username', conn_data.get('Username', 'N/A'))}

Protocol: {conn_data.get('Type')} ({conn_data.get('Family')})
Status: {conn_data.get('Status')}
Local: {conn_data.get('Laddr')}:{conn_data.get('Lport')}
Remote: {conn_data.get('Raddr')}:{conn_data.get('Rport')}

Time: {conn_data.get('Timestamp', 'N/A')}

Click OK to navigate to this process in the Process Tree
"""

        reply = QMessageBox.question(self, "Connection Details", details,
                                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

        if reply == QMessageBox.StandardButton.Ok:
            self.signals.process_selected.emit(pid)
            self.tabs.setCurrentIndex(4)  # Go to tree tab

    def on_process_selected(self, pid):
        """Handle process selection - highlight in tree"""
        self.statusBar().showMessage(f"Viewing process PID: {pid}")
        # Could highlight the process in the tree here

    def on_intel_tree_clicked(self, item):
        """Show process details when clicked"""
        proc = item.data(0, Qt.ItemDataRole.UserRole)
        if not proc:
            return

        pid = str(proc.get('Pid', ''))
        conns = [n for n in self.network_data if str(n.get('Pid')) == pid]

        details = []
        details.append("=" * 60)
        details.append(f"PROCESS: {proc.get('Name', 'Unknown')}")
        details.append("=" * 60)
        details.append(f"PID:          {pid}")
        details.append(f"PPID:         {proc.get('Ppid', 'N/A')}")
        details.append(f"User:         {proc.get('Username', 'N/A')}")
        details.append(f"Executable:   {proc.get('Exe', 'N/A')}")
        details.append(f"Command:      {proc.get('CommandLine', 'N/A')}")
        details.append(f"Start Time:   {proc.get('StartTime', 'N/A')}")
        details.append(f"Call Chain:   {proc.get('CallChain', 'N/A')}")
        details.append(f"\nNetwork Connections: {len(conns)}")
        details.append("-" * 60)

        for idx, conn in enumerate(conns, 1):
            details.append(f"\n{idx}. {conn.get('Type')} - {conn.get('Status')}")
            details.append(f"   Local:  {conn.get('Laddr')}:{conn.get('Lport')}")
            details.append(f"   Remote: {conn.get('Raddr')}:{conn.get('Rport')}")

        self.intel_details.setText('\n'.join(details))
        self.statusBar().showMessage(f"Selected: {proc.get('Name')} (PID: {pid})")

    def on_intel_tree_double_clicked(self, item):
        """Navigate to process tree when double-clicked"""
        proc = item.data(0, Qt.ItemDataRole.UserRole)
        if proc:
            pid = str(proc.get('Pid', ''))
            self.signals.process_selected.emit(pid)
            self.tabs.setCurrentIndex(4)

    def on_tree_double_clicked(self, item):
        """Show process connections when tree item double-clicked"""
        proc = item.data(0, Qt.ItemDataRole.UserRole)
        if proc:
            proc_name = proc.get('Name', '')
            self.signals.filter_by_process.emit(proc_name)
            self.tabs.setCurrentIndex(1)  # Go to grid view

    def on_activity_clicked(self, item):
        """Navigate when activity item clicked"""
        conn = item.data(Qt.ItemDataRole.UserRole)
        if conn:
            self.signals.connection_selected.emit(conn)

    def on_threat_clicked(self, item):
        """Filter by unsigned process"""
        proc_name = item.data(Qt.ItemDataRole.UserRole)
        if proc_name:
            self.signals.filter_by_process.emit(proc_name)
            self.tabs.setCurrentIndex(1)

    def on_external_table_clicked(self, row, col):
        """Show external connection details"""
        item = self.external_table.item(row, 3)
        if item:
            conn = item.data(Qt.ItemDataRole.UserRole)
            if conn:
                self.signals.connection_selected.emit(conn)

    def on_timeline_clicked(self, row, col):
        """Navigate from timeline"""
        item = self.timeline_table.item(row, 0)
        if item:
            proc = item.data(Qt.ItemDataRole.UserRole)
            if proc:
                pid = str(proc.get('Pid', ''))
                self.tabs.setCurrentIndex(2)
                self.select_process_in_intel_tree(pid)
                self.statusBar().showMessage(f"Viewing process PID: {pid}")

    def on_table_double_clicked(self, row, col):
        """Navigate from table and select process"""
        item = self.advanced_table.item(row, 0)
        if item:
            conn = item.data(Qt.ItemDataRole.UserRole)
            if conn:
                pid = str(conn.get('Pid', ''))
                self.tabs.setCurrentIndex(2)  # Go to Process Intel tab
                self.select_process_in_intel_tree(pid)
                self.statusBar().showMessage(f"Viewing process PID: {pid}")

    def goto_tree_tab(self):
        """Navigate to Process Tree and highlight selected process"""
        # Tab indices: 0=Dashboard, 1=Network Grid, 2=Process Intel, 3=Security, 4=Process Tree, 5=Timeline, 6=Table
        selected = self.intel_tree.selectedItems()
        if selected:
            proc = selected[0].data(0, Qt.ItemDataRole.UserRole)
            if proc:
                pid = str(proc.get('Pid', ''))
                proc_name = proc.get('Name', '')

                # Navigate to tree tab
                self.tabs.setCurrentIndex(4)

                # Search for the process in the tree
                self.tree_search.setText(proc_name)

                self.statusBar().showMessage(f"Viewing {proc_name} (PID: {pid}) in Process Tree")
        else:
            self.tabs.setCurrentIndex(4)
            self.statusBar().showMessage("Select a process first to highlight it in the tree")

    def goto_table_tab(self):
        """Navigate to Table View and filter by selected process"""
        # Tab indices: 0=Dashboard, 1=Network Grid, 2=Process Intel, 3=Security, 4=Process Tree, 5=Timeline, 6=Table
        selected = self.intel_tree.selectedItems()
        if selected:
            proc = selected[0].data(0, Qt.ItemDataRole.UserRole)
            if proc:
                proc_name = proc.get('Name', '')
                pid = str(proc.get('Pid', ''))

                # Navigate to table tab
                self.tabs.setCurrentIndex(6)

                # Filter by process name
                self.table_search.setText(proc_name)
                self.apply_table_filters()

                self.statusBar().showMessage(f"Showing connections for {proc_name} (PID: {pid})")
        else:
            self.tabs.setCurrentIndex(6)
            self.statusBar().showMessage("Select a process first to filter the table")

    def filter_by_selected_process(self):
        """Filter by currently selected process in intel view"""
        selected = self.intel_tree.selectedItems()
        if selected:
            proc = selected[0].data(0, Qt.ItemDataRole.UserRole)
            if proc:
                proc_name = proc.get('Name', '')
                self.signals.filter_by_process.emit(proc_name)
                self.tabs.setCurrentIndex(1)
                self.statusBar().showMessage(f"Filtered by process: {proc_name}")

    def on_filter_by_process(self, proc_name):
        """Filter network grid by process name"""
        self.grid_search.setText(proc_name)
        self.update_network_grid()
        self.statusBar().showMessage(f"Filtered by process: {proc_name}")

    def on_filter_by_user(self, username):
        """Filter by user"""
        self.table_user.setCurrentText(username)
        self.apply_table_filters()

    def on_highlight_external(self):
        """Highlight external connections"""
        self.statusBar().showMessage("Viewing external connections")

    def on_highlight_untrusted(self):
        """Highlight untrusted"""
        self.statusBar().showMessage("Viewing untrusted processes")

    def filter_by_status(self, status):
        """Filter by connection status"""
        self.table_status.setCurrentText(status)
        self.apply_table_filters()
        self.tabs.setCurrentIndex(6)
        self.statusBar().showMessage(f"Filtered by status: {status}")

    def update_network_grid(self):
        """Update grid"""
        self.populate_network_grid()

    def clear_grid_filters(self):
        """Clear grid filters"""
        self.grid_search.clear()
        self.grid_protocol.setCurrentIndex(0)
        self.grid_status.setCurrentIndex(0)

    def apply_table_filters(self):
        """Apply table filters"""
        search = self.table_search.text().lower()
        protocol = self.table_protocol.currentText()
        status = self.table_status.currentText()
        user = self.table_user.currentText()

        self.filtered_data = []

        for net in self.network_data:
            pid = str(net.get('Pid', ''))
            proc = self.process_map.get(pid, {})

            if protocol != 'All Protocols' and net.get('Type') != protocol:
                continue
            if status != 'All Status' and net.get('Status') != status:
                continue
            if user != 'All Users':
                net_user = proc.get('Username', net.get('Username', ''))
                if net_user != user:
                    continue
            if search:
                searchable = f"{net.get('Name', '')} {pid} {net.get('Laddr', '')} {net.get('Raddr', '')}".lower()
                if search not in searchable:
                    continue

            self.filtered_data.append(net)

        self.update_advanced_table()

    def clear_table_filters(self):
        """Clear all table filters"""
        self.table_search.clear()
        self.table_protocol.setCurrentIndex(0)
        self.table_status.setCurrentIndex(0)
        self.table_user.setCurrentIndex(0)

    def filter_tree(self):
        """Filter process tree"""
        search_text = self.tree_search.text().lower()

        def filter_item(item):
            show = False
            if search_text in item.text(0).lower():
                show = True

            for i in range(item.childCount()):
                child_show = filter_item(item.child(i))
                show = show or child_show

            item.setHidden(not show)
            return show

        if search_text:
            for i in range(self.process_tree.topLevelItemCount()):
                filter_item(self.process_tree.topLevelItem(i))
            self.process_tree.expandAll()
        else:
            for i in range(self.process_tree.topLevelItemCount()):
                self.show_all_items(self.process_tree.topLevelItem(i))
            self.process_tree.collapseAll()
            self.process_tree.expandToDepth(1)

    def show_all_items(self, item):
        """Show all tree items"""
        item.setHidden(False)
        for i in range(item.childCount()):
            self.show_all_items(item.child(i))

    def select_process_in_intel_tree(self, pid):
        """Find and select a process in the Process Intel tree."""
        iterator = QTreeWidgetItemIterator(self.intel_tree)
        while iterator.value():
            item = iterator.value()
            if item.text(1) == pid:
                self.intel_tree.setCurrentItem(item)
                self.intel_tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                # Expand parents
                parent = item.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
                
                # Manually trigger the details update
                self.on_intel_tree_clicked(item)

                break
            iterator += 1

    def calculate_uptime(self, start_time_str):
        """Calculate uptime"""
        if not start_time_str or start_time_str == '0001-01-01T00:00:00Z':
            return 'N/A'

        try:
            start = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            now = datetime.now(start.tzinfo)
            delta = now - start

            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            if days > 0:
                return f'{days}d {hours}h'
            elif hours > 0:
                return f'{hours}h {minutes}m'
            else:
                return f'{minutes}m'
        except:
            return 'N/A'


def main():
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    viewer = InteractiveNetworkViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
