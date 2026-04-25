from __future__ import annotations

import json
import time
import warnings
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
    no_type_check,
)
from typing import cast as typing_cast
from urllib.parse import urlencode

import anyio
from sqlalchemy import Column, String, asc, cast, desc, false, func, inspect, or_
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import DetachedInstanceError
from sqlalchemy.sql.elements import ClauseElement
from sqlalchemy.sql.expression import Select, select
from starlette.datastructures import URL
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import StreamingResponse
from wtforms import Field, Form
from wtforms.fields.core import UnboundField

from sqladmin._queries import Query
from sqladmin._types import (
    MODEL_ATTR,
    SESSION_MAKER,
    ColumnFilter,
    OperationColumnFilter,
    SimpleColumnFilter,
)
from sqladmin.ajax import create_ajax_loader
from sqladmin.exceptions import InvalidModelError
from sqladmin.formatters import BASE_FORMATTERS
from sqladmin.forms import ModelConverter, ModelConverterBase, get_model_form
from sqladmin.helpers import (
    Writer,
    default_encoder,
    get_object_identifier,
    get_primary_keys,
    object_identifier_values,
    prettify_class_name,
    secure_filename,
    slugify_class_name,
    stream_to_csv,
)

# stream_to_csv,
from sqladmin.pagination import Pagination
from sqladmin.pretty_export import PrettyExport
from sqladmin.templating import Jinja2Templates

if TYPE_CHECKING:
    from sqladmin.application import BaseAdmin

__all__ = [
    "BaseView",
    "ModelView",
    "ModelView",
]


class ModelViewMeta(type):
    """Metaclass used to specify class variables in ModelView.

    Danger:
        This class should almost never be used directly.
    """

    @no_type_check
    def __new__(mcs, name, bases, attrs: dict, **kwargs: Any):
        cls: Type["ModelView"] = super().__new__(mcs, name, bases, attrs)

        model = kwargs.get("model")

        if not model:
            return cls

        try:
            inspect(model)
        except NoInspectionAvailable as exc:
            raise InvalidModelError(
                f"Class {model.__name__} is not a SQLAlchemy model."
            ) from exc

        cls.pk_columns = get_primary_keys(model)
        cls.identity = slugify_class_name(model.__name__)
        cls.model = model

        cls.name = attrs.get("name", prettify_class_name(cls.model.__name__))
        cls.name_plural = attrs.get("name_plural", f"{cls.name}s")

        mcs._check_conflicting_options(["column_list", "column_exclude_list"], attrs)
        mcs._check_conflicting_options(["form_columns", "form_excluded_columns"], attrs)
        mcs._check_conflicting_options(
            ["column_details_list", "column_details_exclude_list"], attrs
        )
        mcs._check_conflicting_options(
            ["column_export_list", "column_export_exclude_list"], attrs
        )

        return cls

    @classmethod
    def _check_conflicting_options(mcs, keys: List[str], attrs: dict) -> None:
        pass


class BaseModelView:
    def is_visible(self, request: Request) -> bool:
        """Override this method if you want dynamically
        hide or show administrative views from SQLAdmin menu structure
        By default, item is visible in menu.
        Both is_visible and is_accessible to be displayed in menu.
        """
        pass

    def is_accessible(self, request: Request) -> bool:
        """Override this method to add permission checks.
        SQLAdmin does not make any assumptions about the authentication system
        used in your application, so it is up to you to implement it.
        By default, it will allow access for everyone.
        """
        pass


class BaseView(BaseModelView):
    """Base class for defining admnistrative views for the model.

    ???+ usage
        ```python
        from sqladmin import BaseView, expose

        class CustomAdmin(BaseView):
            name = "Custom Page"
            icon = "fa-solid fa-chart-line"

            @expose("/custom", methods=["GET"])
            async def test_page(self, request: Request):
                return await self.templates.TemplateResponse(request, "custom.html")

        admin.add_base_view(CustomAdmin)
        ```
    """

    # Internals
    is_model: ClassVar[bool] = False
    templates: ClassVar[Jinja2Templates]
    _admin_ref: ClassVar["BaseAdmin"]

    name: ClassVar[str] = ""
    """Name of the view to be displayed."""

    identity: ClassVar[str] = ""
    """Same as name but it will be used for URL of the endpoints."""

    methods: ClassVar[List[str]] = ["GET"]
    """List of method names for the endpoint.
    By default it's set to `["GET"]` only.
    """

    include_in_schema: ClassVar[bool] = True
    """Control whether this endpoint
    should be included in the schema.
    """

    icon: ClassVar[str] = ""
    """Display icon for ModelAdmin in the sidebar.
    Currently only supports FontAwesome and Tabler icons.
    """

    category: ClassVar[str] = ""
    """Category name to group views together."""

    category_icon: ClassVar[str] = ""
    """Display icon for category in the sidebar."""


class ModelView(BaseView, metaclass=ModelViewMeta):
    """Base class for defining admnistrative behaviour for the model.

    ???+ usage
        ```python
        from sqladmin import ModelView

        from mymodels import User # SQLAlchemy model

        class UserAdmin(ModelView, model=User):
            can_create = True
        ```
    """

    model: ClassVar[type]

    # Internals
    pk_columns: ClassVar[Tuple[Column]]
    session_maker: ClassVar[SESSION_MAKER]
    is_async: ClassVar[bool] = False
    is_model: ClassVar[bool] = True
    ajax_lookup_url: ClassVar[str] = ""

    name_plural: ClassVar[str] = ""
    """Plural name of ModelView.
    Default value is Model class name + `s`.
    """

    # Permissions
    can_create: ClassVar[bool] = True
    """Permission for creating new Models. Default value is set to `True`."""

    can_edit: ClassVar[bool] = True
    """Permission for editing Models. Default value is set to `True`."""

    can_delete: ClassVar[bool] = True
    """Permission for deleting Models. Default value is set to `True`."""

    can_view_details: ClassVar[bool] = True
    """Permission for viewing full details of Models.
    Default value is set to `True`.
    """

    can_export: ClassVar[bool] = True
    """Permission for exporting lists of Models.
    Default value is set to `True`.
    """

    # List page
    column_list: ClassVar[Union[str, Sequence[MODEL_ATTR]]] = []
    """List of columns to display in `List` page.
    Columns can either be string names or SQLAlchemy columns.

    ???+ note
        By default only Model primary key is displayed.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_list = [User.id, User.name]
        ```
    """

    column_exclude_list: ClassVar[Sequence[MODEL_ATTR]] = []
    """List of columns to exclude in `List` page.
    Columns can either be string names or SQLAlchemy columns.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_exclude_list = [User.id, User.name]
        ```
    """

    column_formatters: ClassVar[Dict[MODEL_ATTR, Callable[[type, Column], Any]]] = {}
    """Dictionary of list view column formatters.
    Columns can either be string names or SQLAlchemy columns.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_formatters = {User.name: lambda m, a: m.name[:10]}
        ```

    The format function has the prototype:
    ???+ formatter
        ```python
        def formatter(model, attribute):
            # `model` is model instance
            # `attribute` is a Union[ColumnProperty, RelationshipProperty]
            pass
        ```
    """

    page_size: ClassVar[int] = 10
    """Default number of items to display in `List` page pagination.
    Default value is set to `10`.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            page_size = 25
        ```
    """

    page_size_options: ClassVar[Sequence[int]] = [10, 25, 50, 100]
    """Pagination choices displayed in `List` page.
    Default value is set to `[10, 25, 50, 100]`.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            page_size_options = [50, 100]
        ```
    """

    column_searchable_list: ClassVar[Sequence[MODEL_ATTR]] = []
    """A collection of the searchable columns.
    It is assumed that only text-only fields are searchable,
    but it is up to the model implementation to decide.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_searchable_list = [User.name]
        ```
    """

    search_auto_submit: ClassVar[bool] = True
    """Automatically submit search while typing in list view.

    When set to `True`, typing in the search input triggers a delayed search.
    Set to `False` to require pressing `Enter` or clicking the search button.
    """

    column_filters: ClassVar[Sequence[ColumnFilter]] = []
    """Collection of the filterable columns for the list view.
    Columns can either be string names or SQLAlchemy columns.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_filters = [User.is_admin]
        ```
    """

    column_sortable_list: ClassVar[Sequence[MODEL_ATTR]] = []
    """Collection of the sortable columns for the list view.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_sortable_list = [User.name]
        ```
    """

    column_default_sort: ClassVar[Union[MODEL_ATTR, Tuple[MODEL_ATTR, bool], list]] = []
    """Default sort column if no sorting is applied.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_default_sort = "email"
        ```

    You can use tuple to control ascending descending order. In following example, items
    will be sorted in descending order:

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_default_sort = ("email", True)
        ```

    If you want to sort by more than one column, you can pass a list of tuples

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_default_sort = [("email", True), ("name", False)]
        ```
    """

    # Details page
    column_details_list: ClassVar[Union[str, Sequence[MODEL_ATTR]]] = []
    """List of columns to display in `Detail` page.
    Columns can either be string names or SQLAlchemy columns.

    ???+ note
        By default all columns of Model are displayed.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_details_list = [User.id, User.name, User.mail]
        ```
    """

    column_details_exclude_list: ClassVar[Sequence[MODEL_ATTR]] = []
    """List of columns to exclude from displaying in `Detail` page.
    Columns can either be string names or SQLAlchemy columns.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_details_exclude_list = [User.mail]
        ```
    """

    column_formatters_detail: ClassVar[
        Dict[MODEL_ATTR, Callable[[type, Column], Any]]
    ] = {}
    """Dictionary of details view column formatters.
    Columns can either be string names or SQLAlchemy columns.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_formatters_detail = {User.name: lambda m, a: m.name[:10]}
        ```

    The format function has the prototype:
    ???+ formatter
        ```python
        def formatter(model, attribute):
            # `model` is model instance
            # `attribute` is a Union[ColumnProperty, RelationshipProperty]
            pass
        ```
    """

    save_as: ClassVar[bool] = False
    """Set `save_as` to enable a "save as new" feature on admin change forms.

    Normally, objects have three save options:
    ``Save`, `Save and continue editing` and `Save and add another`.

    If save_as is True, `Save and add another` will be replaced
    by a `Save as new` button
    that creates a new object (with a new ID)
    rather than updating the existing object.

    By default, `save_as` is set to `False`.
    """

    save_as_continue: ClassVar[bool] = True
    """When `save_as=True`, the default redirect after saving the new object
    is to the edit view for that object.
    If you set `save_as_continue=False`, the redirect will be to the list view.

    By default, `save_as_continue` is set to `True`.
    """

    # Templates
    list_template: ClassVar[str] = "sqladmin/list.html"
    """List view template. Default is `sqladmin/list.html`."""

    create_template: ClassVar[str] = "sqladmin/create.html"
    """Create view template. Default is `sqladmin/create.html`."""

    details_template: ClassVar[str] = "sqladmin/details.html"
    """Details view template. Default is `sqladmin/details.html`."""

    edit_template: ClassVar[str] = "sqladmin/edit.html"
    """Edit view template. Default is `sqladmin/edit.html`."""

    # Template configuration
    show_compact_lists: ClassVar[bool] = True
    """Show compact lists. Default is `True`. 
    If False, when showing lists of objects, each object will be \
    displayed in a separate line."""

    # Export
    column_export_list: ClassVar[List[MODEL_ATTR]] = []
    """List of columns to include when exporting.
    Columns can either be string names or SQLAlchemy columns.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_export_list = [User.id, User.name]
        ```
    """

    column_export_exclude_list: ClassVar[List[MODEL_ATTR]] = []
    """List of columns to exclude when exporting.
    Columns can either be string names or SQLAlchemy columns.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_export_exclude_list = [User.id, User.name]
        ```
    """

    export_types: ClassVar[List[str]] = ["csv", "json"]
    """A list of available export filetypes.
    Currently only `csv` is supported.
    """

    export_max_rows: ClassVar[int] = 0
    """Maximum number of rows allowed for export.
    Unlimited by default.
    """

    use_pretty_export: ClassVar[bool] = False
    """
    Enable export of CSV files using column labels and column formatters.

    If set to True, the export will apply column labels and formatting logic 
    used in the list template.
    Otherwise, raw database values and field names will be used.

    You can override cell formatting per column by implementing `custom_export_cell`.
    """

    # Form
    form: ClassVar[Optional[Type[Form]]] = None
    """Form class.
    Override if you want to use custom form for your model.
    Will completely disable form scaffolding functionality.

    ???+ example
        ```python
        class MyForm(Form):
            name = StringField('Name')

        class MyModelView(ModelView, model=User):
            form = MyForm
        ```
    """

    form_base_class: ClassVar[Type[Form]] = Form
    """Base form class.
    Will be used by form scaffolding function when creating model form.
    Useful if you want to have custom constructor or override some fields.

    ???+ example
        ```python
        class MyBaseForm(Form):
            def do_something(self):
                pass

        class MyModelView(ModelView, model=User):
            form_base_class = MyBaseForm
        ```
    """

    form_args: ClassVar[Dict[str, Dict[str, Any]]] = {}
    """Dictionary of form field arguments.
    Refer to WTForms documentation for list of possible options.

    ???+ example
        ```python
        from wtforms.validators import DataRequired

        class MyModelView(ModelView, model=User):
            form_args = dict(
                name=dict(label="User Name", validators=[DataRequired()])
            )
        ```
    """

    form_widget_args: ClassVar[Dict[str, Dict[str, Any]]] = {}
    """Dictionary of form widget rendering arguments.
    Use this to customize how widget is rendered without using custom template.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            form_widget_args = {
                "email": {
                    "readonly": True,
                },
            }
        ```
    """

    form_columns: ClassVar[Sequence[MODEL_ATTR]] = []
    """List of columns to include in the form.
    Columns can either be string names or SQLAlchemy columns.

    ???+ note
        By default all columns of Model are included in the form.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            form_columns = [User.name, User.mail]
        ```
    """

    form_excluded_columns: ClassVar[Sequence[MODEL_ATTR]] = []
    """List of columns to exclude from the form.
    Columns can either be string names or SQLAlchemy columns.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            form_excluded_columns = [User.id]
        ```
    """

    form_overrides: ClassVar[Dict[str, Type[Field]]] = {}
    """Dictionary of form column overrides.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            form_overrides = dict(name=wtf.FileField)
        ```
    """

    form_include_pk: ClassVar[bool] = False
    """Control if form should include primary key columns or not.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            form_include_pk = True
        ```
    """

    form_ajax_refs: ClassVar[Dict[str, dict]] = {}
    """Use Ajax for foreign key model loading.
    Should contain dictionary, where key is field name and
    value is a dictionary which configures Ajax lookups.

    ???+example
        ```python
        class UserAdmin(ModelAdmin, model=User):
            form_ajax_refs = {
                'address': {
                    'fields': ('street', 'zip_code'),
                    'order_by': ('id',),
                }
            }
        ```
    """

    form_converter: ClassVar[Type[ModelConverterBase]] = ModelConverter
    """Custom form converter class.
    Useful if you want to add custom form conversion in addition to the defaults.

    ???+ example
        ```python
        class PhoneNumberConverter(ModelConverter):
            pass

        class UserAdmin(ModelAdmin, model=User):
            form_converter = PhoneNumberConverter
        ```
    """

    form_rules: ClassVar[list[str]] = []
    """List of rendering rules for model creation and edit form.
    This property changes default form rendering behavior and to rearrange
    order of rendered fields, add some text between fields, group them, etc.
    If not set, will use default Flask-Admin form rendering logic.

    ???+ example
        ```python
        class UserAdmin(ModelAdmin, model=User):
            form_rules = [
                "first_name",
                "last_name",
            ]
        ```
    """

    form_create_rules: ClassVar[list[str]] = []
    """Customized rules for the create form. Cannot be specified with `form_rules`."""

    form_edit_rules: ClassVar[list[str]] = []
    """Customized rules for the edit form. Cannot be specified with `form_rules`."""

    # General options
    column_labels: ClassVar[Dict[MODEL_ATTR, str]] = {}
    """A mapping of column labels, used to map column names to new names.
    Dictionary keys can be string names or SQLAlchemy columns with string values.

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_labels = {User.mail: "Email"}
        ```
    """

    column_type_formatters: ClassVar[Dict[Type, Callable]] = BASE_FORMATTERS
    """Dictionary of value type formatters to be used in the list view.

    By default, two types are formatted:

        - None will be displayed as an empty string
        - bool will be displayed as a checkmark if it is True otherwise as an X.

    If you don't like the default behavior and don't want any type formatters applied,
    just override this property with an empty dictionary:

    ???+ example
        ```python
        class UserAdmin(ModelView, model=User):
            column_type_formatters = dict()
        ```
    """

    def __init__(self) -> None:
        self._mapper = inspect(self.model)
        self._prop_names = [attr.key for attr in self._mapper.attrs]
        self._relations = [
            getattr(self.model, relation.key) for relation in self._mapper.relationships
        ]
        self._relation_names = [relation.key for relation in self._mapper.relationships]

        self._column_labels = self._build_column_pairs(self.column_labels)
        self._column_labels_value_by_key = {
            v: k for k, v in self._column_labels.items()
        }

        self._list_prop_names = self.get_list_columns()
        self._list_relation_names = [
            name for name in self._list_prop_names if name in self._relation_names
        ]
        self._list_relations = [
            getattr(self.model, name) for name in self._list_relation_names
        ]

        self._details_prop_names = self.get_details_columns()
        self._details_relation_names = [
            name for name in self._details_prop_names if name in self._relation_names
        ]
        self._details_relations = [
            getattr(self.model, name) for name in self._details_relation_names
        ]

        self._list_formatters = self._build_column_pairs(self.column_formatters)
        self._detail_formatters = self._build_column_pairs(
            self.column_formatters_detail
        )

        self._form_prop_names = self.get_form_columns()
        self._form_relation_names = [
            name for name in self._form_prop_names if name in self._relation_names
        ]
        self._form_relations = [
            getattr(self.model, name) for name in self._form_relation_names
        ]

        self._export_prop_names = self.get_export_columns()

        self._search_fields = [
            self._get_prop_name(attr) for attr in self.column_searchable_list
        ]
        self._sort_fields = [
            self._get_prop_name(attr) for attr in self.column_sortable_list
        ]

        self._form_ajax_refs = {}
        for name, options in self.form_ajax_refs.items():
            self._form_ajax_refs[name] = create_ajax_loader(
                model_admin=self, name=name, options=options
            )

        self._refresh_form_rules_cache()

        self._custom_actions_in_list: Dict[str, str] = {}
        self._custom_actions_in_detail: Dict[str, str] = {}
        self._custom_actions_confirmation: Dict[str, str] = {}

    def _run_arbitrary_query_sync(self, stmt: ClauseElement) -> Any:
        pass

    async def _run_arbitrary_query(self, stmt: ClauseElement) -> Any:
        pass

    def _run_query_sync(self, stmt: ClauseElement) -> Any:
        pass

    async def _run_query(self, stmt: ClauseElement) -> Any:
        pass

    def _url_for_delete(self, request: Request, obj: Any) -> str:
        pass

    def _url_for_details_with_prop(self, request: Request, obj: Any, prop: str) -> URL:
        pass

    def _url_for_action(self, request: Request, action_name: str) -> str:
        pass

    def _build_url_for(self, name: str, request: Request, obj: Any) -> URL:
        pass

    def _get_prop_name(self, prop: MODEL_ATTR) -> str:
        pass

    def _get_default_sort(self) -> List[Tuple[str, bool]]:
        pass

    def _default_formatter(self, value: Any) -> Any:
        pass

    def validate_page_number(self, number: Union[str, None], default: int) -> int:
        pass

    async def count(self, request: Request, stmt: Optional[Select] = None) -> int:
        pass

    async def list(self, request: Request) -> Pagination:
        pass

    async def get_model_objects(
        self, request: Request, limit: Union[int, None] = 0
    ) -> List[Any]:
        # For unlimited rows this should pass None
        pass

    async def _get_object_by_pk(self, stmt: Select) -> Any:
        pass

    async def get_object_for_details(self, request: Request) -> Any:
        pass

    async def get_object_for_edit(self, request: Request) -> Any:
        pass

    async def get_object_for_delete(self, value: Any) -> Any:
        pass

    def _stmt_by_identifier(self, identifier: str) -> Select:
        pass

    async def get_prop_value(self, obj: Any, prop: str) -> Any:
        pass

    async def _lazyload_prop(self, obj: Any, prop: str) -> Any:
        pass

    async def get_list_value(self, obj: Any, prop: str) -> Tuple[Any, Any]:
        """Get tuple of (value, formatted_value) for the list view."""
        pass

    async def get_detail_value(self, obj: Any, prop: str) -> Tuple[Any, Any]:
        """Get tuple of (value, formatted_value) for the detail view."""
        pass

    def _build_column_list(
        self,
        defaults: List[str],
        include: Optional[Union[str, Sequence[MODEL_ATTR]]] = None,
        exclude: Optional[Union[str, Sequence[MODEL_ATTR]]] = None,
    ) -> List[str]:
        """This function generalizes constructing a list of columns
        for any sequence of inclusions or exclusions.
        """
        pass

    def get_list_columns(self) -> List[str]:
        """Get list of properties to display in List page."""
        pass

    def get_details_columns(self) -> List[str]:
        """Get list of properties to display in Detail page."""
        pass

    def get_form_columns(self) -> List[str]:
        """Get list of properties to display in the form."""
        pass

    def get_export_columns(self) -> List[str]:
        """Get list of properties to export."""
        pass

    def get_filters(self) -> List[ColumnFilter]:
        """Get list of filters."""
        pass

    async def on_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        """Perform some actions before a model is created or updated.
        By default does nothing.
        """

    async def after_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        """Perform some actions after a model was created
        or updated and committed to the database.
        By default does nothing.
        """

    def _build_column_pairs(
        self,
        pair: Dict[Any, Any],
    ) -> Dict[str, Any]:
        pass

    async def delete_model(self, request: Request, pk: Any) -> None:
        pass

    async def insert_model(self, request: Request, data: dict) -> Any:
        pass

    async def update_model(self, request: Request, pk: str, data: dict) -> Any:
        pass

    async def on_model_delete(self, model: Any, request: Request) -> None:
        """Perform some actions before a model is deleted.
        By default does nothing.
        """

    async def after_model_delete(self, model: Any, request: Request) -> None:
        """Perform some actions after a model is deleted.
        By default do nothing.
        """

    async def check_can_view_details(self, request: Request, model: Any) -> bool:
        """
        You can add a custom model attribute checker before view details.
        """
        pass

    async def check_can_edit(self, request: Request, model: Any) -> bool:
        """
        You can add a custom model attribute checker before edit.
        """
        pass

    async def check_can_delete(self, request: Request, model: Any) -> bool:
        """
        You can add a custom model attribute checker before delete.
        """
        pass

    async def scaffold_form(self, rules: List[str] | None = None) -> Type[Form]:
        pass

    def search_placeholder(self) -> str:
        """Return search placeholder text.

        ???+ example
            ```python
            class UserAdmin(ModelView, model=User):
                column_labels = dict(name="Name", email="Email")
                column_searchable_list = [User.name, User.email]

            # placeholder is: "Name, Email"
            ```
        """
        pass

    def _join_relationship_paths(
        self,
        stmt: Select,
        field_path: str,
        joined_paths: Set[str],
    ) -> Tuple[Select, Any]:
        """Join relationship paths and return the statement and target model.

        Navigates through a dotted relationship path (e.g. ``user.profile.role``)
        and joins each segment via its relationship attribute, which lets
        SQLAlchemy pick the correct foreign key when a model has multiple
        relationships to the same target. Paths are tracked to avoid duplicate
        joins within a single call; SQLAlchemy itself dedupes joins on the same
        relationship attribute across calls.
        """
        pass

    def search_query(self, stmt: Select, term: str) -> Select:
        """Specify the search query given the SQLAlchemy statement
        and term to search for.
        It can be used for doing more complex queries like JSON objects. For example:

        ```py
        return stmt.filter(MyModel.name == term)
        ```
        """
        pass

    def list_query(self, request: Request) -> Select:
        """
        The SQLAlchemy select expression used for the list page which can be customized.
        By default it will select all objects without any filters.
        """
        pass

    def details_query(self, request: Request) -> Select:
        """
        The SQLAlchemy select expression used for the details page which can be
        customized. By default it will select all objects without any filters.
        """
        pass

    def edit_form_query(self, request: Request) -> Select:
        pass

    def form_edit_query(self, request: Request) -> Select:
        """
        The SQLAlchemy select expression used for the edit form page which can be
        customized. By default it will select the object by primary key(s) without any
        additional filters.
        """
        pass

    def count_query(self, request: Request) -> Select:
        """
        The SQLAlchemy select expression used for the count query
        which can be customized.
        By default it will select all objects without any filters.
        """
        pass

    def sort_query(self, stmt: Select, request: Request) -> Select:
        """
        A method that is called every time the fields are sorted
        and that can be customized.
        By default, sorting takes place by default fields.

        The 'sortBy' and 'sort' query parameters are available in this request context.
        """
        pass

    def get_export_name(self, export_type: str) -> str:
        """The file name when exporting."""
        pass

    async def export_data(
        self,
        data: List[Any],
        export_type: str = "csv",
    ) -> StreamingResponse:
        pass

    async def _export_csv(
        self,
        data: List[Any],
    ) -> StreamingResponse:
        pass

    async def _export_json(
        self,
        data: List[Any],
        ensure_ascii: bool = False,
    ) -> StreamingResponse:
        pass

    async def custom_export_cell(
        self,
        row: Any,
        name: str,
        value: Any,
    ) -> Optional[str]:
        """
        Override to provide custom formatting for a specific cell in pretty export.

        Return a string to override the default formatting for the given field,
        or return None to fall back to `base_export_cell`.

        Only used when `use_pretty_export = True`.
        """
        pass

    def _refresh_form_rules_cache(self) -> None:
        pass

    def _validate_form_class(self, ruleset: List[Any], form_class: Type[Form]) -> None:
        pass
