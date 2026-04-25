# mypy: disable-error-code="override"

from __future__ import annotations

import json
import operator
from enum import Enum
from typing import Any, Callable, Generator
from uuid import UUID

from wtforms import Form, ValidationError, fields, widgets

from sqladmin import widgets as sqladmin_widgets
from sqladmin.ajax import QueryAjaxModelLoader
from sqladmin.helpers import get_object_identifier, parse_interval

__all__ = [
    "AjaxSelectField",
    "AjaxSelectMultipleField",
    "DateField",
    "DateTimeField",
    "IntervalField",
    "JSONField",
    "QuerySelectField",
    "QuerySelectMultipleField",
    "SelectField",
    "Select2TagsField",
]


class DateField(fields.DateField):
    """
    Add custom DatePickerWidget for data-format and data-date-format fields
    """

    widget = sqladmin_widgets.DatePickerWidget()  # type: ignore[assignment]


class DateTimeField(fields.DateTimeField):
    """
    Allows modifying the datetime format of a DateTimeField using form_args.
    """

    widget = sqladmin_widgets.DateTimePickerWidget()  # type: ignore[assignment]


class IntervalField(fields.StringField):
    """
    A text field which stores a `datetime.timedelta` object.
    """

    def process_formdata(self, valuelist: list[str]) -> None:
        pass


class SelectField(fields.SelectField):
    def __init__(
        self,
        label: str | None = None,
        validators: list | None = None,
        coerce: type = str,
        choices: list | Callable | None = None,
        allow_blank: bool = False,
        blank_text: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(label, validators, coerce, choices, **kwargs)
        self.allow_blank = allow_blank
        self.blank_text = blank_text or " "

    def iter_choices(self) -> Generator[tuple[str, str, bool, dict], None, None]:
        pass

    def process_formdata(self, valuelist: list[str]) -> None:
        pass

    def pre_validate(self, form: Form) -> None:
        pass


class JSONField(fields.TextAreaField):
    def _value(self) -> str:
        pass

    def process_formdata(self, valuelist: list[str]) -> None:
        pass


class QuerySelectField(fields.SelectFieldBase):
    widget = widgets.Select()

    def __init__(
        self,
        data: list | None = None,
        label: str | None = None,
        validators: list | None = None,
        get_label: Callable | str | None = None,
        allow_blank: bool = False,
        blank_text: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(label=label, validators=validators, **kwargs)

        self._select_data = data or []

        if get_label is None:
            self.get_label = lambda x: x
        elif isinstance(get_label, str):
            self.get_label = operator.attrgetter(get_label)
        else:
            self.get_label = get_label

        self.allow_blank = allow_blank
        self.blank_text = blank_text
        self._data: tuple | None
        self._formdata: str | list[str] | None

    @property
    def data(self) -> tuple | None:
        pass

    @data.setter
    def data(self, data: tuple | None) -> None:
        pass

    def iter_choices(self) -> Generator[tuple[str, str, bool, dict], None, None]:
        pass

    def process_formdata(self, valuelist: list[str]) -> None:
        pass

    def pre_validate(self, form: Form) -> None:
        pass


class QuerySelectMultipleField(QuerySelectField):
    """
    Very similar to QuerySelectField with the difference that this will
    display a multiple select. The data property will hold a list with ORM
    model instances and will be an empty list when no value is selected.

    If any of the items in the data list or submitted form data cannot be
    found in the query, this will result in a validation error.
    """

    widget = widgets.Select(multiple=True)

    def __init__(
        self,
        data: list | None = None,
        label: str | None = None,
        validators: list | None = None,
        default: Any = None,
        **kwargs: Any,
    ) -> None:
        default = default or []
        super().__init__(label=label, validators=validators, default=default, **kwargs)

        self._select_data = data or []

        if kwargs.get("allow_blank", False):
            import warnings

            warnings.warn(
                "allow_blank=True does not do anything for QuerySelectMultipleField."
            )
        self._invalid_formdata = False
        self._formdata: list[str] | None = None
        self._data: tuple | None = None

    @property
    def data(self) -> tuple | None:
        pass

    @data.setter
    def data(self, data: tuple | None) -> None:
        pass

    def iter_choices(self) -> Generator[tuple[str, Any, bool, dict], None, None]:
        pass

    def process_formdata(self, valuelist: list[str]) -> None:
        pass

    def pre_validate(self, form: Form) -> None:
        pass


class AjaxSelectField(fields.SelectFieldBase):
    widget = sqladmin_widgets.AjaxSelect2Widget()
    separator = ","

    def __init__(
        self,
        loader: QueryAjaxModelLoader,
        label: str | None = None,
        validators: list | None = None,
        allow_blank: bool = False,
        **kwargs: Any,
    ) -> None:
        kwargs.pop("data", None)  # Handled by JS side
        self.loader = loader
        self.allow_blank = allow_blank
        super().__init__(label, validators, **kwargs)

    @property
    def data(self) -> Any:
        pass

    @data.setter
    def data(self, data: Any) -> None:
        pass

    def process_formdata(self, valuelist: list) -> None:
        pass

    def pre_validate(self, form: Form) -> None:
        pass


class AjaxSelectMultipleField(fields.SelectFieldBase):
    widget = sqladmin_widgets.AjaxSelect2Widget(multiple=True)  # type: ignore[assignment]
    separator = ","

    def __init__(
        self,
        loader: QueryAjaxModelLoader,
        label: str | None = None,
        validators: list | None = None,
        default: list | None = None,
        allow_blank: bool = False,
        **kwargs: Any,
    ) -> None:
        kwargs.pop("data", None)  # Handled by JS side
        self.loader = loader
        self.allow_blank = allow_blank
        default = default or []
        self._formdata: set[Any] = set()

        super().__init__(label, validators, default=default, **kwargs)

    @property
    def data(self) -> Any:
        pass

    @data.setter
    def data(self, data: Any) -> None:
        pass

    def process_formdata(self, valuelist: list) -> None:
        pass


class Select2TagsField(fields.SelectField):
    widget = sqladmin_widgets.Select2TagsWidget()  # type: ignore[assignment]

    def pre_validate(self, form: Form) -> None: ...

    def process_formdata(self, valuelist: list) -> None:
        pass

    def process_data(self, value: list | None) -> None:
        pass


class FileField(fields.FileField):
    """
    File field which is clearable.
    """

    widget = sqladmin_widgets.FileInputWidget()


class BooleanField(fields.BooleanField):
    """
    Boolean checkbox field.
    """

    widget = sqladmin_widgets.BooleanInputWidget()


class UuidField(fields.StringField):
    def process_formdata(self, valuelist: list) -> None:
        """Convert submitted string to UUID object."""
        pass

    def process_data(self, value: str | UUID | None) -> None:
        """Handle initial data (from object or default)."""
        pass
