def normalize_optional_str(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


def normalize_required_str(value: str | None, *, field_name: str) -> str:
    normalized = normalize_optional_str(value)
    if normalized is None:
        raise ValueError(f"{field_name} is required")
    return normalized