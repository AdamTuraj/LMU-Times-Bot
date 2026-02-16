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
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger("recorder")


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callbacks."""

    expected_state = ""
    login_callback = None

    def do_GET(self):
        """Handle callback GET request."""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path != "/callback":
            self.send_error(404)
            return

        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        name = params.get("name", [""])[0]
        state = params.get("state", [None])[0]

        if not code or state != self.expected_state:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid request. You can close this tab.")
            return

        logger.info("OAuth success for %s", name)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Login complete.</h2>You can close this tab.")

        if OAuthCallbackHandler.login_callback:
            OAuthCallbackHandler.login_callback(code, name)

        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class LocalCallbackServer:
    """Local server for OAuth callbacks."""

    def __init__(self, port, state, on_login):
        self.port = port
        self.state = state
        self.on_login = on_login
        self.httpd = None

    def start(self):
        """Start the server in a background thread."""
        OAuthCallbackHandler.expected_state = self.state
        OAuthCallbackHandler.login_callback = self.on_login

        self.httpd = HTTPServer(("127.0.0.1", self.port), OAuthCallbackHandler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        logger.info("OAuth server started on port %d", self.port)

    def stop(self):
        """Stop the server."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None