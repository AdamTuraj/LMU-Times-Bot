import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("recorder")

BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEOUT = 5


class Backend:
    """Client for the LMU Times backend API."""

    def __init__(self, base_url=BASE_URL, timeout=TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        logger.info("Backend initialized: %s", self.base_url)

    def get(self, endpoint, token=None):
        """Make a GET request. Returns JSON data, False for 404, None on error."""
        url = f"{self.base_url}/{endpoint}"
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                return False
            logger.error("GET %s: %d", endpoint, response.status_code)
            return None
        except Exception as e:
            logger.error("GET %s failed: %s", endpoint, e)
            return None

    def post(self, endpoint, data, token=None):
        """Make a POST request. Returns JSON data, False for 403/404, None on error."""
        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.post(url, json=data, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            if response.status_code in (403, 404):
                return False
            logger.error("POST %s: %d", endpoint, response.status_code)
            return None
        except Exception as e:
            logger.error("POST %s failed: %s", endpoint, e)
            return None

    def get_discord_oauth_url(self, state):
        """Get Discord OAuth URL."""
        data = self.get(f"discord?state={state}")
        if data and isinstance(data, dict):
            return data.get("url")
        return None

    def get_username(self, token):
        """Get username for a token."""
        data = self.get("user", token)
        if data and isinstance(data, dict):
            return data.get("name")
        return None

    def get_lb_info(self, track):
        """Get leaderboard info for a track."""
        data = self.get(f"leaderboard/{track}")
        if data:
            return data
        return None

    def submit_time(self, token, time_data, track, car, class_, driver_name):
        """Submit a lap time."""
        logger.info("Submitting time %.3f for %s", time_data["lap"], track)
        data = self.post(
            f"leaderboard/{track}/submit",
            {"time_data": time_data, "car": car, "class": class_, "driver_name": driver_name},
            token
        )
        if data is False:
            return False
        if data and data.get("message"):
            logger.info("Time submitted")
            return True
        return None

    def logout_user(self, token):
        """Logout user."""
        data = self.post("user/logout", {}, token)
        return bool(data and data.get("message"))