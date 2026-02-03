import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("recorder")

BASE_URL = os.getenv("LMU_URL", "http://localhost:6397")
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
        print(data.get("SESSSET_pract1_realroad_init"))
        if data and "SESSSET_pract1_realroad_init" in data:
            return data["SESSSET_pract1_realroad_init"].get("currentValue")
        return None