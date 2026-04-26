from enum import Enum


class ServiceCallbackData(str, Enum):
    SVC = "svc:"
    ST = "st:"

    NAV = "svc:nav:"
    NAV_HOME = "svc:nav:home"
    NAV_CURRENT = "svc:nav:current"
    NAV_PREVIOUS = "svc:nav:previous"

    PRC_START = "svc:prc:start:"
    PRC_CMD = "svc:prc:cmd:"