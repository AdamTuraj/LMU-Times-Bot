# MIT License
#
# Copyright (c) 2026 Adam Turaj
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import secrets
import sys
import threading
import webbrowser

from PyQt6.QtCore import pyqtSignal, Qt, QSettings
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget
)

from config.settings import (
    __version__,
    APP_NAME,
    OAUTH_CALLBACK_PORT,
    POLL_INTERVAL,
    TRACK_NAMES,
)
from config.helpers import (
    logger,
    flash_window,
    play_info_sound,
    play_error_sound,
    hide_to_tray,
    save_token,
    delete_token,
    get_token,
)
from ui.ui_styles import get_stylesheet
from ui.load_session_popup import LoadSessionPopup
from utils.backend import Backend
from utils.lmu import LMU
from utils.token_server import LocalCallbackServer
from utils.resources import get_embedded_icon
from core.session_validator import SessionValidator
from core.session_recorder import SessionRecorder


class MainWindow(QMainWindow):
    # Signals for thread-safe UI updates
    oauth_result = pyqtSignal(str, str)
    show_record_dialog = pyqtSignal(dict)
    update_status_signal = pyqtSignal(str)
    add_session_button_signal = pyqtSignal(str)
    add_check_lb_button_signal = pyqtSignal()
    remove_session_button_signal = pyqtSignal()
    show_window_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(350, 200)
        self.resize(380, 230)
        logger.info("Starting %s", APP_NAME)
        
        # Load embedded icon
        try:
            app_icon = get_embedded_icon()
            if app_icon and not app_icon.isNull():
                self.setWindowIcon(app_icon)
            else:
                logger.warning("Failed to load embedded icon - using default")
        except Exception as e:
            logger.warning("Error loading embedded icon: %s", e)

        # Dialogs
        self.load_session_popup = LoadSessionPopup()

        # Settings
        self.settings = QSettings("LMU Times Bot", "Recorder")

        # Initialize clients
        self.backend = Backend()
        self.lmu = LMU()
        
        # Check version compatibility
        self._check_version_compatibility()
        
        # Fetch car models from backend
        self.car_models = self.backend.get_car_models()
        if not self.car_models:
            self._show_fatal_error("Backend Error", "Failed to load car models from backend.")
        
        #Initialize logic components
        self.validator = None  # Created after login when we have token
        self.recorder = None
        
        # OAuth
        self.oauth_server = None
        self.token = None
        self.username = None
        self.logged_in = False

        # Session state
        self.track = None
        self.car = None
        self.setup_session_button_track = None
        self.session_button = None
        self.check_for_setup_session = False

        # Try to restore session
        self._restore_session()

        # Setup system tray
        self._setup_system_tray()

        # Setup UI
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(8)
        self.setup_ui()

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        # Connect signals
        self.oauth_result.connect(self.on_oauth_result)
        self.show_record_dialog.connect(self.on_show_record_dialog)
        self.update_status_signal.connect(self.on_update_status)
        self.add_session_button_signal.connect(self.on_add_session_button)
        self.add_check_lb_button_signal.connect(self.check_for_leaderboard)
        self.remove_session_button_signal.connect(self.on_remove_session_button)
        self.show_window_signal.connect(self.on_show_window)

    # ============================================================
    # Initialization Helper Methods
    # ============================================================

    def _check_version_compatibility(self):
        """Check if client version matches backend version."""
        backend_version = self.backend.get_version()
        if not backend_version:
            self._show_fatal_error("Backend Error", 
                                  "Failed to connect to backend. Please check your connection and try again.")
        
        if backend_version != __version__:
            logger.error("Version mismatch: Client=%s Expected=%s", __version__, backend_version)
            self._show_fatal_error("Version Mismatch",
                f"Your client version ({__version__}) does not match the latest version ({backend_version}).\n\n"
                "Please download the latest executable.")

    def _show_fatal_error(self, title, message):
        """Show a fatal error and exit the application."""
        logger.error("%s: %s", title, message)
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        sys.exit(1)

    def _restore_session(self):
        """Try to restore a saved session."""
        self.token = get_token()
        if self.token:
            self.username = self.backend.get_username(self.token)
            if self.username:
                self.logged_in = True
                logger.info("Session restored for %s", self.username)
                # Initialize logic components with token
                self._init_logic()
            else:
                delete_token()
                self.token = None

    def _init_logic(self):
        """Initialize validator and recorder with current credentials."""
        self.validator = SessionValidator(self.lmu, self.backend, self.car_models)
        self.recorder = SessionRecorder(self.lmu, self.backend, self.token)

    def _setup_system_tray(self):
        """Setup system tray icon and menu."""
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.windowIcon()
        if not icon.isNull():
            self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip(APP_NAME)
        
        # Create tray menu
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    # ============================================================
    # UI Setup
    # ============================================================

    def setup_ui(self):
        """Build the UI based on login state."""
        self.setStyleSheet(get_stylesheet())
        if self.logged_in:
            self.add_logged_in_ui()
        else:
            self.add_login_ui()

    def add_logged_in_ui(self):
        """Add UI for logged in state."""
        self.layout.addStretch(1)
        
        self.status_label = QLabel(f"Logged in as {self.username}\nWaiting for LMU...")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        font = QFont()
        font.setPointSize(9)
        self.status_label.setFont(font)
        self.layout.addWidget(self.status_label)
        
        self.layout.addStretch(2)

        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("secondaryButton")
        logout_btn.setMinimumHeight(32)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(self.logout)
        self.layout.addWidget(logout_btn)

        threading.Thread(target=self.poll_lmu, daemon=True).start()

    def add_login_ui(self):
        """Add UI for logged out state."""
        self.layout.addStretch(2)
        
        login_btn = QPushButton("Login with Discord")
        login_btn.setObjectName("loginButton")
        login_btn.setMinimumWidth(220)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self.open_oauth)
        self.layout.addWidget(login_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.layout.addSpacing(10)

        self.status_label = QLabel("Please login to continue")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(8)
        self.status_label.setFont(font)
        self.layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addStretch(3)

    def clear_layout(self):
        """Clear all widgets from layout."""
        self.session_button = None
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ============================================================
    # Status Updates
    # ============================================================

    def update_status(self, message):
        """Update status label (thread-safe via signal)."""
        self.update_status_signal.emit(message)

    def on_update_status(self, message):
        """Handle status update from signal."""
        if hasattr(self, "status_label"):
            self.status_label.setText(f"Logged in as {self.username}\n\n{message}")

    # ============================================================
    # System Tray
    # ============================================================

    def hide_to_tray(self):
        """Hide window to system tray."""
        hide_to_tray(self, self.tray_icon)

    def show_from_tray(self):
        """Show window from system tray (thread-safe via signal)."""
        self.show_window_signal.emit()

    def on_show_window(self):
        """Handle window show from signal."""
        self.show()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_from_tray()

    def changeEvent(self, event):
        """Handle window state changes."""
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                event.ignore()
                self.hide_to_tray()
                return
        super().changeEvent(event)

    # ============================================================
    # Session Setup Button Management
    # ============================================================

    def add_setup_session_button(self, track):
        """Add a button to setup session (thread-safe via signal)."""
        self.add_session_button_signal.emit(track)

    def on_add_session_button(self, track):
        """Handle session button addition from signal."""
        setup_session_btn = QPushButton(f"Setup Session for {TRACK_NAMES.get(track, track)}")
        setup_session_btn.setMinimumHeight(32)
        setup_session_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        setup_session_btn.clicked.connect(self.setup_session)
        self.layout.insertWidget(self.layout.count() - 1, setup_session_btn)
        self.session_button = setup_session_btn

    def add_check_leaderboard_button(self):
        """Add a button to check for leaderboard (thread-safe via signal)."""
        self.add_check_lb_button_signal.emit()

    def check_for_leaderboard(self):
        """When pressed, checks current track for leaderboard and adds setup button if found."""
        check_button = QPushButton("Check for Leaderboard")
        check_button.setMinimumHeight(32)
        check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        check_button.clicked.connect(self.on_check_for_leaderboard)
        self.layout.insertWidget(self.layout.count() - 1, check_button)
        self.session_button = check_button

    def on_check_for_leaderboard(self):
        """Handle check for leaderboard button press."""
        lb_info = self.check_track_for_lb()
        self.remove_session_button()
        if lb_info:
            self.update_status("Click the button below to setup the session for recording.")
            

            self.add_setup_session_button(lb_info["track"])
            self.setup_session_button_track = lb_info

            self.check_for_setup_session = True
        else:
            self.update_status("LMU Connected. No track with leaderboard detected. Please select a track with a leaderboard.")
            self.check_for_setup_session = True

    def remove_session_button(self):
        """Remove session button (thread-safe via signal)."""
        self.remove_session_button_signal.emit()

    def on_remove_session_button(self):
        """Handle session button removal from signal."""
        if self.session_button:
            self.session_button.deleteLater()
            self.session_button = None

    # ============================================================
    # OAuth Authentication
    # ============================================================

    def open_oauth(self):
        """Start OAuth login flow."""
        logger.info("Starting OAuth flow")
        state = secrets.token_urlsafe(24)
        url = self.backend.get_discord_oauth_url(state)

        if not url:
            self.status_label.setText("Failed to connect to server")
            return

        def on_login(code, name):
            self.oauth_result.emit(code, name)

        self.oauth_server = LocalCallbackServer(OAUTH_CALLBACK_PORT, state, on_login)

        try:
            self.oauth_server.start()
            webbrowser.open(url)
            self.status_label.setText("Opening browser...\nWaiting for login")
        except OSError as e:
            logger.error("OAuth server failed: %s", e)
            self.status_label.setText("Failed to start login server")
            self.oauth_server = None

    def on_oauth_result(self, code, name):
        """Handle OAuth completion."""
        logger.info("OAuth completed for %s", name)
        save_token(code)

        self.logged_in = True
        self.token = code
        self.username = name

        # Initialize logic with new credentials
        self._init_logic()

        if self.oauth_server:
            self.oauth_server.stop()
            self.oauth_server = None

        self.clear_layout()
        self.add_logged_in_ui()
        self.raise_()
        self.activateWindow()

    def logout(self):
        """Handle logout."""
        logger.info("Logging out")

        if self.token:
            if not self.backend.logout_user(self.token):
                if hasattr(self, 'status_label'):
                    self.status_label.setText(f"Logged in as {self.username}\n\nLogout failed. Try again.")
                return

        delete_token()
        self.logged_in = False
        self.token = None
        self.username = None
        self.validator = None
        self.recorder = None

        self.clear_layout()
        self.add_login_ui()
        logger.info("Logged out")

    # ============================================================
    # Session Setup
    # ============================================================

    def setup_session(self):
        """Setup session weather and conditions."""
        res = self.lmu.set_session(
            self.setup_session_button_track["weather"], 
            self.setup_session_button_track["tod"]
        )

        if res is not None:
            play_error_sound()
            return self.update_status(f"Failed to setup session. Reason: {res}.")

        self.update_status("Session setup successfully! Waiting for session start...")

        dont_show_popup = self.settings.value("dont_show_load_session_popup", False, type=bool)
        if not dont_show_popup:
            self.load_session_popup.exec()


    def check_track_for_lb(self):
        """Check if current track has a leaderboard."""
        session = self.lmu.get_session_state()
        if not session:
            return None

        track = session.get("loadingStatus", {}).get("track", {}).get("sceneDesc")
        if not track:
            return None
        
        if track == self.setup_session_button_track or track == self.track:
            return None
        
        self.track = track

        lb_info = self.backend.get_lb_info(track)
        return lb_info

    # ============================================================
    # LMU Polling & Session Management
    # ============================================================
    def poll_lmu(self):
        """Poll for LMU connection and session."""
        logger.info("Polling for LMU...")

        while not self.lmu.attempt_connection():
            threading.Event().wait(POLL_INTERVAL)

        logger.info("LMU connected")
        self.update_status("LMU connected. Waiting for session...")

        self.track = None  # Reset track to detect new session
        self.add_check_leaderboard_button()

        while True:
            state = self.lmu.get_session_info()

            if state is False:
                logger.warning("LMU disconnected")
                self.update_status("Waiting for LMU...")
                self.poll_lmu()
                return

            if state and state.get("inControlOfVehicle"):
                logger.info("Session started")
                self.update_status("Session started!")
                break
            elif self.check_for_setup_session:
                track = self.check_track_for_lb()

                if track:
                    logger.info("Track with LB detected: %s", track["track"])

                    self.update_status("Click the button below to setup the session for recording.")
        
                    self.remove_session_button()
                    
                    self.add_setup_session_button(track["track"])
                    self.setup_session_button_track = track

            threading.Event().wait(POLL_INTERVAL)

        self.launch_session()

    def wait_for_session_end(self):
        """Wait for session to end then resume polling."""
        logger.info("Waiting for session end...")

        while True:
            state = self.lmu.get_session_info()
            if not state.get("inControlOfVehicle", False):
                logger.info("Session ended")
                self.update_status("Session ended. Waiting for new session...")
                self.poll_lmu()
                return
            threading.Event().wait(POLL_INTERVAL)

    def start_end_watcher(self):
        """Start thread to watch for session end."""
        threading.Thread(target=self.wait_for_session_end, daemon=True).start()

    # ============================================================
    # Session Validation & Recording
    # ============================================================

    def on_validation_error(self, message):
        """Handle validation error."""
        self.update_status(message)
        logger.info("Validation error: %s", message)

        self.show_from_tray()
        flash_window(self.winId())
        play_error_sound()
        self.start_end_watcher()

    def launch_session(self):
        """Validate session and prepare for recording."""
        logger.info("Launching session handler")

        # Use validator to check all conditions
        success, error_msg, lb_info, car, track = self.validator.validate_session(
            self.update_status
        )

        if not success:
            return self.on_validation_error(error_msg)

        # Store session info
        self.car = car
        self.track = track

        logger.info("All conditions met")
        self.update_status("Ready to record!")
        play_info_sound()
        self.show_from_tray()
        self.show_record_dialog.emit(lb_info)

    def on_show_record_dialog(self, lb_info):
        """Show record confirmation dialog."""
        reply = QMessageBox.question(
            self, "Record Session", "Do you want to record this session?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        def on_error(message):
            self.on_validation_error(message)

        if reply == QMessageBox.StandardButton.Yes:
            logger.info("Recording session")
            self.update_status("Recording...")
            self.hide_to_tray()
            
            # Start recording using the recorder
            self.recorder.start_recording(
                track=self.track,
                car=self.car,
                fixed_setup=lb_info.get("fixed_setup", False),
                update_callback=self.update_status,
                on_session_end=self.poll_lmu,
                on_disconnect=self.poll_lmu,
                on_error=on_error
            )
        else:
            self.update_status("Recording cancelled. Waiting for session end...")
            self.start_end_watcher()
