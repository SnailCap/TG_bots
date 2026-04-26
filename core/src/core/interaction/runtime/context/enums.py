from enum import Enum


class UserInputType(str, Enum):
    """Defines the possible types of subscriber input."""
    CALLBACK = "callback"
    MESSAGE = "message"
    COMMAND = "command"
    UNKNOWN = "unknown"


class UserRole(str, Enum):
    ADMIN = "admin"
    PUBLIC = "public"