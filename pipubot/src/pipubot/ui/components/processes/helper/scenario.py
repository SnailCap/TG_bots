from __future__ import annotations

from core.interaction.input import InputParseResult, InputValues


class HelperBundleScenario:
    def parse(self, raw_input: str) -> InputParseResult:
        lines = [line.strip() for line in raw_input.splitlines() if line.strip()]
        errors: list[str] = []

        if len(lines) not in (2, 3):
            errors.append("Отправьте 2 или 3 строки: текст, ссылка, длина.")
            return InputParseResult(data=InputValues(values={}), errors=errors)

        text, url = lines[0], lines[1]

        parsed: dict[str, object] = {"text": text, "url": url}

        if len(lines) == 3:
            raw_width = lines[2]
            try:
                width = int(raw_width)
                if width <= 0:
                    raise ValueError
                parsed["width"] = width
            except ValueError:
                errors.append("Длина должна быть целым числом больше 0.")

        return InputParseResult(
            data=InputValues(values=parsed),
            errors=errors,
        )
