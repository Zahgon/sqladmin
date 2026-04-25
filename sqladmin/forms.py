# mypy: disable-error-code="return-value"

"""
The converters are from Flask-Admin project.
"""

from __future__ import annotations

import enum
import inspect
import sys
from typing import (
    Any,
    Callable,
    Sequence,
    TypeVar,
    Union,
    no_type_check,
)

import anyio
from sqlalchemy import Boolean, select
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import ColumnProperty, RelationshipProperty
from sqlalchemy.sql.elements import Label
from wtforms import (
    DecimalField,
    Field,
    Form,
    IntegerField,
    StringField,
    TextAreaField,
    TimeField,
    validators,
)
from wtforms.fields.core import UnboundField

from sqladmin._types import MODEL_PROPERTY, SESSION_MAKER
from sqladmin._validators import (
    ColorValidator,
    CurrencyValidator,
    PhoneNumberValidator,
    TimezoneValidator,
)
from sqladmin.ajax import QueryAjaxModelLoader
from sqladmin.exceptions import NoConverterFound
from sqladmin.fields import (
    AjaxSelectField,
    AjaxSelectMultipleField,
    BooleanField,
    DateField,
    DateTimeField,
    FileField,
    IntervalField,
    JSONField,
    QuerySelectField,
    QuerySelectMultipleField,
    Select2TagsField,
    SelectField,
    UuidField,
)
from sqladmin.helpers import (
    choice_type_coerce_factory,
    get_direction,
    get_object_identifier,
    is_async_session_maker,
    is_relationship,
)

if sys.version_info >= (3, 8):
    from typing import Protocol
else:
    from typing_extensions import Protocol


class Validator(Protocol):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...  # pragma: no cover

    def __call__(self, form: Form, field: Field) -> None: ...  # pragma: no cover


class ConverterCallable(Protocol):
    def __call__(
        self,
        model: type,
        prop: MODEL_PROPERTY,
        kwargs: dict[str, Any],
    ) -> UnboundField: ...  # pragma: no cover


T_CC = TypeVar("T_CC", bound=ConverterCallable)

_WTFORMS_PRIVATE_ATTRS = {"data", "errors", "process", "validate", "populate_obj"}
WTFORMS_ATTRS = {key: key + "_" for key in _WTFORMS_PRIVATE_ATTRS}
WTFORMS_ATTRS_REVERSED = {v: k for k, v in WTFORMS_ATTRS.items()}


@no_type_check
def converts(*args: str) -> Callable[[T_CC], T_CC]:
    def _inner(func: T_CC) -> T_CC:
        pass

    return _inner


class ModelConverterBase:
    _converters: dict[str, ConverterCallable] = {}

    def __init__(self) -> None:
        super().__init__()
        self._register_converters()

    def _register_converters(self) -> None:
        pass

    async def _prepare_kwargs(
        self,
        prop: MODEL_PROPERTY,
        session_maker: SESSION_MAKER,
        field_args: dict[str, Any],
        field_widget_args: dict[str, Any],
        form_include_pk: bool,
        label: str | None = None,
        loader: QueryAjaxModelLoader | None = None,
    ) -> dict[str, Any] | None:
        pass

    def _prepare_column(
        self,
        prop: ColumnProperty,
        form_include_pk: bool,
        kwargs: dict,
    ) -> Union[dict, None]:
        pass

    async def _prepare_relationship(
        self,
        prop: RelationshipProperty,
        kwargs: dict,
        session_maker: SESSION_MAKER,
        loader: QueryAjaxModelLoader | None = None,
    ) -> dict:
        pass

    async def _prepare_select_options(
        self,
        prop: RelationshipProperty,
        session_maker: SESSION_MAKER,
    ) -> list[tuple[str, Any]]:
        pass

    def get_converter(self, prop: MODEL_PROPERTY) -> ConverterCallable:
        pass

    async def convert(
        self,
        model: type,
        prop: MODEL_PROPERTY,
        session_maker: SESSION_MAKER,
        field_args: dict[str, Any],
        field_widget_args: dict[str, Any],
        form_include_pk: bool,
        label: str | None = None,
        override: type[Field] | None = None,
        form_ajax_refs: dict[str, QueryAjaxModelLoader] | None = None,
    ) -> UnboundField:
        pass

    def _get_identifier_value(self, o: Any) -> str:
        pass


class ModelConverter(ModelConverterBase):
    @staticmethod
    def _string_common(prop: ColumnProperty) -> list[Validator]:
        pass

    @converts("String", "CHAR")  # includes Unicode
    def conv_string(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("Text", "LargeBinary", "Binary")  # includes UnicodeText
    def conv_text(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("Boolean", "dialects.mssql.base.BIT")
    def conv_boolean(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("Date")
    def conv_date(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("Time")
    def conv_time(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("DateTime")
    def conv_datetime(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("Enum")
    def conv_enum(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("Integer")  # includes BigInteger and SmallInteger
    def conv_integer(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("Numeric")  # includes DECIMAL, Float/FLOAT, REAL, and DOUBLE
    def conv_decimal(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        # override default decimal places limit, use database defaults instead
        pass

    @converts("JSON", "JSONB")
    def conv_json(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("Interval")
    def conv_interval(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts(
        "sqlalchemy.dialects.postgresql.base.INET",
        "sqlalchemy.dialects.postgresql.types.INET",
        "sqlalchemy_utils.types.ip_address.IPAddressType",
    )
    def conv_ip_address(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts(
        "sqlalchemy.dialects.postgresql.base.MACADDR",
        "sqlalchemy.dialects.postgresql.types.MACADDR",
    )
    def conv_mac_address(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts(
        "sqlalchemy.dialects.postgresql.base.UUID",
        "sqlalchemy.sql.sqltypes.UUID",
        "sqlalchemy.sql.sqltypes.Uuid",
        "sqlalchemy_utils.types.uuid.UUIDType",
    )
    def conv_uuid(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts(
        "sqlalchemy.dialects.postgresql.base.ARRAY",
        "sqlalchemy.sql.sqltypes.ARRAY",
    )
    def conv_array(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("sqlalchemy_utils.types.email.EmailType")
    def conv_email(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("sqlalchemy_utils.types.url.URLType")
    def conv_url(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("sqlalchemy_utils.types.currency.CurrencyType")
    def conv_currency(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("sqlalchemy_utils.types.timezone.TimezoneType")
    def conv_timezone(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("sqlalchemy_utils.types.phone_number.PhoneNumberType")
    def conv_phone_number(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("sqlalchemy_utils.types.color.ColorType")
    def conv_color(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("sqlalchemy_utils.types.choice.ChoiceType")
    @no_type_check
    def convert_choice_type(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("fastapi_storages.integrations.sqlalchemy.FileType")
    def conv_file(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("fastapi_storages.integrations.sqlalchemy.ImageType")
    def conv_image(
        self,
        model: type,
        prop: ColumnProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("ONETOONE")
    def conv_one_to_one(
        self,
        model: type,
        prop: RelationshipProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("MANYTOONE")
    def conv_many_to_one(
        self,
        model: type,
        prop: RelationshipProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass

    @converts("MANYTOMANY", "ONETOMANY")
    def conv_many_to_many(
        self,
        model: type,
        prop: RelationshipProperty,
        kwargs: dict[str, Any],
    ) -> UnboundField:
        pass


async def get_model_form(
    model: type,
    session_maker: SESSION_MAKER,
    only: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    column_labels: dict[str, str] | None = None,
    form_args: dict[str, dict[str, Any]] | None = None,
    form_widget_args: dict[str, dict[str, Any]] | None = None,
    form_class: type[Form] = Form,
    form_overrides: dict[str, type[Field]] | None = None,
    form_ajax_refs: dict[str, QueryAjaxModelLoader] | None = None,
    form_include_pk: bool = False,
    form_converter: type[ModelConverterBase] = ModelConverter,
) -> type[Form]:
    pass
