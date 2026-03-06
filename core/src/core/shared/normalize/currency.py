from .strings import normalize_required_str


def normalize_currency_code(value: str | None) -> str:
    code = normalize_required_str(value, field_name="currency")
    return code.upper()