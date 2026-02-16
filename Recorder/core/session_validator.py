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

import json
import threading
from config.helpers import logger, get_condition_name, weather_matches
from config.settings import (
    POLL_INTERVAL,
    CAR_CLASSES,
    CAR_CLASS_NAMES,
    GRIP_LEVELS,
)


class SessionValidator:
    def __init__(self, lmu_client, backend_client, car_models):
        """
        Initialize the validator.

        Args:
            lmu_client: LMU API client
            backend_client: Backend API client  
            car_models: Dict of car signatures to car info
        """
        self.lmu = lmu_client
        self.backend = backend_client
        self.car_models = car_models

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

    def validate_session(self, update_callback):
        """
        Validate session conditions for recording.

        Args:
            update_callback: Function to call with status updates

        Returns:
            tuple: (success: bool, error_message: str, lb_info: dict, car: str, track: str)
        """
        logger.info("Validating session conditions")

        # Get standings
        standings = None
        for attempt in range(10):
            standings = self.lmu.get_standings()
            if standings:
                break
            update_callback(f"Loading... ({attempt + 1}/10)")
            threading.Event().wait(POLL_INTERVAL*5)

        if not standings:
            return False, "Failed to load standings. Waiting for session end...", None, None, None

        if len(standings) > 1:
            return False, "Multiple drivers detected. Only one driver allowed.", None, None, None

        # Get session state
        session = self.lmu.get_session_state()
        if not session:
            return False, "Error reading session state. Waiting for session end...", None, None, None

        # Get car info via signature lookup
        selected_car = json.loads(session["loadingStatus"]["loadingData"])["selectedCar"]
        car_sig = selected_car.get("sig", "")
        car = self.car_models.get(car_sig)
        if not car:
            return False, f"Unknown car (sig: {car_sig[:8]}...). Waiting for session end...", None, None, None

        # Check practice session
        game_session = session.get("state", {}).get("gameSession")
        if game_session != "PRACTICE1":
            return False, "Not in practice. Waiting for session end...", None, None, None

        # Get leaderboard info
        track = session["loadingStatus"]["track"]["sceneDesc"]
        lb_info = self.backend.get_lb_info(track)

        if not lb_info:
            return False, "No leaderboard for this track. Waiting for session end...", None, None, None

        # Check car class
        classes = lb_info.get("classes", [])
        car_class = standings[0].get("carClass", "")
        class_num = CAR_CLASSES.get(car_class)

        if class_num is None or class_num not in classes:
            allowed = [CAR_CLASS_NAMES.get(c, "?") for c in classes]
            error_msg = f"Wrong class! Yours: {car_class}\nAllowed: {', '.join(allowed)}"
            return False, error_msg, None, None, None

        # Check weather
        weather = self.get_weather()
        if not weather:
            return False, "Error reading weather. Waiting for session end...", None, None, None

        matches, bad_idx = weather_matches(weather, lb_info["weather"])
        if not matches:
            req = lb_info["weather"]
            bad = weather[bad_idx] if bad_idx is not None else weather[0]

            error_msg = (
                f"Weather incorrect!\n"
                f"Required: {get_condition_name(req.get('condition'))}, "
                f"{req.get('temperature')}°C, {req.get('rain')}%\n"
                f"Slot {(bad_idx or 0) + 1}: {get_condition_name(bad['condition'])}, "
                f"{bad['temperature']}°C, {bad['rain']}%"
            )
            return False, error_msg, None, None, None

        # Check grip level
        grip_level = self.lmu.get_grip_level()
        required_grip = lb_info["weather"].get("grip_level")

        if grip_level is None or required_grip is None:
            return False, "Error reading grip level. Waiting for session end...", None, None, None

        if required_grip is not None and grip_level != required_grip:
            error_msg = (
                f"Grip level incorrect!\n"
                f"Required: {GRIP_LEVELS.get(required_grip, required_grip)}\n"
                f"Current: {GRIP_LEVELS.get(grip_level, grip_level)}"
            )
            return False, error_msg, None, None, None

        logger.info("All conditions met - session valid")
        return True, None, lb_info, car, track
