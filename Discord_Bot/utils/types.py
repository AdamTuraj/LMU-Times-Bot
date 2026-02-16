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

from enum import Enum


class Tracks(str, Enum):
    """Available racing tracks."""

    PORTIMAO = "PORTIMAOWEC"
    IMOLA = "IMOLAWEC"
    MONZA = "MONZAWEC"
    MONZA_CURVA_GRANDE = "MONZAWEC_GRANDE"
    INTERLAGOS = "INTERLAGOSWEC"
    BAHRAIN = "BAHRAINWEC"
    BAHRAIN_ENDURANCE = "BAHRAINWEC_ENDCE"
    BAHRAIN_OUTER = "BAHRAINWEC_OUTER"
    BAHRAIN_PADDOCK = "BAHRAINWEC_PADDOCK"
    SPA = "SPAWEC"
    SPA_ENDURANCE = "SPAWEC_ENDCE"
    LE_MANS = "LEMANSWEC"
    LE_MANS_MULSANNE = "LEMANSWEC_MULSANNE"
    COTA_NATIONAL = "COTAWEC_NATIONAL"
    COTA = "COTAWEC"
    FUJI = "FUJIWEC"
    FUJI_CLASSIC = "FUJIWEC_CL"
    LUSAIL_SHORT = "QATARWEC_SHORT"
    QATAR = "QATARWEC"
    PAUL_RICARD = "PAULRICARDELMS"
    SEBRING = "SEBRINGWEC"
    SEBRING_SCHOOL = "SEBRINGWEC_SCHOOL"
    SILVERSTONE = "SILVERSTONEELMS"


class Classes(Enum):
    """Car class categories."""

    LMGT3 = 0
    GTE = 1
    LMP3 = 2
    LMP2 = 3
    LMP2_UNRESTRICTED = 4
    HYPERCAR = 5


class WeatherConditions(Enum):
    """Weather condition settings."""

    CLEAR = 0
    LIGHT_CLOUDS = 1
    PARTIALLY_CLOUDY = 2
    MOSTLY_CLOUDY = 3
    OVERCAST = 4
    CLOUDY_DRIZZLE = 5
    CLOUDY_LIGHT_RAIN = 6
    OVERCAST_LIGHT_RAIN = 7
    OVERCAST_RAIN = 8
    OVERCAST_HEAVY_RAIN = 9
    OVERCAST_STORM = 10


class GripLevel(Enum):
    """Track grip level settings."""

    SATURATED_GRIP = 5
    MEDIUM_GRIP = 4
    LOW_GRIP = 3
    HEAVY_GRIP = 2
    NATURALLY_PROGRESSING = 1
    GREEN = 0