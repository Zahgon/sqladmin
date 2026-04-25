from __future__ import annotations

import csv
import enum
import inspect
import json
import os
import re
import unicodedata
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timedelta
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Generator,
    TypeVar,
    get_args,
    get_origin,
)

from sqlalchemy import Column
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import RelationshipProperty

from sqladmin._types import MODEL_PROPERTY, SESSION_MAKER

T = TypeVar("T")

_filename_ascii_strip_re = re.compile(r"[^A-Za-z0-9_.-]")
_windows_device_files = (
    "CON",
    "AUX",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "LPT1",
    "LPT2",
    "LPT3",
    "PRN",
    "NUL",
)

standard_duration_re = re.compile(
    r"^"
    r"(?:(?P<days>-?\d+) (days?, )?)?"
    r"(?P<sign>-?)"
    r"((?:(?P<hours>\d+):)(?=\d+:\d+))?"
    r"(?:(?P<minutes>\d+):)?"
    r"(?P<seconds>\d+)"
    r"(?:[\.,](?P<microseconds>\d{1,6})\d{0,6})?"
    r"$"
)

# Support the sections of ISO 8601 date representation that are accepted by timedelta
iso8601_duration_re = re.compile(
    r"^(?P<sign>[-+]?)"
    r"P"
    r"(?:(?P<days>\d+([\.,]\d+)?)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+([\.,]\d+)?)H)?"
    r"(?:(?P<minutes>\d+([\.,]\d+)?)M)?"
    r"(?:(?P<seconds>\d+([\.,]\d+)?)S)?"
    r")?"
    r"$"
)

# Support PostgreSQL's day-time interval format, e.g. "3 days 04:05:06". The
# year-month and mixed intervals cannot be converted to a timedelta and thus
# aren't accepted.
postgres_interval_re = re.compile(
    r"^"
    r"(?:(?P<days>-?\d+) (days? ?))?"
    r"(?:(?P<sign>[-+])?"
    r"(?P<hours>\d+):"
    r"(?P<minutes>\d\d):"
    r"(?P<seconds>\d\d)"
    r"(?:\.(?P<microseconds>\d{1,6}))?"
    r")?$"
)


def prettify_class_name(name: str) -> str:
    pass


def slugify_class_name(name: str) -> str:
    pass


def slugify_action_name(name: str) -> str:
    if not re.search(r"^[A-Za-z0-9 \-_]+$", name):
        raise ValueError(
            "name must be non-empty and contain only allowed characters"
            " - use `label` for more expressive names"
        )

    return re.sub(r"[_ ]", "-", name).lower()


def secure_filename(filename: str) -> str:
    """Ported from Werkzeug.

    Pass it a filename and it will return a secure version of it. This
    filename can then safely be stored on a regular file system and passed
    to :func:`os.path.join`. The filename returned is an ASCII only string
    for maximum portability.
    On windows systems the function also makes sure that the file is not
    named after one of the special device files.
    """
    pass


class Writer(ABC):
    """https://docs.python.org/3/library/csv.html#writer-objects"""

    @abstractmethod
    def writerow(self, row: list[str]) -> None:
        pass  # pragma: no cover

    @abstractmethod
    def writerows(self, rows: list[list[str]]) -> None:
        pass  # pragma: no cover

    @property
    @abstractmethod
    def dialect(self) -> csv.Dialect:
        pass  # pragma: no cover


class _PseudoBuffer:
    """An object that implements just the write method of the file-like
    interface.
    """

    encoding = "utf-8"

    def write(self, value: T) -> bytes:
        pass


def stream_to_csv(
    callback: Callable[[Writer], AsyncGenerator[T, None]],
) -> Generator[T, None, None]:
    """Function that takes a callable (that yields from a CSV Writer), and
    provides it a writer that streams the output directly instead of
    storing it in a buffer. The direct output stream is intended to go
    inside a `starlette.responses.StreamingResponse`.

    Loosely adapted from here:

    https://docs.djangoproject.com/en/1.8/howto/outputting-csv/
    """
    pass


def get_primary_keys(model: Any) -> tuple[Column, ...]:
    pass


def get_object_identifier(obj: Any) -> Any:
    """Returns a value that uniquely identifies this object."""
    pass


def _object_identifier_parts(id_string: str, model: type) -> tuple[str, ...]:
    pass


def object_identifier_values(id_string: str, model: Any) -> tuple:
    pass


def get_direction(prop: MODEL_PROPERTY) -> str:
    pass


def get_column_python_type(column: Column) -> type:
    pass


def is_relationship(prop: MODEL_PROPERTY) -> bool:
    pass


def parse_interval(value: str) -> timedelta | None:
    pass


def is_falsy_value(value: Any) -> bool:
    pass


def choice_type_coerce_factory(type_: Any) -> Callable[[Any], Any]:
    pass


def is_async_session_maker(session_maker: SESSION_MAKER) -> bool:
    pass


def default_encoder(obj: Any) -> Any:
    pass
