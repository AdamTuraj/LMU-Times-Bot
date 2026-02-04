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
