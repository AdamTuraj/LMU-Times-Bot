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
            background-color: #5865f2;
            font-size: 11pt;
            min-height: 36px;
            padding: 8px 18px;
        }
        QPushButton#loginButton:hover {
            background-color: #4752c4;
        }
        QPushButton#loginButton:pressed {
            background-color: #3c45a5;
        }
    """
