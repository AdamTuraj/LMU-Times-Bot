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

    def start_recording(self, track, car, fixed_setup, update_callback, on_session_end, on_disconnect, on_error):
        """
        Start recording lap times.

        Args:
            track: Track identifier
            car: Car identifier
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
        
        def record_loop():
            logger.info("Starting recording loop")

            is_on_fixed = True
            
            while self.is_recording:
                state = self.lmu.get_standings()
                session_state = self.lmu.get_session_info()

                # Check fixed setup
                if fixed_setup:
                    setup = self.lmu.get_active_setup()
                    if not setup:
                        on_error("Error reading setup. Trying again...")
                        continue
                    if "Balanced" not in setup.get("activeSetup", "") and is_on_fixed: # A pretty bad way to check for default LMU setup. Maybe I'll implement a better way in the future but this is mainly to prevent someone from being naive.
                        on_error("Fixed setup required! Please switch to the default LMU setup (not CDA) to record.")
                        is_on_fixed = False
                        continue
                    elif "Balanced" in setup.get("activeSetup", "") and not is_on_fixed:
                        on_error("Thank you for switching to the default LMU setup! Resuming recording.")
                        is_on_fixed = True

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
                    threading.Event().wait(POLL_INTERVAL)
                    continue

                # Get lap data
                lap = state[0].get("bestLapTime")
                s1 = state[0].get("bestLapSectorTime1")
                s2 = state[0].get("bestLapSectorTime2")

                # Validate lap time
                if not lap or lap < 10:
                    threading.Event().wait(POLL_INTERVAL)
                    continue

                # Check if this is a new best lap
                if self.fastest_lap and lap >= self.fastest_lap:
                    threading.Event().wait(POLL_INTERVAL)
                    continue

                # Validate sector times
                if not s1 or not s2:
                    threading.Event().wait(POLL_INTERVAL)
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

                threading.Event().wait(POLL_INTERVAL*5)

        self.recording_thread = threading.Thread(target=record_loop, daemon=True)
        self.recording_thread.start()

    def stop_recording(self):
        """Stop the recording process."""
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread = None
        logger.info("Recording stopped")

    def reset(self):
        """Reset the recorder state."""
        self.fastest_lap = None
        self.is_recording = False
