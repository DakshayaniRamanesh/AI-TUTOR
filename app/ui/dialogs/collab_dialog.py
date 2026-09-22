"""
Kestrel Collaboration Dialog
Modal dialog for creating, sharing, joining, and managing live collaborative whiteboard sessions.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QWidget, QComboBox, QFrame, QApplication, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QFont, QClipboard
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
import qtawesome as qta

from ...collaboration.collab_session_manager import CollabSessionManager, CollabRole
from ...collaboration.collab_protocol import get_local_ip_addresses, DEFAULT_COLLAB_PORT
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT


class CollabDialog(QDialog):
    """
    Share & Real-Time Collaboration Modal Dialog.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kestrel Collaboration")
        self.setFixedSize(540, 520)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.manager = CollabSessionManager.instance()
        self.manager.session_state_changed.connect(self._on_session_state_changed)
        self.manager.peer_count_changed.connect(self._on_peer_count_changed)
        self.manager.connection_error.connect(self._on_connection_error)

        self._init_ui()
        self._refresh_view()

    def _init_ui(self):
        c = ThemeManager.instance().get_colors()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        # Card container with shadow
        self.card = QFrame(self)
        self.card.setObjectName("CollabCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 70))
        shadow.setOffset(0, 4)
        self.card.setGraphicsEffect(shadow)

        self._apply_card_styling()

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 20, 24, 24)
        card_layout.setSpacing(16)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        icon_lbl = QLabel(self.card)
        icon_lbl.setPixmap(qta.icon('ri.team-line', color='#8b5cf6').pixmap(24, 24))
        hdr.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Live Collaboration", self.card)
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {c['text_primary']};")
        subtitle_lbl = QLabel("Work simultaneously on the canvas & notes with peers", self.card)
        subtitle_lbl.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)
        hdr.addLayout(title_box)

        hdr.addStretch()

        btn_close = QPushButton("✕", self.card)
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c['border_color']};
                border-radius: 14px;
                color: {c['text_secondary']};
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
                color: {c['text_primary']};
            }}
        """)
        btn_close.clicked.connect(self.close)
        hdr.addWidget(btn_close)

        card_layout.addLayout(hdr)

        # ── Body: Stack between Tabs (Not in session) and Active Session View ──
        self.tabs_container = QWidget(self.card)
        tabs_layout = QVBoxLayout(self.tabs_container)
        tabs_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget(self.tabs_container)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {c['border_color']};
                border-radius: 8px;
                background-color: {c['panel_card_bg']};
                padding: 16px;
            }}
            QTabBar::tab {{
                padding: 8px 20px;
                font-weight: 600;
                font-size: 12px;
                background: transparent;
                color: {c['text_secondary']};
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: #8b5cf6;
                border-bottom: 2px solid #8b5cf6;
            }}
        """)

        # Tab 1: Host
        self.tab_host = self._create_host_tab()
        self.tab_widget.addTab(self.tab_host, "Host Session")

        # Tab 2: Join
        self.tab_join = self._create_join_tab()
        self.tab_widget.addTab(self.tab_join, "Join Session")

        tabs_layout.addWidget(self.tab_widget)
        card_layout.addWidget(self.tabs_container)

        # Active Session View (Shown when in active session)
        self.active_session_container = self._create_active_session_view()
        card_layout.addWidget(self.active_session_container)

        # Error / Status Label
        self.lbl_status = QLabel("", self.card)
        self.lbl_status.setStyleSheet("font-size: 11px; color: #ef4444; font-weight: 500;")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setVisible(False)
        card_layout.addWidget(self.lbl_status)

        outer.addWidget(self.card)

    def _apply_card_styling(self):
        c = ThemeManager.instance().get_colors()
        self.card.setStyleSheet(f"""
            QFrame#CollabCard {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 12px;
            }}
            QLineEdit {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 6px;
                padding: 8px 12px;
                color: {c['text_primary']};
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid #8b5cf6;
            }}
            QComboBox {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 6px;
                padding: 6px 12px;
                color: {c['text_primary']};
                font-size: 12px;
            }}
        """)

    # ── Host Tab ──────────────────────────────────────────────────────────────

    def _create_host_tab(self) -> QWidget:
        c = ThemeManager.instance().get_colors()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)
        layout.setContentsMargins(4, 8, 4, 4)

        # Name Field
        layout.addWidget(QLabel("Your Display Name:", tab))
        self.txt_host_name = QLineEdit("Host", tab)
        layout.addWidget(self.txt_host_name)

        # Network Interface Selector
        layout.addWidget(QLabel("Share Over Network:", tab))
        self.combo_interfaces = QComboBox(tab)
        ips = get_local_ip_addresses()
        for ip, desc in ips:
            self.combo_interfaces.addItem(f"{ip} ({desc})", ip)
        layout.addWidget(self.combo_interfaces)

        # Host Button
        self.btn_start_host = QPushButton("🚀 Start Hosting Live Session", tab)
        self.btn_start_host.setFixedHeight(38)
        self.btn_start_host.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start_host.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #6366f1);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #4f46e5);
            }
        """)
        self.btn_start_host.clicked.connect(self._on_start_hosting_clicked)
        layout.addWidget(self.btn_start_host)

        info_lbl = QLabel("Peers on the same Wi-Fi, Tailscale, or VPN can join with your Room Code.", tab)
        info_lbl.setStyleSheet(f"font-size: 10px; color: {c['text_secondary']};")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        layout.addStretch()
        return tab

    # ── Join Tab ──────────────────────────────────────────────────────────────

    def _create_join_tab(self) -> QWidget:
        c = ThemeManager.instance().get_colors()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)
        layout.setContentsMargins(4, 8, 4, 4)

        # Name Field
        layout.addWidget(QLabel("Your Display Name:", tab))
        self.txt_join_name = QLineEdit("Collaborator", tab)
        layout.addWidget(self.txt_join_name)

        # Room Code / Link Input
        layout.addWidget(QLabel("Room Code or Share Link:", tab))
        code_row = QHBoxLayout()
        code_row.setSpacing(8)
        self.txt_join_code = QLineEdit(tab)
        self.txt_join_code.setPlaceholderText("e.g. KEST-C0A8010F-223D or 192.168.1.15:8765")
        code_row.addWidget(self.txt_join_code)

        btn_paste = QPushButton("Paste", tab)
        btn_paste.setFixedHeight(34)
        btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_paste.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 600;
                font-size: 11px;
                color: {c['text_primary']};
            }}
            QPushButton:hover {{
                border-color: #8b5cf6;
            }}
        """)
        btn_paste.clicked.connect(self._on_paste_clicked)
        code_row.addWidget(btn_paste)
        layout.addLayout(code_row)

        # Connect Button
        self.btn_join = QPushButton("⚡ Connect to Canvas", tab)
        self.btn_join.setFixedHeight(38)
        self.btn_join.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_join.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
            }
        """)
        self.btn_join.clicked.connect(self._on_join_clicked)
        layout.addWidget(self.btn_join)

        layout.addStretch()
        return tab

    # ── Active Session View ───────────────────────────────────────────────────

    def _create_active_session_view(self) -> QWidget:
        c = ThemeManager.instance().get_colors()
        widget = QWidget(self.card)
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 0, 0)

        # Status Pill Bar
        status_bar = QHBoxLayout()
        self.lbl_live_badge = QLabel("🟢 LIVE SESSION ACTIVE", widget)
        self.lbl_live_badge.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #10b981;
            letter-spacing: 1px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 4px;
            padding: 4px 10px;
        """)
        status_bar.addWidget(self.lbl_live_badge)

        self.lbl_role = QLabel("Role: Host", widget)
        self.lbl_role.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']}; font-weight: 600;")
        status_bar.addWidget(self.lbl_role)
        status_bar.addStretch()

        self.lbl_members_count = QLabel("👥 1 member", widget)
        self.lbl_members_count.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {c['text_primary']};")
        status_bar.addWidget(self.lbl_members_count)
        layout.addLayout(status_bar)

        # Room Code Card
        code_card = QFrame(widget)
        code_card.setStyleSheet(f"""
            QFrame {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        cc_layout = QVBoxLayout(code_card)
        cc_layout.setSpacing(8)

        cc_top = QHBoxLayout()
        cc_lbl_title = QLabel("ROOM CODE", code_card)
        cc_lbl_title.setStyleSheet(f"font-size: 10px; font-weight: 700; letter-spacing: 1px; color: {c['text_secondary']};")
        cc_top.addWidget(cc_lbl_title)
        cc_top.addStretch()

        self.btn_copy_code = QPushButton("Copy Code", code_card)
        self.btn_copy_code.setFixedSize(90, 26)
        self.btn_copy_code.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_code.setStyleSheet(f"""
            QPushButton {{
                background-color: #8b5cf6;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #7c3aed;
            }}
        """)
        self.btn_copy_code.clicked.connect(self._copy_room_code)
        cc_top.addWidget(self.btn_copy_code)
        cc_layout.addLayout(cc_top)

        self.lbl_display_code = QLabel("KEST-XXXX", code_card)
        self.lbl_display_code.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 700;
            font-family: {MONO_FONT};
            letter-spacing: 2px;
            color: {c['text_primary']};
        """)
        self.lbl_display_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cc_layout.addWidget(self.lbl_display_code)

        layout.addWidget(code_card)

        # Share Link Row
        link_card = QFrame(widget)
        link_card.setStyleSheet(f"""
            QFrame {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        lc_layout = QHBoxLayout(link_card)
        self.lbl_share_link = QLabel("kestrel://collab/...", link_card)
        self.lbl_share_link.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']}; font-family: {MONO_FONT};")
        self.lbl_share_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lc_layout.addWidget(self.lbl_share_link)

        self.btn_copy_link = QPushButton("Copy Link", link_card)
        self.btn_copy_link.setFixedSize(85, 26)
        self.btn_copy_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_link.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c['border_color']};
                border-radius: 4px;
                color: {c['text_primary']};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: #8b5cf6;
            }}
        """)
        self.btn_copy_link.clicked.connect(self._copy_share_link)
        lc_layout.addWidget(self.btn_copy_link)
        layout.addWidget(link_card)

        # Leave / End Session Button
        self.btn_leave = QPushButton("End Live Session", widget)
        self.btn_leave.setFixedHeight(34)
        self.btn_leave.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_leave.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        self.btn_leave.clicked.connect(self._on_leave_clicked)
        layout.addWidget(self.btn_leave)

        return widget

    # ── Action Handlers ───────────────────────────────────────────────────────

    def _on_start_hosting_clicked(self):
        self.lbl_status.setVisible(False)
        selected_ip = self.combo_interfaces.currentData()
        name = self.txt_host_name.text().strip() or "Host"

        self.btn_start_host.setEnabled(False)
        self.btn_start_host.setText("Starting Session...")

        success, err = self.manager.start_hosting(
            display_ip=selected_ip,
            port=DEFAULT_COLLAB_PORT,
            user_name=name
        )
        self.btn_start_host.setEnabled(True)
        self.btn_start_host.setText("🚀 Start Hosting Live Session")

        if not success:
            self._show_error(f"Failed to start hosting: {err}")

    def _on_join_clicked(self):
        self.lbl_status.setVisible(False)
        code = self.txt_join_code.text().strip()
        name = self.txt_join_name.text().strip() or "Guest"

        if not code:
            self._show_error("Please enter a Room Code or Host Address.")
            return

        self.btn_join.setEnabled(False)
        self.btn_join.setText("Connecting...")

        success, err = self.manager.join_session(code, user_name=name)
        self.btn_join.setEnabled(True)
        self.btn_join.setText("⚡ Connect to Canvas")

        if not success:
            self._show_error(err)

    def _on_paste_clicked(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.txt_join_code.setText(text)

    def _copy_room_code(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.manager.room_code)
        self.btn_copy_code.setText("✓ Copied!")
        QTimer.singleShot(1800, lambda: self.btn_copy_code.setText("Copy Code"))

    def _copy_share_link(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.manager.share_link)
        self.btn_copy_link.setText("✓ Copied!")
        QTimer.singleShot(1800, lambda: self.btn_copy_link.setText("Copy Link"))

    def _on_leave_clicked(self):
        self.manager.leave_session()
        self._refresh_view()

    def _show_error(self, message: str):
        self.lbl_status.setText(message)
        self.lbl_status.setVisible(True)

    # ── Reactive View Refreshing ──────────────────────────────────────────────

    def _refresh_view(self):
        if self.manager.is_in_session:
            self.tabs_container.setVisible(False)
            self.active_session_container.setVisible(True)
            self.lbl_display_code.setText(self.manager.room_code)
            self.lbl_share_link.setText(self.manager.share_link)
            self.lbl_role.setText(f"Role: {'Host (You)' if self.manager.role == CollabRole.HOST else 'Guest'}")
            self.btn_leave.setText("End Live Session" if self.manager.role == CollabRole.HOST else "Leave Session")
        else:
            self.tabs_container.setVisible(True)
            self.active_session_container.setVisible(False)
            self.lbl_status.setVisible(False)

    def _on_session_state_changed(self, role: str, room_code: str, share_link: str):
        self._refresh_view()

    def _on_peer_count_changed(self, count: int):
        self.lbl_members_count.setText(f"👥 {count} member{'s' if count != 1 else ''}")

    def _on_connection_error(self, err: str):
        self._show_error(err)
