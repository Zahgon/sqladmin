from typing import Any

from markupsafe import Markup


def empty_formatter(value: Any) -> str:
    """Return empty string for `None` value"""
    pass


def bool_formatter(value: bool) -> Markup:
    """Return check icon if value is `True` or X otherwise."""
    pass


BASE_FORMATTERS = {
    type(None): empty_formatter,
    bool: bool_formatter,
}
