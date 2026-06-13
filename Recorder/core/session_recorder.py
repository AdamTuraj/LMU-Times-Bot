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

import threading
from config.helpers import logger
from config.settings import POLL_INTERVAL


CLASS_ALIASES = {
    "HYPER": "Hypercar",
    "HYPERCAR": "Hypercar",
    "LMGT3": "GT3",
    "LMP2_UNRESTRICTED": "LMP2_ELMS",
}


class SessionRecorder:
    def __init__(self, lmu_client, backend_client, token):
        """
        Initialize the recorder.

        Args:
            lmu_client: LMU API client
            backend_client: Backend API client
            token: Authentication token
        """
        self.lmu = lmu_client
        self.backend = backend_client
        self.token = token
        
        self.fastest_lap = None
        self.is_recording = False
        self.recording_thread = None
        self._stop_event = threading.Event()

    @staticmethod
    def _normalize_class_name(name):
        value = str(name or "").strip()
        return CLASS_ALIASES.get(value.upper(), value)

    @classmethod
    def _normalize_classes(cls, classes):
        return {
            cls._normalize_class_name(car_class)
            for car_class in (classes or [])
            if str(car_class or "").strip()
        }

    def _wait(self, seconds):
        return self._stop_event.wait(seconds)

    def start_recording(self, track, car, car_classes, fixed_setup, update_callback, on_session_end, on_disconnect, on_error):
        """
        Start recording lap times.

        Args:
            track: Track identifier
            car: Car identifier
            car_classes: Classes allowed for the selected car/livery
            fixed_setup: Whether fixed setup is required
            update_callback: Function to call with status updates
            on_session_end: Callback when session ends normally
            on_disconnect: Callback when LMU disconnects
            on_error: Callback when an error occurs
        """
        if self.is_recording:
            logger.warning("Already recording")
            return

        self.fastest_lap = None
        self.is_recording = True
        self._stop_event.clear()
        expected_classes = self._normalize_classes(car_classes)
        
        def record_loop():
            logger.info("Starting recording loop")

            is_on_fixed = True
            
            while self.is_recording and not self._stop_event.is_set():
                state = self.lmu.get_standings()
                session_state = self.lmu.get_session_info()

                if session_state is False:
                    logger.warning("LMU disconnected during recording")
                    update_callback("Waiting for LMU...")
                    self.is_recording = False
                    on_disconnect()
                    return

                if not isinstance(session_state, dict):
                    self._wait(POLL_INTERVAL)
                    continue

                # Check if session ended
                if not session_state.get("inControlOfVehicle", False):
                    logger.info("Session ended during recording")
                    update_callback("Session ended. Waiting for new session...")
                    self.is_recording = False
                    on_session_end()
                    return

                # Check if LMU disconnected
                if state is False:
                    logger.warning("LMU disconnected during recording")
                    update_callback("Waiting for LMU...")
                    self.is_recording = False
                    on_disconnect()
                    return

                if state is None:
                    self._wait(POLL_INTERVAL)
                    continue

                if not isinstance(state, list) or not state or not isinstance(state[0], dict):
                    self._wait(POLL_INTERVAL)
                    continue

                if len(state) != 1:
                    logger.info(
                        "Active standings no longer match a loaded solo session: rows=%d",
                        len(state),
                    )
                    update_callback("Recording stopped because the active session changed. Waiting for a loaded session...")
                    self.is_recording = False
                    on_session_end()
                    return

                current_car_class = self._normalize_class_name(state[0].get("carClass"))
                if expected_classes and not current_car_class:
                    self._wait(POLL_INTERVAL)
                    continue

                if expected_classes and current_car_class not in expected_classes:
                    logger.info(
                        "Active car class changed during recording: expected=%s actual=%s",
                        sorted(expected_classes),
                        current_car_class,
                    )
                    update_callback("Recording stopped because the active car class changed. Waiting for a loaded session...")
                    self.is_recording = False
                    on_session_end()
                    continue

                # Check fixed setup
                if fixed_setup:
                    setup = self.lmu.get_active_setup()
                    if not setup:
                        on_error("Error reading setup. Trying again...")
                        self._wait(POLL_INTERVAL)
                        continue
                    if "Balanced" not in setup.get("activeSetup", ""):
                        if is_on_fixed:
                            on_error("Fixed setup required! Please switch to the default LMU setup (not CDA) to record.")
                            is_on_fixed = False
                        self._wait(POLL_INTERVAL)
                        continue
                    elif not is_on_fixed:
                        on_error("Thank you for switching to the default LMU setup! Resuming recording.")
                        is_on_fixed = True

                # Get lap data
                lap = state[0].get("bestLapTime")
                s1 = state[0].get("bestLapSectorTime1")
                s2 = state[0].get("bestLapSectorTime2")

                # Validate lap time
                if not lap or lap < 10:
                    self._wait(POLL_INTERVAL)
                    continue

                # Check if this is a new best lap
                if self.fastest_lap and lap >= self.fastest_lap:
                    self._wait(POLL_INTERVAL)
                    continue

                # Validate sector times
                if not s1 or not s2:
                    self._wait(POLL_INTERVAL)
                    continue

                # New best lap - record it
                logger.info("Lap: %.3f (S1: %.3f, S2: %.3f)", lap, s1, s2)
                self.fastest_lap = lap
                update_callback(f"Recorded: {lap:.3f}s\nWaiting for next lap...")

                # Submit to backend
                lap_data = {"sector1": s1, "sector2": s2, "lap": lap}
                res = self.backend.submit_time(
                    self.token, lap_data, track, car, state[0]["carClass"],
                    state[0].get("driverName", "Unknown")
                )

                if res is False:
                    logger.error("Submission failed - blacklisted")
                    update_callback("Submission failed. Blacklisted. Waiting for session end...")
                    self.is_recording = False
                    on_session_end()
                    return

                self._wait(POLL_INTERVAL*5)

            logger.info("Recording loop stopped")

        self.recording_thread = threading.Thread(target=record_loop, daemon=True)
        self.recording_thread.start()

    def stop_recording(self):
        """Stop the recording process."""
        self.is_recording = False
        self._stop_event.set()
        thread = self.recording_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=POLL_INTERVAL * 2)
        self.recording_thread = None
        logger.info("Recording stopped")

    def reset(self):
        """Reset the recorder state."""
        self.fastest_lap = None
        self.stop_recording()
