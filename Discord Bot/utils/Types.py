from enum import Enum


class Tracks(Enum):
    """Available racing tracks."""

    PORTIMAOWEC = "Portimao"
    IMOLAWEC = "Imola"
    MONZAWEC = "Monza"
    MONZAWEC_GRANDE = "Monza Curva Grande"
    INTERLAGOSWEC = "Interlagos"
    BAHRAINWEC = "Bahrain"
    BAHRAINWEC_ENDCE = "Bahrain Endurance"
    BAHRAINWEC_OUTER = "Bahrain Outer"
    BAHRAINWEC_PADDOCK = "Bahrain Paddock"
    SPAWEC = "Spa"
    SPAWEC_ENDCE = "Spa Endurance"
    LEMANSWEC = "Le Mans"
    LEMANSWEC_MULSANNE = "Le Mans Mulsanne"
    COTAWEC_NATIONAL = "COTA National"
    COTAWEC = "COTA"
    FUJIWEC = "Fuji"
    FUJIWEC_CL = "Fuji Classic"
    QATARWEC_SHORT = "Lusail Short"
    QATARWEC = "Qatar"
    PAULRICARDELMS = "Paul Ricard"
    SEBRINGWEC = "Sebring"
    SEBRINGWEC_SCHOOL = "Sebring School"
    LIVERYSHOWROOM = "Livery Showroom"
    SILVERSTONEELMS = "Silverstone"


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