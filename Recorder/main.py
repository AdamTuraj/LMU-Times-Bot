import json
import logging
import secrets
import sys
import threading
import webbrowser
from pathlib import Path

import keyring
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Backend import Backend
from LMU import LMU
from TokenServer import LocalCallbackServer

# Constants
APP_NAME = "LMU Times Recorder"
SERVICE_NAME = "LMUTimesRecorder"
KEYRING_USERNAME = "user_token"
OAUTH_CALLBACK_PORT = 54783
POLL_INTERVAL = 5.0
TEMP_TOLERANCE = 1.0
RAIN_TOLERANCE = 5.0

CAR_CLASSES = {"LMGT3": 0, "LMGTE": 1, "LMP3": 2, "LMP2": 3, "ELMS2025": 4, "Hyper": 5}
CAR_CLASS_NAMES = {v: k for k, v in CAR_CLASSES.items()}

WEATHER_CONDITIONS = {
    0: "Clear", 1: "Light Clouds", 2: "Partially Cloudy", 3: "Mostly Cloudy",
    4: "Overcast", 5: "Cloudy & Drizzle", 6: "Cloudy & Light Rain",
    7: "Overcast & Light Rain", 8: "Overcast & Rain", 9: "Overcast & Heavy Rain",
    10: "Overcast & Storm",
}


def setup_logging():
    """Set up logging with file and console handlers."""
    log = logging.getLogger("recorder")
    if log.handlers:
        return log

    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    log.addHandler(console)

    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "recorder.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    log.addHandler(file_handler)

    return log


logger = setup_logging()


def get_condition_name(condition):
    """Get weather condition name from code."""
    if isinstance(condition, int):
        return WEATHER_CONDITIONS.get(condition, f"Unknown ({condition})")
    return str(condition)


def save_token(token):
    """Save token to keyring."""
    try:
        keyring.set_password(SERVICE_NAME, KEYRING_USERNAME, token)
        logger.info("Token saved")
    except Exception as e:
        logger.error("Failed to save token: %s", e)


def delete_token():
    """Delete token from keyring."""
    try:
        keyring.delete_password(SERVICE_NAME, KEYRING_USERNAME)
        logger.info("Token deleted")
    except Exception:
        pass


def get_token():
    """Get token from keyring."""
    try:
        return keyring.get_password(SERVICE_NAME, KEYRING_USERNAME)
    except Exception:
        return None


def weather_matches(session_weather, required_weather):
    """Check if session weather matches required weather within tolerances."""
    req_condition = required_weather.get("condition", required_weather.get("Sky", ""))
    req_temp = required_weather.get("temperature", required_weather.get("Temperature", 0))
    req_rain = required_weather.get("rain", required_weather.get("RainChance", 0))

    for i, w in enumerate(session_weather):
        if w["condition"] != req_condition:
            return False, i
        if abs(w["temperature"] - req_temp) > TEMP_TOLERANCE:
            return False, i
        if abs(w["rain"] - req_rain) > RAIN_TOLERANCE:
            return False, i

    return True, None


class MainWindow(QMainWindow):
    """Main application window."""

    oauth_result = pyqtSignal(str, str)
    show_record_dialog = pyqtSignal(dict, dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        logger.info("Starting %s", APP_NAME)

        self.backend = Backend()
        self.lmu = LMU()
        self.oauth_server = None

        self.token = None
        self.username = None
        self.logged_in = False

        self.fastest_lap = None
        self.track = None
        self.car = None

        # Try to restore session
        self.token = get_token()
        if self.token:
            self.username = self.backend.get_username(self.token)
            if self.username:
                self.logged_in = True
                logger.info("Session restored for %s", self.username)
            else:
                delete_token()
                self.token = None

        # Setup UI
        self.layout = QVBoxLayout()
        self.setup_ui()

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        self.oauth_result.connect(self.on_oauth_result)
        self.show_record_dialog.connect(self.on_show_record_dialog)

    def setup_ui(self):
        """Build the UI based on login state."""
        if self.logged_in:
            self.add_logged_in_ui()
        else:
            self.add_login_ui()

    def add_logged_in_ui(self):
        """Add UI for logged in state."""
        self.status_label = QLabel(f"Logged in as {self.username}\nWaiting for LMU...")
        self.layout.addWidget(self.status_label)

        logout_btn = QPushButton("Logout")
        logout_btn.clicked.connect(self.logout)
        self.layout.addWidget(logout_btn)

        threading.Thread(target=self.poll_lmu, daemon=True).start()

    def add_login_ui(self):
        """Add UI for logged out state."""
        login_btn = QPushButton("Login with Discord")
        login_btn.clicked.connect(self.open_oauth)
        self.layout.addWidget(login_btn)

        self.status_label = QLabel("Not logged in.")
        self.layout.addWidget(self.status_label)

    def clear_layout(self):
        """Clear all widgets from layout."""
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def update_status(self, message):
        """Update status label."""
        if hasattr(self, "status_label"):
            self.status_label.setText(f"Logged in as {self.username}\n{message}")

    # OAuth
    def open_oauth(self):
        """Start OAuth login flow."""
        logger.info("Starting OAuth flow")
        state = secrets.token_urlsafe(24)
        url = self.backend.get_discord_oauth_url(state)

        if not url:
            self.status_label.setText("Failed to get OAuth URL")
            return

        def on_login(code, name):
            self.oauth_result.emit(code, name)

        self.oauth_server = LocalCallbackServer(OAUTH_CALLBACK_PORT, state, on_login)

        try:
            self.oauth_server.start()
            webbrowser.open(url)
            self.status_label.setText("Waiting for Discord login...")
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

        if self.oauth_server:
            self.oauth_server.stop()
            self.oauth_server = None

        self.clear_layout()
        self.add_logged_in_ui()
        self.raise_()
        self.activateWindow()

    # LMU Polling
    def poll_lmu(self):
        """Poll for LMU connection and session."""
        logger.info("Polling for LMU...")

        while not self.lmu.attempt_connection():
            threading.Event().wait(POLL_INTERVAL)

        logger.info("LMU connected")
        self.update_status("LMU connected. Waiting for session...")

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

    def launch_session(self):
        """Handle session start and validate conditions."""
        logger.info("Launching session handler")

        # Get standings
        standings = None
        for attempt in range(10):
            standings = self.lmu.get_standings()
            if standings:
                break
            self.update_status(f"Loading... ({attempt + 1}/10)")
            threading.Event().wait(POLL_INTERVAL)

        if not standings:
            self.update_status("Could not get standings. Waiting for session end...")
            self.start_end_watcher()
            return

        if len(standings) > 1:
            self.update_status("Multiple drivers detected. Only one driver allowed.")
            return

        # Get session state
        session = self.lmu.get_session_state()
        if not session:
            logger.error("Failed to get session state")
            return

        # Get car info
        car_info = json.loads(session["loadingStatus"]["loadingData"])["selectedCar"]["classes"]
        if car_info[0] == "Default_Custom_Livery":
            self.car = car_info[2].replace("_", " ")
        else:
            self.car = car_info[1].replace("_", " ")

        # Check practice session
        game_session = session.get("state", {}).get("gameSession")
        if game_session != "PRACTICE1":
            self.update_status("Not in practice. Waiting for session end...")
            self.start_end_watcher()
            return

        # Get leaderboard info
        self.track = session["loadingStatus"]["track"]["sceneDesc"]
        lb_info = self.backend.get_lb_info(self.track)

        if not lb_info:
            self.update_status("No leaderboard for this track. Waiting for session end...")
            self.start_end_watcher()
            return

        # Check car class
        classes = lb_info.get("classes", [])
        car_class = standings[0].get("carClass", "")
        class_num = CAR_CLASSES.get(car_class)

        if class_num is None or class_num not in classes:
            allowed = [CAR_CLASS_NAMES.get(c, "?") for c in classes]
            self.update_status(f"Wrong class! Yours: {car_class}\nAllowed: {', '.join(allowed)}")
            self.start_end_watcher()
            return

        # Check weather
        weather = self.get_weather()
        if not weather:
            self.update_status("Error reading weather. Waiting for session end...")
            self.start_end_watcher()
            return

        matches, bad_idx = weather_matches(weather, lb_info["weather"])
        if not matches:
            req = lb_info["weather"]
            bad = weather[bad_idx] if bad_idx is not None else weather[0]
            self.update_status(
                f"Weather incorrect!\n"
                f"Required: {get_condition_name(req.get('condition'))}, "
                f"{req.get('temperature')}°C, {req.get('rain')}%\n"
                f"Slot {(bad_idx or 0) + 1}: {get_condition_name(bad['condition'])}, "
                f"{bad['temperature']}°C, {bad['rain']}%"
            )
            self.start_end_watcher()
            return

        logger.info("All conditions met")
        self.update_status("Ready to record!")
        self.show_record_dialog.emit(session, lb_info)

    def get_weather(self):
        """Get weather data from LMU."""
        try:
            weather_list = self.lmu.get_weather()["PRACTICE"].values()
            return [
                {
                    "condition": w["WNV_SKY"]["currentValue"],
                    "temperature": w["WNV_TEMPERATURE"]["currentValue"],
                    "rain": w["WNV_RAIN_CHANCE"]["currentValue"],
                }
                for w in weather_list
            ][::-1]
        except Exception as e:
            logger.error("Failed to get weather: %s", e)
            return []

    # Recording
    def on_show_record_dialog(self, session, lb_info):
        """Show record confirmation dialog."""
        reply = QMessageBox.question(
            self, "Record Session", "Do you want to record this session?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info("Recording session")
            self.update_status("Recording...")
            threading.Thread(target=self.record_session, daemon=True).start()
        else:
            self.update_status("Recording cancelled. Waiting for session end...")
            self.start_end_watcher()

    def record_session(self):
        """Record lap times during session."""
        logger.info("Recording session...")

        while True:
            state = self.lmu.get_standings()

            if state is False:
                logger.warning("LMU disconnected during recording")
                self.update_status("Waiting for LMU...")
                self.poll_lmu()
                return

            if state is None:
                threading.Event().wait(POLL_INTERVAL)
                continue

            lap = state[0].get("bestLapTime")
            s1 = state[0].get("bestLapSectorTime1")
            s2 = state[0].get("bestLapSectorTime2")

            if not lap or lap < 10:
                threading.Event().wait(POLL_INTERVAL)
                continue

            if self.fastest_lap and lap >= self.fastest_lap:
                threading.Event().wait(POLL_INTERVAL)
                continue

            if not s1 or not s2:
                threading.Event().wait(POLL_INTERVAL)
                continue

            logger.info("Lap: %.3f (S1: %.3f, S2: %.3f)", lap, s1, s2)
            self.fastest_lap = lap
            self.update_status(f"Recorded: {lap:.3f}s\nWaiting for next lap...")

            lap_data = {"sector1": s1, "sector2": s2, "lap": lap}
            res = self.backend.submit_time(
                self.token, lap_data, self.track, self.car,
                state[0].get("driverName", "Unknown")
            )

            if res is False:
                self.update_status("Submission failed. Blacklisted. Waiting for session end...")
                self.start_end_watcher()
                return

            threading.Event().wait(POLL_INTERVAL)

    # Logout
    def logout(self):
        """Handle logout."""
        logger.info("Logging out")

        if self.token:
            if not self.backend.logout_user(self.token):
                self.status_label.setText("Logout failed. Try again.")
                return

        delete_token()
        self.logged_in = False
        self.token = None
        self.username = None

        self.clear_layout()
        self.add_login_ui()
        logger.info("Logged out")


def main():
    """Application entry point."""
    logger.info("=" * 50)
    logger.info("Starting %s", APP_NAME)
    logger.info("=" * 50)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
