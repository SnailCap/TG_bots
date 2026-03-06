def normalize_telegram_username(value: str | None) -> str | None:
    if value is None:
        return None

    username = value.strip()

    if username.startswith("@"):
        username = username[1:]

    username = username.strip()

    return username or None