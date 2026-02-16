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

import ctypes
import logging
import os
import sys
import keyring
import winsound
from pathlib import Path

from PyQt6.QtWidgets import QSystemTrayIcon

from config.settings import (
    APP_NAME,
    SERVICE_NAME,
    KEYRING_USERNAME,
    WEATHER_CONDITIONS,
    TEMP_TOLERANCE,
    RAIN_TOLERANCE,
)


def get_log_path() -> Path:
    """Get the path to the log file."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")

    log_dir = Path(base) / APP_NAME / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return log_dir / "app.log"


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

    log_path = get_log_path()
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    log.addHandler(file_handler)

    return log


logger = setup_logging()


def flash_window(hwnd):
    """Flash the taskbar button for a window."""
    FLASHW_ALL = 0x00000003
    FLASHW_TIMERNOFG = 0x0000000C

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("hwnd", ctypes.c_void_p),
            ("dwFlags", ctypes.c_uint),
            ("uCount", ctypes.c_uint),
            ("dwTimeout", ctypes.c_uint),
        ]

    info = FLASHWINFO()
    info.cbSize = ctypes.sizeof(FLASHWINFO)
    info.hwnd = int(hwnd)
    info.dwFlags = FLASHW_ALL | FLASHW_TIMERNOFG
    info.uCount = 0
    info.dwTimeout = 0
    ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))


def play_info_sound():
    """Play the Windows information sound."""
    winsound.MessageBeep(winsound.MB_ICONASTERISK)


def play_error_sound():
    """Play the Windows error sound."""
    winsound.MessageBeep(winsound.MB_ICONHAND)


def hide_to_tray(window, tray_icon):
    """Hide the window to the system tray."""
    window.hide()
    if tray_icon and tray_icon.isVisible():
        tray_icon.showMessage(
            APP_NAME,
            "Application minimized to tray",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )


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
