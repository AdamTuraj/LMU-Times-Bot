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

__version__ = "<VERSION>"

APP_NAME = "<APP_NAME>"
SERVICE_NAME = APP_NAME.replace(" ", "")
KEYRING_USERNAME = "user_token"
OAUTH_CALLBACK_PORT = 54783
POLL_INTERVAL = 1.0
TEMP_TOLERANCE = 1.0
RAIN_TOLERANCE = 5.0

# Car class mappings
CAR_CLASSES = {
    "GT3": 0,
    "GTE": 1,
    "LMP3": 2,
    "LMP2": 3,
    "LMP2_ELMS": 4,
    "Hyper": 5
}
CAR_CLASS_NAMES = {v: k for k, v in CAR_CLASSES.items()}

# Weather condition mappings
WEATHER_CONDITIONS = {
    0: "Clear",
    1: "Light Clouds",
    2: "Partially Cloudy",
    3: "Mostly Cloudy",
    4: "Overcast",
    5: "Cloudy & Drizzle",
    6: "Cloudy & Light Rain",
    7: "Overcast & Light Rain",
    8: "Overcast & Rain",
    9: "Overcast & Heavy Rain",
    10: "Overcast & Storm",
}

# Grip level mappings
GRIP_LEVELS = {
    5: "Saturated Grip",
    4: "Medium Grip",
    3: "Low Grip",
    2: "Heavy Grip",
    1: "Naturally Progressing",
    0: "Green",
}

# Track name mappings
TRACK_NAMES = {
    "PORTIMAOWEC": "Portimão",
    "IMOLAWEC": "Imola",
    "MONZAWEC": "Monza",
    "MONZAWEC_GRANDE": "Monza Curva Grande",
    "INTERLAGOSWEC": "Interlagos",
    "BAHRAINWEC": "Bahrain",
    "BAHRAINWEC_ENDCE": "Bahrain Endurance",
    "BAHRAINWEC_OUTER": "Bahrain Outer",
    "BAHRAINWEC_PADDOCK": "Bahrain Paddock",
    "SPAWEC": "Spa-Francorchamps",
    "SPAWEC_ENDCE": "Spa Endurance",
    "LEMANSWEC": "Le Mans",
    "LEMANSWEC_MULSANNE": "Le Mans Mulsanne",
    "COTAWEC_NATIONAL": "Circuit of the Americas - National",
    "COTAWEC": "Circuit of the Americas",
    "FUJIWEC": "Fuji Speedway",
    "FUJIWEC_CL": "Fuji Classic",
    "QATARWEC_SHORT": "Lusail Short",
    "QATARWEC": "Lusail Circuit",
    "PAULRICARDELMS": "Paul Ricard",
    "SEBRINGWEC": "Sebring International Raceway",
    "SEBRINGWEC_SCHOOL": "Sebring School Circuit",
    "SILVERSTONEELMS": "Silverstone",
}
