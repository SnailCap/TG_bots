from dataclasses import dataclass, field


@dataclass(slots=True)
class MemorySecretStore:
    _values: dict[str, str] = field(default_factory=dict)

    def set(self, reference: str, value: str) -> None:
        if not reference.strip() or not value:
            raise ValueError("Secret reference and value must not be empty")
        self._values[reference] = value

    def get(self, reference: str) -> str | None:
        return self._values.get(reference)

    def delete(self, reference: str) -> None:
        self._values.pop(reference, None)

