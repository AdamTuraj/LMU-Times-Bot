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

import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("recorder")

BASE_URL = "<LMU_URL>"
TIMEOUT = 5


class LMU:
    """Client for the LMU (Le Mans Ultimate) local API."""

    def __init__(self, base_url=BASE_URL, timeout=TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.connected = False

    def get(self, endpoint):
        """Make a GET request. Returns JSON, False for connection error, None on other errors."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                return False
            return None
        except requests.ConnectionError:
            self.connected = False
            return False
        except Exception:
            return None
        
    def post(self, endpoint, data=None, json=None, headers=None):
        """Make a POST request. Returns JSON, False for connection error, None on other errors."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.post(url, data=data, json=json, headers=headers, timeout=self.timeout)
            if 200 <= response.status_code < 300:
                return response.json() if response.content else {}
            if response.status_code == 404:
                return False
            return None
        except requests.ConnectionError:
            self.connected = False
            return False
        except Exception:
            return None
        
    def update_weather(self, node, setting, value, current_weather):
        """Set weather conditions. Expects node (e.g. 'NODE_25'), setting (e.g. 'temperature'), and value."""
        current_data = current_weather.get(setting, {}).get("currentValue")

        if current_data is None:
            logger.warning("Current value for %s at node %s not found in weather data", setting, node)
            return "Failed to set weather: current value not found"
        
        if current_data == value:
            logger.info("Weather setting %s at node %s already at desired value %s", setting, node, value)
            return None

        logger.info("Updating weather: node=%s, setting=%s, value=%s (current: %s)", node, setting, value, current_data)

        url = f"rest/sessions/weather/PRACTICE/{node}/{setting}"
        res = self.post(url, data=str(value - current_data), headers={"Content-Type": "text/plain"})

        if res is not None and res.get(setting, {}).get("currentValue", None) == value:
            logger.info("Weather setting updated successfully")
            return None
        else:
            logger.warning("Failed to set weather setting. Response: %s", res)
            return "Weather setting update failed"
        
    def set_session_setting(self, session_setting, value, expected):
        """Set a session setting. Expects the setting name (e.g. 'SESSSET_practice1_starting_time') and the value."""
        url = "rest/sessions/settings"
        res = self.post(url, json={"sessionSetting": session_setting, "value": int(value)})

        if res is not None and res.get("currentValue", None) == int(expected):
            logger.info("Session setting %s updated successfully to %s", session_setting, res["currentValue"])
            return None
        else:
            logger.warning("Failed to set session setting %s by %s. Response: %s", session_setting, value, res)
            return "Session setting update failed"

    def attempt_connection(self):
        """Check if LMU is running."""
        try:
            response = requests.get(f"{self.base_url}/swagger-schema.json", timeout=self.timeout)
            self.connected = response.status_code == 200
            if self.connected:
                logger.info("Connected to LMU")
            return self.connected
        except Exception:
            return False

    def get_session_state(self):
        """Get navigation/session state."""
        return self.get("navigation/state")

    def get_session_info(self):
        """Get game state info."""
        return self.get("rest/sessions/GetGameState")

    def get_standings(self):
        """Get race/practice standings."""
        data = self.get("rest/watch/standings")
        if data == []:
            return False
        return data

    def get_weather(self):
        """Get weather conditions."""
        return self.get("rest/sessions/weather")
    
    def get_grip_level(self):
        """Get current grip level."""
        data = self.get("rest/sessions")

        if data and "SESSSET_pract1_realroad_init" in data:
            return data["SESSSET_pract1_realroad_init"].get("currentValue")
        return None
    
    def get_active_setup(self):
        """Get current setups."""
        return self.get("rest/garage/summary")
    
    def set_session(self, weather, time):
        """Sets up the session. Expects a dict with keys: temperature, rain, condition, grip_level and the time."""
        
        current_data = self.get("rest/sessions")

        # Practice only session
        logger.info("Setting practice only session.")
        current_pract1 = current_data.get("SESSSET_pract1", {}).get("currentValue")
        if current_pract1 is None:
            logger.warning("Current practice session value not found in session data")
            return "Current practice session value not found"
        
        if current_pract1 == 1:
            logger.info("Practice session already active")
        else:
            res = self.set_session_setting("SESSSET_pract1", 1, 1)
            if res is not None:
                return res
            
        # Disabling qualifying
        logger.info("Disabling qualifying")
        current_qual = current_data.get("SESSSET_num_qual_sessions", {}).get("currentValue")
        if current_qual is None:
            logger.warning("Current qualifying session value not found in session data")
            return "Current qualifying session value not found"
        
        if current_qual == 0:
            logger.info("Qualifying session already disabled")
        else:
            res = self.set_session_setting("SESSSET_num_qual_sessions", -current_qual, 0)
            if res is not None:
                return res
        
        # Disabling race
        logger.info("Disabling race")
        current_race = current_data.get("SESSSET_num_race_sessions", {}).get("currentValue")
        if current_race is None:
            logger.warning("Current race session value not found in session data")
            return "Current race session value not found"
        
        if current_race == 0:
            logger.info("Race session already disabled")
        else:
            res = self.set_session_setting("SESSSET_num_race_sessions", -current_race, 0)
            if res is not None:
                return res
            
        # Set timescale to static
        logger.info("Setting timescale to static (0)")
        current_timescale = current_data.get("SESSSET_realroad_timescale_practice", {}).get("currentValue")
        if current_timescale is None:
            logger.warning("Current timescale value not found in session data")
            return "Current timescale value not found"
        
        if current_timescale == 0:
            logger.info("Timescale already at static (0)")
        else:
            res = self.set_session_setting("SESSSET_realroad_timescale_practice", -current_timescale, 0)
            if res is not None:
                return res

        # Set time
        logger.info("Setting time of day to %s", time)

        current_time = current_data.get("SESSSET_practice1_starting_time", {}).get("currentValue")
        if current_time is None:
            logger.warning("Current time not found in session data")
            return "Current time not found"
        
        if current_time == time:
            logger.info("Time of day already at desired value %s", time)
        else:
            res = self.set_session_setting("SESSSET_practice1_starting_time", time - current_time, time)
            if res is not None:
                return res

        # Set grip level
        target_grip = weather.get("grip_level", 0)

        logger.info("Setting grip level to %s", target_grip)

        current_grip = current_data.get("SESSSET_pract1_realroad_init", {}).get("currentValue")
        if current_grip is None:
            logger.warning("Current grip level not found in session data")
            return "Current grip level not found"
        
        if current_grip == target_grip:
            logger.info("Grip level already at desired value %s", current_grip)
        else:
            res = self.set_session_setting("SESSSET_pract1_realroad_init", target_grip - current_grip, target_grip)
            if res is not None:
                return res

        # Set weather for all nodes
        logger.info("Setting weather conditions for all nodes")

        current_weather = self.get_weather()["PRACTICE"]

        nodes = ["START", "NODE_25", "NODE_50", "NODE_75", "FINISH"]
        for n in nodes:
            res = self.update_weather(n, "WNV_SKY", weather.get("condition", 0), current_weather[n])
            if res is not None:
                return res
            
            res = self.update_weather(n, "WNV_RAIN_CHANCE", weather.get("rain", 0), current_weather[n])
            if res is not None:
                return res

            res = self.update_weather(n, "WNV_TEMPERATURE", weather.get("temperature", 25), current_weather[n])
            if res is not None:
                return res
            
        logger.info("Weather setup successfully")

        return None
