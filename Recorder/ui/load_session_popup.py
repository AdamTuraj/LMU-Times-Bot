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

import sys
import os

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QDialogButtonBox,
    QFrame,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QSettings, QTimer


class LoadSessionPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Session loaded successfully!")
        self.setFixedSize(680, 500)

        self.settings = QSettings("LMU Times Bot", "Recorder")

        self.setStyleSheet("""
            QDialog { background: #f3f4f6; }

            QFrame#card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }

            QLabel#title {
                font-size: 16px;
                font-weight: 700;
                color: #111827;
            }

            QLabel#subtitle {
                font-size: 11.5px;
                color: #4b5563;
            }

            QCheckBox {
                font-size: 11px;
                color: #374151;
                spacing: 8px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #d1d5db;
                border-radius: 4px;
                background: white;
            }

            QCheckBox::indicator:hover {
                border-color: #0b6cff;
                cursor: pointer;
            }

            QCheckBox::indicator:checked {
                background: #0b6cff;
                border-color: #0b6cff;
            }

            QCheckBox:hover { 
                color: #1f2937;
            }

            QDialogButtonBox QPushButton {
                background-color: #0b6cff;
                color: white;
                font-size: 11px;
                font-weight: 600;
                padding: 7px 16px;
                border: none;
                border-radius: 8px;
                min-width: 90px;
            }
            QDialogButtonBox QPushButton:hover { background-color: #0a5fe0; }
                           
            QDialogButtonBox QPushButton:pressed { background-color: #084db6; }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        title_label = QLabel("Session Loaded Successfully")
        title_label.setObjectName("title")
        layout.addWidget(title_label)

        body_label = QLabel(
            "Follow the steps shown below to continue. "
            "Avoid changing settings to ensure preflight checks pass correctly."
        )
        body_label.setObjectName("subtitle")
        body_label.setWordWrap(True)
        layout.addWidget(body_label)

        # Image
        image_path = self.get_image_path("setup_session_instructions.jpg")
        self.image_pixmap = QPixmap(image_path)

        self.image_label = QLabel()
        self.image_label.setObjectName("image")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(320)
        self.image_label.setMaximumHeight(340)
        self.image_label.setScaledContents(False)
        self.image_label.setCursor(Qt.CursorShape.ArrowCursor)
        layout.addWidget(self.image_label)

        # Bottom row
        self.dont_show_checkbox = QCheckBox("Don't show this message again")
        self.dont_show_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dont_show_checkbox.setChecked(
            self.settings.value("dont_show_load_session_popup", False, type=bool)
        )

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.setCursor(Qt.CursorShape.PointingHandCursor)
        button_box.accepted.connect(self.accept)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.dont_show_checkbox)
        bottom_row.addStretch()
        bottom_row.addWidget(button_box)
        layout.addLayout(bottom_row)

    def accept(self):
        self.settings.setValue(
            "dont_show_load_session_popup",
            self.dont_show_checkbox.isChecked()
        )
        super().accept()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._update_image)
        QTimer.singleShot(30, self._update_image)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_image()

    def _update_image(self):
        if self.image_pixmap.isNull():
            self.image_label.setText("Image not found.")
            return

        target = self.image_label.contentsRect().size()
        if target.width() <= 0 or target.height() <= 0:
            return

        scaled = self.image_pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.image_label.setPixmap(scaled)

    # Edited from https://stackoverflow.com/a/66581062
    @staticmethod
    def get_image_path(filename):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, filename)
        return os.path.join(os.path.abspath("."), "images", filename)
