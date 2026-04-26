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

def get_stylesheet():
    """Return the application stylesheet."""
    return """
        QMainWindow {
            background-color: #f5f5f5;
        }
        QWidget {
            background-color: #f5f5f5;
        }
        QLabel {
            color: #2c2c2c;
            font-size: 10pt;
            padding: 6px;
            background-color: transparent;
        }
        QLabel#statusLabel {
            background-color: white;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            padding: 10px;
            color: #333;
        }
        QLabel#fieldLabel {
            color: #555;
            font-size: 9pt;
            padding: 2px 4px 0 4px;
        }
        QLabel#loginTitle {
            color: #1f2937;
            font-size: 18pt;
            font-weight: 700;
            padding: 0;
        }
        QLabel#loginSubtitle {
            color: #4b5563;
            font-size: 9.5pt;
            padding: 4px 16px;
            max-width: 320px;
        }
        QLabel#loginStatus {
            color: #6b7280;
            font-size: 8.5pt;
            padding: 2px;
        }
        QComboBox {
            background-color: white;
            border: 1px solid #d6d6d6;
            border-radius: 5px;
            padding: 6px 8px;
            min-height: 26px;
            color: #2c2c2c;
            selection-background-color: #0b6cff;
            selection-color: white;
        }
        QComboBox:hover {
            border-color: #9ca3af;
        }
        QComboBox::drop-down {
            border: none;
            width: 24px;
        }
        QComboBox QAbstractItemView {
            background-color: white;
            border: 1px solid #9ca3af;
            color: #1f2937;
            outline: none;
            selection-background-color: #0b6cff;
            selection-color: white;
        }
        QComboBox QAbstractItemView::item {
            min-height: 26px;
            padding: 5px 8px;
            color: #1f2937;
            background-color: white;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #eaf2ff;
            color: #111827;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: #0b6cff;
            color: white;
        }
        QComboBox:disabled {
            color: #777;
            background-color: #eeeeee;
        }
        QProgressBar {
            border: 1px solid #d6d6d6;
            border-radius: 5px;
            background-color: white;
            min-height: 8px;
            max-height: 8px;
        }
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 4px;
        }
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 6px 14px;
            font-weight: 600;
            font-size: 10pt;
            min-height: 28px;
        }
        QPushButton:hover {
            background-color: #106ebe;
        }
        QPushButton:pressed {
            background-color: #005a9e;
        }
        QPushButton:disabled {
            background-color: #a6a6a6;
            color: #f4f4f4;
        }
        QPushButton#secondaryButton {
            background-color: #6c757d;
        }
        QPushButton#secondaryButton:hover {
            background-color: #5a6268;
        }
        QPushButton#secondaryButton:pressed {
            background-color: #4e555b;
        }
        QPushButton#loginButton {
            background-color: #334155;
            font-size: 11pt;
            min-height: 36px;
            padding: 8px 18px;
        }
        QPushButton#loginButton:hover {
            background-color: #1f2937;
        }
        QPushButton#loginButton:pressed {
            background-color: #111827;
        }
    """
