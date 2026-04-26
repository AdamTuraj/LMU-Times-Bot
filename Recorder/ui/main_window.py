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

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget
)

from config.settings import (
    __version__,
    APP_NAME,
    CAR_CLASS_NAMES,
    OAUTH_CALLBACK_PORT,
    POLL_INTERVAL,
    TRACK_NAMES,
)
from config.helpers import (
    logger,
    flash_window,
    play_error_sound,
    hide_to_tray,
    save_token,
    delete_token,
    get_token,
)
from ui.ui_styles import get_stylesheet
from utils.backend import Backend
from utils.lmu import LMU
from utils.token_server import LocalCallbackServer
from utils.resources import get_embedded_icon
from core.session_recorder import SessionRecorder


class MainWindow(QMainWindow):
    # Signals for thread-safe UI updates
    oauth_result = pyqtSignal(str, str)
    update_status_signal = pyqtSignal(str)
    show_window_signal = pyqtSignal()
    leaderboards_loaded_signal = pyqtSignal(object)
    cars_loaded_signal = pyqtSignal(object, str)
    lmu_connected_signal = pyqtSignal(bool)
    session_load_result_signal = pyqtSignal(bool, str)
    set_loading_signal = pyqtSignal(bool, str)
    start_recording_signal = pyqtSignal()
    recording_error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(420, 320)
        self.resize(460, 360)
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
        self.recorder = None
        
        # OAuth
        self.oauth_server = None
        self.token = None
        self.username = None
        self.logged_in = False

        # Session state
        self.track = None
        self.car = None
        self.leaderboards = []
        self.selected_leaderboard = None
        self.valid_cars = []
        self.selected_car = None
        self.lmu_connected = False
        self.loading_session = False

        # Try to restore session
        self._restore_session()

        # Setup system tray
        self._setup_system_tray()

        # Setup UI
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(8)
        self._connect_signals()
        self.setup_ui()

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

    def _connect_signals(self):
        """Connect Qt signals before background threads can emit them."""
        self.oauth_result.connect(self.on_oauth_result)
        self.update_status_signal.connect(self.on_update_status)
        self.show_window_signal.connect(self.on_show_window)
        self.leaderboards_loaded_signal.connect(self.on_leaderboards_loaded)
        self.cars_loaded_signal.connect(self.on_cars_loaded)
        self.lmu_connected_signal.connect(self.on_lmu_connected_changed)
        self.session_load_result_signal.connect(self.on_session_load_result)
        self.set_loading_signal.connect(self.on_set_loading)
        self.start_recording_signal.connect(self.launch_session)
        self.recording_error_signal.connect(self.on_recording_error)

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
        """Initialize recorder with current credentials."""
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
        
        self.status_label = QLabel(f"Logged in as {self.username}\nLoading leaderboards...")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        font = QFont()
        font.setPointSize(9)
        self.status_label.setFont(font)
        self.layout.addWidget(self.status_label)

        self.leaderboard_label = QLabel("Leaderboard")
        self.leaderboard_label.setObjectName("fieldLabel")
        self.layout.addWidget(self.leaderboard_label)

        self.leaderboard_combo = QComboBox()
        self.leaderboard_combo.setEnabled(False)
        self.leaderboard_combo.addItem("Loading leaderboards...")
        self.leaderboard_combo.currentIndexChanged.connect(self.on_leaderboard_selected)
        self.layout.addWidget(self.leaderboard_combo)

        self.car_label = QLabel("Car")
        self.car_label.setObjectName("fieldLabel")
        self.layout.addWidget(self.car_label)

        self.car_combo = QComboBox()
        self.car_combo.setEnabled(False)
        self.car_combo.addItem("Select a leaderboard first")
        self.car_combo.currentIndexChanged.connect(self.on_car_selected)
        self.layout.addWidget(self.car_combo)

        self.load_session_btn = QPushButton("Load Session")
        self.load_session_btn.setMinimumHeight(32)
        self.load_session_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_session_btn.setEnabled(False)
        self.load_session_btn.clicked.connect(self.load_selected_session)
        self.layout.addWidget(self.load_session_btn)

        self.loading_indicator = QProgressBar()
        self.loading_indicator.setRange(0, 0)
        self.loading_indicator.setTextVisible(False)
        self.loading_indicator.hide()
        self.layout.addWidget(self.loading_indicator)

        self.layout.addStretch(1)

        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("secondaryButton")
        logout_btn.setMinimumHeight(32)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(self.logout)
        self.layout.addWidget(logout_btn)

        threading.Thread(target=self.load_leaderboards, daemon=True).start()
        threading.Thread(target=self.poll_lmu, daemon=True).start()

    def add_login_ui(self):
        """Add UI for logged out state."""
        self.layout.addStretch(2)

        login_btn = QPushButton("Login with Discord")
        login_btn.setObjectName("loginButton")
        login_btn.setMinimumWidth(240)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self.open_oauth)
        self.layout.addWidget(login_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("")
        self.status_label.setObjectName("loginStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()
        self.layout.addStretch(3)

    def clear_layout(self):
        """Clear all widgets from layout."""
        self.leaderboard_combo = None
        self.car_combo = None
        self.load_session_btn = None
        self.loading_indicator = None
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def load_leaderboards(self):
        """Fetch active leaderboards from the backend."""
        leaderboards = self.backend.get_leaderboards()
        self.leaderboards_loaded_signal.emit(leaderboards)

    def on_leaderboards_loaded(self, leaderboards):
        """Populate the leaderboard selector."""
        self.leaderboards = leaderboards or []
        if not hasattr(self, "leaderboard_combo") or self.leaderboard_combo is None:
            return

        self.leaderboard_combo.blockSignals(True)
        self.leaderboard_combo.clear()

        if not self.leaderboards:
            self.leaderboard_combo.addItem("No active leaderboards")
            self.leaderboard_combo.setEnabled(False)
            self.selected_leaderboard = None
            self.update_status("No active leaderboards are available.")
        else:
            for leaderboard in self.leaderboards:
                track = leaderboard.get("track", "")
                label = TRACK_NAMES.get(track, track)
                self.leaderboard_combo.addItem(label, leaderboard)
            self.leaderboard_combo.setEnabled(not self.loading_session)
            self.leaderboard_combo.setCurrentIndex(0)

        self.leaderboard_combo.blockSignals(False)

        if self.leaderboards:
            self.on_leaderboard_selected(self.leaderboard_combo.currentIndex())

    def on_leaderboard_selected(self, index):
        """Load valid cars for the selected leaderboard."""
        if not hasattr(self, "leaderboard_combo") or self.leaderboard_combo is None:
            return

        leaderboard = self.leaderboard_combo.itemData(index)
        self.selected_leaderboard = leaderboard if isinstance(leaderboard, dict) else None
        self.selected_car = None
        self.valid_cars = []

        self._set_car_combo_message("Waiting for LMU..." if not self.lmu_connected else "Loading cars...")
        self._update_load_button_state()

        if self.selected_leaderboard and self.lmu_connected and not self.loading_session:
            threading.Thread(
                target=self.load_cars_for_leaderboard,
                args=(self.selected_leaderboard,),
                daemon=True
            ).start()

    def on_car_selected(self, index):
        """Store the selected car/livery."""
        if not hasattr(self, "car_combo") or self.car_combo is None:
            return

        car = self.car_combo.itemData(index)
        self.selected_car = car if isinstance(car, dict) else None
        self._update_load_button_state()

    def load_cars_for_leaderboard(self, leaderboard):
        """Fetch and filter LMU vehicles for the selected leaderboard."""
        try:
            cars = self.get_valid_cars(leaderboard)
            self.cars_loaded_signal.emit(cars, "")
        except Exception as e:
            logger.exception("Failed to load cars")
            self.cars_loaded_signal.emit([], str(e))

    def on_cars_loaded(self, cars, error):
        """Populate the car selector."""
        if not hasattr(self, "car_combo") or self.car_combo is None:
            return

        self.valid_cars = cars or []
        self.car_combo.blockSignals(True)
        self.car_combo.clear()

        if error:
            self.car_combo.addItem("Failed to load cars")
            self.car_combo.setEnabled(False)
            self.update_status(f"Failed to load cars: {error}")
        elif not self.valid_cars:
            self.car_combo.addItem("No valid cars found")
            self.car_combo.setEnabled(False)
            self.update_status("No valid cars found for this leaderboard class.")
        else:
            for car in self.valid_cars:
                self.car_combo.addItem(self.format_car_label(car), car)
            self.car_combo.setEnabled(not self.loading_session)
            self.car_combo.setCurrentIndex(0)

        self.car_combo.blockSignals(False)
        self.on_car_selected(self.car_combo.currentIndex())

    def _set_car_combo_message(self, message):
        if not hasattr(self, "car_combo") or self.car_combo is None:
            return
        self.car_combo.blockSignals(True)
        self.car_combo.clear()
        self.car_combo.addItem(message)
        self.car_combo.setEnabled(False)
        self.car_combo.blockSignals(False)

    def get_valid_cars(self, leaderboard):
        """Return the first livery for each valid car model in LMU vehicle order."""
        allowed_class_names = [
            CAR_CLASS_NAMES.get(class_id, class_id)
            for class_id in leaderboard.get("classes", [])
        ]

        valid = []
        seen = set()
        for car in self.lmu.get_all_vehicles():
            if car.get("isOwned") is False:
                continue

            classes = car.get("classes") or []
            if allowed_class_names and not any(class_name in classes for class_name in allowed_class_names):
                continue

            key = car.get("sig") or car.get("vehicle") or car.get("id")
            if key in seen:
                continue
            seen.add(key)
            valid.append(car)

        return valid

    def format_car_label(self, car):
        """Build the visible car selector label."""
        model = self.car_models.get(car.get("sig"))
        if not model:
            full_path = car.get("fullPathTree") or ""
            model = full_path.split(",")[-1].strip() if full_path else None
        if not model:
            model = car.get("manufacturer") or car.get("desc") or car.get("vehicle") or car.get("id")

        return str(model)

    def _update_load_button_state(self):
        if not hasattr(self, "load_session_btn") or self.load_session_btn is None:
            return

        can_load = (
            self.lmu_connected
            and bool(self.selected_leaderboard)
            and bool(self.selected_car)
            and not self.loading_session
        )
        self.load_session_btn.setEnabled(can_load)

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

    def on_lmu_connected_changed(self, connected):
        """Handle LMU connection state changes on the UI thread."""
        self.lmu_connected = connected
        if connected:
            if self.selected_leaderboard and not self.valid_cars and not self.loading_session:
                self._set_car_combo_message("Loading cars...")
                threading.Thread(
                    target=self.load_cars_for_leaderboard,
                    args=(self.selected_leaderboard,),
                    daemon=True
                ).start()
            self._update_load_button_state()
        else:
            self.selected_car = None
            self.valid_cars = []
            self._set_car_combo_message("Waiting for LMU...")
            self._update_load_button_state()

    def on_set_loading(self, loading, message):
        """Toggle loading UI while the save is generated and loaded."""
        self.loading_session = loading

        if hasattr(self, "loading_indicator") and self.loading_indicator is not None:
            self.loading_indicator.setVisible(loading)

        if hasattr(self, "leaderboard_combo") and self.leaderboard_combo is not None:
            self.leaderboard_combo.setEnabled(not loading and bool(self.leaderboards))

        if hasattr(self, "car_combo") and self.car_combo is not None:
            self.car_combo.setEnabled(not loading and bool(self.valid_cars))

        if message:
            self.update_status(message)

        self._update_load_button_state()

    def load_selected_session(self):
        """Start LMU save generation/load for the selected leaderboard and car."""
        if not self.selected_leaderboard or not self.selected_car:
            return

        leaderboard = dict(self.selected_leaderboard)
        car = dict(self.selected_car)
        self.on_set_loading(True, "Loading session...")

        threading.Thread(
            target=self._load_selected_session_worker,
            args=(leaderboard, car),
            daemon=True
        ).start()

    def _load_selected_session_worker(self, leaderboard, car):
        success, error = self.lmu.load_generated_session(leaderboard, car)
        self.session_load_result_signal.emit(success, error or "")

    def on_session_load_result(self, success, error):
        """Handle loadGame result."""
        if success:
            self.on_set_loading(True, "Session loaded. Waiting for LMU...")
            return

        play_error_sound()
        self.on_set_loading(False, f"Failed to load session. Reason: {error}")

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
    # OAuth Authentication
    # ============================================================

    def open_oauth(self):
        """Start OAuth login flow."""
        logger.info("Starting OAuth flow")
        state = secrets.token_urlsafe(24)
        url = self.backend.get_discord_oauth_url(state)

        if not url:
            self.status_label.setText("Failed to connect to server")
            self.status_label.show()
            return

        def on_login(code, name):
            self.oauth_result.emit(code, name)

        self.oauth_server = LocalCallbackServer(OAUTH_CALLBACK_PORT, state, on_login)

        try:
            self.oauth_server.start()
            webbrowser.open(url)
            self.status_label.setText("Opening browser...\nWaiting for login")
            self.status_label.show()
        except OSError as e:
            logger.error("OAuth server failed: %s", e)
            self.status_label.setText("Failed to start login server")
            self.status_label.show()
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
        self.recorder = None
        self.leaderboards = []
        self.selected_leaderboard = None
        self.valid_cars = []
        self.selected_car = None
        self.loading_session = False

        self.clear_layout()
        self.add_login_ui()
        logger.info("Logged out")

    # ============================================================
    # LMU Polling & Session Management
    # ============================================================
    def poll_lmu(self):
        """Poll for LMU connection and session."""
        logger.info("Polling for LMU...")

        while True:
            while not self.lmu.attempt_connection():
                if self.lmu_connected:
                    self.lmu_connected_signal.emit(False)
                threading.Event().wait(POLL_INTERVAL)

            logger.info("LMU connected")
            self.lmu_connected_signal.emit(True)
            self.update_status("LMU connected. Select a leaderboard and car.")

            while True:
                state = self.lmu.get_session_info()

                if state is False:
                    logger.warning("LMU disconnected")
                    self.lmu_connected_signal.emit(False)
                    self.update_status("Waiting for LMU...")
                    break

                if state and state.get("inControlOfVehicle"):
                    logger.info("Session started")
                    self.set_loading_signal.emit(False, "Session started!")
                    break

                threading.Event().wait(POLL_INTERVAL)

            if state and state.get("inControlOfVehicle"):
                self.start_recording_signal.emit()
                return

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
    # Session Recording
    # ============================================================

    def on_recording_error(self, message):
        """Handle a recording-blocking error."""
        self.update_status(message)
        logger.info("Recording error: %s", message)

        self.show_from_tray()
        flash_window(self.winId())
        play_error_sound()
        self.start_end_watcher()

    def launch_session(self):
        """Start recording for the loaded leaderboard session."""
        logger.info("Launching session handler")

        lb_info = self.selected_leaderboard or {}
        selected_car = self.selected_car or {}
        track = lb_info.get("track")

        if not track or not selected_car:
            return self.on_recording_error("No loaded leaderboard/car selected. Waiting for session end...")

        self.car = self.car_models.get(selected_car.get("sig")) or self.format_car_label(selected_car)
        self.track = track

        def on_error(message):
            self.recording_error_signal.emit(message)

        logger.info("Recording session")
        self.update_status("Recording...")
        self.hide_to_tray()

        self.recorder.start_recording(
            track=self.track,
            car=self.car,
            fixed_setup=lb_info.get("fixed_setup", False),
            update_callback=self.update_status,
            on_session_end=self.poll_lmu,
            on_disconnect=self.poll_lmu,
            on_error=on_error
        )
