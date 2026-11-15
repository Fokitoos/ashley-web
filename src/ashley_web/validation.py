"""Validation shared by the site's forms."""

import re
from collections.abc import Mapping

_EMAIL = re.compile(r"^\S+@\S+\.\S+$")
_MAX_NAME, _MAX_EMAIL = 120, 254


class FormError(ValueError):
    """The request is invalid; the message is safe to show to the visitor."""


def text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def contact(payload: Mapping[str, object]) -> tuple[str, str]:
    """The visitor's name and email address, validated."""
    name = text(payload, "name")
    if not name or len(name) > _MAX_NAME:
        raise FormError("Please add your name.")
    email = text(payload, "email")
    if not _EMAIL.fullmatch(email) or len(email) > _MAX_EMAIL:
        raise FormError("Please add a valid email address.")
    return name, email
