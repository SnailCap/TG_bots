from enum import Enum

class ServiceCallbackData(str, Enum):
    SVC = "svc:"

    NAV = "svc:nav:"
    NAV_TO = "svc:nav:to:"
    PRC_START = "svc:prc:start:"
    PRC_CMD = "svc:prc:cmd:"

    # nav special targets
    NAV_PREVIOUS = "svc:nav:previous"
    NAV_CURRENT = "svc:nav:current"
    NAV_HOME = "svc:nav:home"