from enum import Enum

class OptionSide(str, Enum):
    CALL = "CALL"
    PUT = "PUT"

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class SpreadType(str, Enum):
    VERTICAL = "VERTICAL"
    IRON_CONDOR = "IRON_CONDOR"
    CALENDAR = "CALENDAR"
    ROLL = "ROLL"

class OrderIntent(str, Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    ROLL = "ROLL"
