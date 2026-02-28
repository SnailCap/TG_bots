from enum import Enum


class PageAccessLevel(str, Enum):
    ADMIN = "admin"
    PUBLIC = "public"
