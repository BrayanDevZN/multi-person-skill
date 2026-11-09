"""Tiny declarative payload validation. Errors carry hints Claude can act on."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CliError(Exception):
    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint


@dataclass(frozen=True)
class Field:
    kind: str  # str | int | list_str | list_int | dict | enum
    required: bool = False
    choices: tuple[str, ...] = ()
    min: int | None = None
    max: int | None = None

    def describe(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.kind, "required": self.required}
        if self.choices:
            d["choices"] = list(self.choices)
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        return d


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def check_field(name: str, field: Field, value: Any) -> Any:
    k = field.kind
    if value is None:
        if field.required:
            raise CliError(f"'{name}' is required and cannot be null")
        return None
    if k == "str":
        if not isinstance(value, str) or (field.required and not value.strip()):
            raise CliError(f"'{name}' must be a non-empty string")
    elif k == "int":
        if not _is_int(value):
            raise CliError(f"'{name}' must be an integer")
        if (field.min is not None and value < field.min) or (field.max is not None and value > field.max):
            raise CliError(f"'{name}' must be between {field.min} and {field.max}, got {value}")
    elif k == "list_str":
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise CliError(f"'{name}' must be a list of strings")
    elif k == "list_int":
        if not isinstance(value, list) or not value or not all(_is_int(v) for v in value):
            raise CliError(f"'{name}' must be a non-empty list of integers")
    elif k == "dict":
        if not isinstance(value, dict):
            raise CliError(f"'{name}' must be a JSON object")
    elif k == "enum":
        if value not in field.choices:
            raise CliError(f"'{name}' must be one of {list(field.choices)}, got {value!r}")
    return value


def validate(data: Any, spec: dict[str, Field], *, partial: bool = False) -> dict[str, Any]:
    """Validate `data` against `spec`. Unknown keys are rejected; `partial` skips required checks."""
    if not isinstance(data, dict):
        raise CliError("payload must be a JSON object", "Pass --json '{\"field\": ...}' or --file path.json")
    unknown = sorted(set(data) - set(spec))
    if unknown:
        raise CliError(f"unknown field(s): {unknown}", f"Allowed fields: {sorted(spec)}")
    out: dict[str, Any] = {}
    for name, field in spec.items():
        if name not in data:
            if field.required and not partial:
                raise CliError(
                    f"missing required field '{name}'",
                    f"Required fields: {[n for n, f in spec.items() if f.required]}",
                )
            continue
        out[name] = check_field(name, field, data[name])
    return out


def as_list(payload: Any, key: str) -> list[dict[str, Any]]:
    """Accept a single object, a list of objects, or {key: [objects]} (batch)."""
    if isinstance(payload, dict) and key in payload and len(payload) == 1:
        payload = payload[key]
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload:
        return payload
    raise CliError("payload must be an object, a non-empty list of objects, or " + f'{{"{key}": [...]}}')
