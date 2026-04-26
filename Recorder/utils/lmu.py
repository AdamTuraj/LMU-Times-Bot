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
import logging
from pathlib import Path
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("recorder")

BASE_URL = "<LMU_URL>"
TIMEOUT = 5
SAVELOAD_TIMEOUT = 30
TEXT_HEADERS = {"Accept": "application/json", "Content-Type": "text/plain;charset=UTF-8"}

PRACTICE_LENGTH_MINUTES = 2880
PRACTICE_TIMER_SECONDS = 21600
WEATHER_NODES = ["START", "NODE_25", "NODE_50", "NODE_75", "FINISH"]
WEATHER_SESSIONS = ["PRACTICE"]
REALROAD_BY_GRIP = {
    0: "green",
    1: "natural",
    2: "preset:Heavy.rrbin",
    3: "preset:Light.rrbin",
    4: "preset:Medium.rrbin",
    5: "preset:Saturated.rrbin",
}
SESSION_PRESET_TEMPLATE = "session_preset_generation_template.json"


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

    @staticmethod
    def _parse_response(response):
        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            return response.text
        
    def post(self, endpoint, data=None, json=None, headers=None, timeout=None):
        """Make a POST request. Returns JSON, False for connection error, None on other errors."""
        url = f"{self.base_url}/{endpoint}"
        try:
            request_timeout = self.timeout if timeout is None else timeout
            response = requests.post(url, data=data, json=json, headers=headers, timeout=request_timeout)
            if 200 <= response.status_code < 300:
                return self._parse_response(response)
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
        res = self.post(url, data=str(value - current_data), headers=TEXT_HEADERS)

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

    def get_tracks_all(self):
        """Get all tracks known to LMU."""
        data = self.get("rest/sessions/getTracksAll")
        return data if isinstance(data, list) else []

    def get_all_vehicles(self):
        """Get all selectable vehicles/liveries known to LMU."""
        data = self.get("rest/sessions/getAllVehicles")
        return data if isinstance(data, list) else []

    def resolve_track_id(self, track):
        """Resolve a leaderboard scene name to the track id expected by /rest/race/track."""
        if not track:
            return None, None

        target = str(track).upper()
        for track_info in self.get_tracks_all():
            for key in ("sceneDesc", "id", "sceneSig"):
                value = track_info.get(key)
                if value and str(value).upper() == target:
                    return track_info.get("id"), track_info

        logger.warning("Could not resolve track '%s' through getTracksAll; using it as-is", track)
        return track, None
    
    def get_grip_level(self):
        """Get current grip level."""
        data = self.get("rest/sessions")

        if data and "SESSSET_pract1_realroad_init" in data:
            return data["SESSSET_pract1_realroad_init"].get("currentValue")
        return None
    
    def get_active_setup(self):
        """Get current setups."""
        return self.get("rest/garage/summary")

    @staticmethod
    def _resource_root():
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parents[1]

    def _load_session_preset_template(self):
        template_path = self._resource_root() / "templates" / SESSION_PRESET_TEMPLATE
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load session preset template %s: %s", template_path, e)
            return None

    @staticmethod
    def _value_from_weather(weather, *keys, default=None):
        for key in keys:
            if key in weather and weather[key] is not None:
                return weather[key]
        return default

    def _weather_targets(self, weather):
        rain = self._value_from_weather(weather, "rain", "RainChance", default=0)
        humidity_default = 80 if rain else 60

        return {
            "WNV_TEMPERATURE": self._value_from_weather(weather, "temperature", "Temperature", default=25),
            "WNV_SKY": self._value_from_weather(weather, "condition", "Sky", default=0),
            "WNV_RAIN_CHANCE": rain,
            "WNV_HUMIDITY": self._value_from_weather(weather, "humidity", "Humidity", default=humidity_default),
            "WNV_WINDSPEED": self._value_from_weather(weather, "wind_speed", "WindSpeed", default=0),
            "WNV_WINDDIRECTION": self._value_from_weather(weather, "wind_direction", "WindDirection", default=0),
        }

    @staticmethod
    def _ensure_dict(parent, key):
        value = parent.get(key)
        if not isinstance(value, dict):
            value = {}
            parent[key] = value
        return value

    @staticmethod
    def _vehicle_allowed_class(car):
        classes = car.get("classes") or []
        if len(classes) > 1:
            return classes[1]
        if classes:
            return classes[0]
        return ""

    @staticmethod
    def _vehicle_session_description(car):
        return car.get("desc") or car.get("vehicle") or car.get("id") or ""

    def set_session_setting_value(self, session_setting, value):
        """Set a session setting to an absolute value using LMU's delta endpoint."""
        current_data = self.get("rest/sessions")
        if not isinstance(current_data, dict):
            return "Failed to read LMU session settings"

        current_value = current_data.get(session_setting, {}).get("currentValue")
        if current_value is None:
            return f"Current value not found for {session_setting}"

        if int(current_value) == int(value):
            return None

        return self.set_session_setting(
            session_setting,
            int(value) - int(current_value),
            int(value),
        )

    def _apply_generation_settings(self, weather, tod):
        """Set only the LMU state needed before save generation."""
        grip_level = self._value_from_weather(weather, "grip_level", "GripLevel", default=None)

        settings = {
            "SESSSET_practice1_starting_time": int(tod),
        }
        if grip_level is not None:
            settings["SESSSET_pract1_realroad_init"] = int(grip_level)

        for setting, value in settings.items():
            res = self.set_session_setting_value(setting, value)
            if res is not None:
                return res

        return None

    def _set_weather_for_generation(self, weather):
        before = self.get_weather()
        if not isinstance(before, dict):
            return "Failed to read weather before generation"

        targets = self._weather_targets(weather)

        for session in WEATHER_SESSIONS:
            session_weather = before.get(session)
            if not isinstance(session_weather, dict):
                continue

            for node in WEATHER_NODES:
                node_weather = session_weather.get(node)
                if not isinstance(node_weather, dict):
                    return f"Weather node missing: {session}/{node}"

                for setting, target_value in targets.items():
                    setting_data = node_weather.get(setting)
                    if not isinstance(setting_data, dict):
                        return f"Weather setting missing: {session}/{node}/{setting}"

                    current_value = setting_data.get("currentValue")
                    if current_value is None:
                        return f"Weather value missing: {session}/{node}/{setting}"

                    delta = float(target_value) - float(current_value)
                    if abs(delta) < 0.0001:
                        continue

                    res = self.post(
                        f"rest/sessions/weather/{session}/{node}/{setting}",
                        data=str(delta),
                        headers=TEXT_HEADERS,
                    )
                    if res is False:
                        return f"LMU rejected weather update: {session}/{node}/{setting}"
                    if res is None:
                        return f"Failed to update weather: {session}/{node}/{setting}"

        after = self.get_weather()
        if not isinstance(after, dict):
            return "Failed to read weather after generation"

        return None

    def _patch_weather_display(self, preset, weather, tod):
        preset_weather = preset.get("Weather")
        if not isinstance(preset_weather, dict):
            return

        targets = self._weather_targets(weather)
        grip_level = self._value_from_weather(weather, "grip_level", "GripLevel", default=None)
        realroad = REALROAD_BY_GRIP.get(int(grip_level)) if grip_level is not None else None

        for section_name, section in preset_weather.items():
            if not isinstance(section, dict):
                continue
            if section_name != "Practice":
                continue

            road = section.get("Road")
            if isinstance(road, dict):
                road["LoadTemperaturesFromRealRoadFile"] = False
                if section_name == "Practice" and realroad:
                    road["RealRoad"] = realroad

            weather_nodes = section.get("Weather")
            if not isinstance(weather_nodes, list):
                continue

            for idx, node in enumerate(weather_nodes):
                if not isinstance(node, dict):
                    continue
                duration = node.get("Duration", 30)
                node["StartTime"] = int(tod) + (idx * int(duration or 30))
                node["Temperature"] = targets["WNV_TEMPERATURE"]
                node["Sky"] = targets["WNV_SKY"]
                node["RainChance"] = targets["WNV_RAIN_CHANCE"]
                node["Humidity"] = targets["WNV_HUMIDITY"]
                node["WindSpeed"] = targets["WNV_WINDSPEED"]
                node["WindDirection"] = targets["WNV_WINDDIRECTION"]

    def _apply_load_safe_session_settings(self, preset):
        player = self._ensure_dict(preset, "Player")
        game_options = self._ensure_dict(player, "Game Options")
        race_conditions = self._ensure_dict(player, "Race Conditions")

        game_options["Opponents"] = 0
        game_options["Drivers Per Vehicle AI"] = 1
        game_options["Drivers Per Vehicle Player"] = 1
        game_options["Tire Warmers"] = True
        game_options["Limited Tire Rules Tires Available In Garage"] = 100
        game_options["practice length"] = PRACTICE_LENGTH_MINUTES
        game_options["qualifying length"] = 20
        game_options["warmup length"] = 0
        game_options["Race Time"] = 2
        game_options["Race Length"] = 0
        game_options["Race Laps"] = 0
        game_options["Multi-session Results"] = False
        game_options["Starting Pos"] = 0

        race_conditions["Run Practice1"] = True
        race_conditions["Run Practice2"] = False
        race_conditions["Run Practice3"] = False
        race_conditions["Run Practice4"] = False
        race_conditions["Run Warmup"] = False
        race_conditions["Num Qual Sessions"] = 0
        race_conditions["Num Race Sessions"] = 0
        race_conditions["PrivatePractice"] = True
        race_conditions["Race Timer"] = 0
        race_conditions["QualifyingStartingTime"] = -1
        race_conditions["RaceStartingTime"] = -1
        race_conditions["WarmupStartingTime"] = -1
        race_conditions["Weather"] = 4
        race_conditions["TimeScaledWeather"] = True
        race_conditions["RealRoadTimeScalePractice"] = 1.0
        race_conditions["RealRoadTimeScaleQualifying"] = 1.0
        race_conditions["RealRoadTimeScaleRace"] = 1.0

    def _patch_template_for_generation(self, preset, leaderboard, car):
        weather = leaderboard.get("weather") or {}
        tod = int(leaderboard.get("tod") or 720)
        allowed_class = self._vehicle_allowed_class(car)

        player = self._ensure_dict(preset, "Player")
        driver = self._ensure_dict(player, "DRIVER")
        game_options = self._ensure_dict(player, "Game Options")
        allowed_vehicles = self._ensure_dict(game_options, "Allowed Vehicles")
        race_conditions = self._ensure_dict(player, "Race Conditions")

        driver["Vehicle"] = self._vehicle_session_description(car)
        allowed_vehicles["Optional"] = [allowed_class] if allowed_class else []
        allowed_vehicles["Required"] = []
        race_conditions["Practice1StartingTime"] = tod

        self._apply_load_safe_session_settings(preset)
        self._patch_weather_display(preset, weather, tod)

    def _patch_generated_session_preset(self, preset, leaderboard, car):
        weather = leaderboard.get("weather") or {}
        tod = int(leaderboard.get("tod") or 720)
        allowed_class = self._vehicle_allowed_class(car)

        preset["Grid"] = []
        player = self._ensure_dict(preset, "Player")
        driver = self._ensure_dict(player, "DRIVER")
        game_options = self._ensure_dict(player, "Game Options")
        allowed_vehicles = self._ensure_dict(game_options, "Allowed Vehicles")
        race_conditions = self._ensure_dict(player, "Race Conditions")

        driver["Vehicle"] = self._vehicle_session_description(car)
        allowed_vehicles["Optional"] = [allowed_class] if allowed_class else []
        allowed_vehicles["Required"] = []
        race_conditions["Practice1StartingTime"] = tod

        self._apply_load_safe_session_settings(preset)
        self._patch_weather_display(preset, weather, tod)

    def _patch_generated_save(self, generated_save, leaderboard, car):
        preset = generated_save.get("SessionPreset")
        if isinstance(preset, dict):
            self._patch_generated_session_preset(preset, leaderboard, car)

        generated_save["aiVehicles"] = []
        generated_save["maxLaps"] = 2147483647

        start_et = float(generated_save.get("startET", 0) or 0)
        generated_save["endET"] = start_et + PRACTICE_TIMER_SECONDS

        generated_save["allowedVehiclesFilter"] = {
            "Optional": ["*"],
            "Required": [],
        }

    @staticmethod
    def _unwrap_generated_save(generated):
        if isinstance(generated, dict) and isinstance(generated.get("save"), dict):
            return generated["save"]
        return generated

    def load_generated_session(self, leaderboard, car):
        """Generate and load an LMU save for the selected leaderboard/car."""
        track = leaderboard.get("track")
        weather = leaderboard.get("weather") or {}
        tod = int(leaderboard.get("tod") or 720)

        if not car or not car.get("id") or not self._vehicle_session_description(car):
            return False, "Selected car is missing LMU id or vehicle description"

        track_id, _track_info = self.resolve_track_id(track)
        if not track_id:
            return False, f"Could not resolve LMU track id for {track}"

        logger.info(
            "Loading generated session: track=%s track_id=%s car=%s",
            track,
            track_id,
            self._vehicle_session_description(car),
        )

        res = self.post("rest/race/track", data=str(track_id), headers=TEXT_HEADERS)
        if res is False:
            return False, f"LMU rejected track {track}"
        if res is None:
            return False, f"Failed to set track {track}"

        res = self._apply_generation_settings(weather, tod)
        if res is not None:
            return False, res

        res = self._set_weather_for_generation(weather)
        if res is not None:
            return False, res

        preset = self._load_session_preset_template()
        if not isinstance(preset, dict):
            return False, "Failed to load session preset template"

        self._patch_template_for_generation(preset, leaderboard, car)

        preset_body = json.dumps(preset, separators=(",", ":"))
        generated_raw = self.post(
            "rest/sessions/SaveLoad/generateSaveFileFromSessionPreset",
            data=preset_body.encode("utf-8"),
            headers=TEXT_HEADERS,
            timeout=SAVELOAD_TIMEOUT,
        )
        if generated_raw is False:
            return False, "LMU rejected save generation"
        if generated_raw is None:
            return False, "Failed to generate LMU save"

        generated_save = self._unwrap_generated_save(generated_raw)
        if not isinstance(generated_save, dict):
            return False, "LMU returned an invalid generated save"

        self._patch_generated_save(generated_save, leaderboard, car)

        load_body = {"save": generated_save}

        load_res = self.post(
            "rest/sessions/SaveLoad/loadGame",
            data=json.dumps(load_body, separators=(",", ":")).encode("utf-8"),
            headers=TEXT_HEADERS,
            timeout=SAVELOAD_TIMEOUT,
        )
        if load_res is False:
            return False, "LMU rejected loadGame"
        if load_res is None:
            return False, "Failed to load generated LMU save"

        logger.info("Generated session loaded successfully")
        return True, None
    
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
