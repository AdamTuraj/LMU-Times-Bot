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

import base64
from PyQt6.QtGui import QIcon, QPixmap
import logging

logger = logging.getLogger(__name__)

# Embedded application icon (auto-generated during build)
ICON_BASE64 = "<ICON_BASE64>"

def get_embedded_icon():
    """Load the embedded application icon."""
    try:
        logger.debug("Loading embedded application icon.")
        icon_bytes = base64.b64decode(ICON_BASE64)
        pixmap = QPixmap()
        if pixmap.loadFromData(icon_bytes):
            logger.info("Embedded icon loaded successfully.")
            return QIcon(pixmap)
        
        logger.error("Failed to load icon from embedded data.")
        return QIcon()
    except Exception:
        logger.exception("Exception occurred while loading embedded icon.")
        return QIcon()
