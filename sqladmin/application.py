from __future__ import annotations

import inspect
import io
import logging
from types import MethodType
from typing import (
    Any,
    Awaitable,
    Callable,
    Sequence,
    cast,
    no_type_check,
)
from urllib.parse import parse_qsl, urljoin

from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader, PrefixLoader
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from starlette.applications import Starlette
from starlette.datastructures import URL, FormData, MultiDict, UploadFile
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from sqladmin._menu import CategoryMenu, Menu, ViewMenu
from sqladmin._types import ENGINE_TYPE, SESSION_MAKER
from sqladmin.ajax import QueryAjaxModelLoader
from sqladmin.authentication import AuthenticationBackend, login_required
from sqladmin.flash import get_flashed_messages
from sqladmin.forms import WTFORMS_ATTRS, WTFORMS_ATTRS_REVERSED
from sqladmin.helpers import (
    get_object_identifier,
    is_async_session_maker,
    slugify_action_name,
)
from sqladmin.models import BaseView, ModelView
from sqladmin.templating import Jinja2Templates

__all__ = [
    "Admin",
    "expose",
    "action",
]

logger = logging.getLogger(__name__)


class BaseAdmin:
    """Base class for implementing Admin interface.

    Danger:
        This class should almost never be used directly.
    """

    def __init__(
        self,
        app: Starlette,
        engine: ENGINE_TYPE | None = None,
        session_maker: SESSION_MAKER | None = None,
        base_url: str = "/admin",
        title: str = "Admin",
        logo_url: str | None = None,
        favicon_url: str | None = None,
        templates_dir: str = "templates",
        middlewares: Sequence[Middleware] | None = None,
        authentication_backend: AuthenticationBackend | None = None,
    ) -> None:
        self.app = app
        self.engine = engine
        self.base_url = base_url
        self.templates_dir = templates_dir
        self.title = title
        self.logo_url = logo_url
        self.favicon_url = favicon_url

        if session_maker:
            self.session_maker = session_maker
        elif isinstance(self.engine, Engine):
            self.session_maker = sessionmaker(bind=self.engine, class_=Session)
        else:
            self.session_maker = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
            )

        self.session_maker.configure(autoflush=False, autocommit=False)
        self.is_async = is_async_session_maker(self.session_maker)

        middlewares = list(middlewares or [])
        self.authentication_backend = authentication_backend
        if authentication_backend:
            middlewares.extend(authentication_backend.middlewares)

        self.admin = Starlette(middleware=middlewares)
        self.templates = self.init_templating_engine()
        self._views: list[BaseView | ModelView] = []
        self._menu = Menu()

    def init_templating_engine(self) -> Jinja2Templates:
        pass

    @property
    def views(self) -> list[BaseView | ModelView]:
        """Get list of ModelView and BaseView instances lazily.

        Returns:
            List of ModelView and BaseView instances added to Admin.
        """
        pass

    def _find_model_view(self, identity: str) -> ModelView:
        pass

    def add_view(self, view: type[ModelView] | type[BaseView]) -> None:
        """Add ModelView or BaseView classes to Admin.
        This is a shortcut that will handle both `add_model_view` and `add_base_view`.
        """

        if view.is_model:
            self.add_model_view(view)  # type: ignore
        else:
            self.add_base_view(view)

    @staticmethod
    def _find_decorated_funcs(
        view: type[BaseView | ModelView],
        view_instance: BaseView | ModelView,
        handle_fn: Callable[
            [MethodType, type[BaseView | ModelView], BaseView | ModelView],
            None,
        ],
    ) -> None:
        funcs = inspect.getmembers(view_instance, predicate=inspect.ismethod)

        for _, func in sorted(
            funcs,
            key=lambda x: inspect.getsourcelines(x[1])[1],
            reverse=True,
        ):
            handle_fn(func, view, view_instance)

    def _handle_action_decorated_func(
        self,
        func: MethodType,
        view: type[BaseView | ModelView],
        view_instance: BaseView | ModelView,
    ) -> None:
        pass

    def _handle_expose_decorated_func(
        self,
        func: MethodType,
        view: type[BaseView | ModelView],
        view_instance: BaseView | ModelView,
    ) -> None:
        pass

    def add_model_view(self, view: type[ModelView]) -> None:
        """Add ModelView to the Admin.

        ???+ usage
            ```python
            from sqladmin import Admin, ModelView

            class UserAdmin(ModelView, model=User):
                pass

            admin.add_model_view(UserAdmin)
            ```
        """

        view._admin_ref = self
        # Set database engine from Admin instance
        view.session_maker = self.session_maker
        view.is_async = self.is_async
        view.ajax_lookup_url = urljoin(
            self.base_url + "/", f"{view.identity}/ajax/lookup"
        )
        view.templates = self.templates
        view_instance = view()

        self._find_decorated_funcs(
            view, view_instance, self._handle_action_decorated_func
        )

        self._find_decorated_funcs(
            view, view_instance, self._handle_expose_decorated_func
        )

        self._views.append(view_instance)
        self._build_menu(view_instance)

    def add_base_view(self, view: type[BaseView]) -> None:
        """Add BaseView to the Admin.

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

        view._admin_ref = self
        view.templates = self.templates
        view_instance = view()

        self._find_decorated_funcs(
            view, view_instance, self._handle_expose_decorated_func
        )
        self._views.append(view_instance)
        self._build_menu(view_instance)

    def _build_menu(self, view: ModelView | BaseView) -> None:
        if view.category:
            menu = CategoryMenu(name=view.category, icon=view.category_icon)
            menu.add_child(ViewMenu(view=view, name=view.name, icon=view.icon))
            self._menu.add(menu)
        else:
            self._menu.add(ViewMenu(view=view, icon=view.icon, name=view.name))


class BaseAdminView(BaseAdmin):
    """
    Manage right to access to an action from a model
    """

    async def _list(self, request: Request) -> None:
        pass

    async def _create(self, request: Request) -> None:
        pass

    async def _details(self, request: Request) -> None:
        pass

    async def _delete(self, request: Request) -> None:
        pass

    async def _edit(self, request: Request) -> None:
        pass

    async def _export(self, request: Request) -> None:
        pass


class Admin(BaseAdminView):
    """Main entrypoint to admin interface.

    ???+ usage
        ```python
        from fastapi import FastAPI
        from sqladmin import Admin, ModelView

        from mymodels import User # SQLAlchemy model


        app = FastAPI()
        admin = Admin(app, engine)


        class UserAdmin(ModelView, model=User):
            column_list = [User.id, User.name]


        admin.add_view(UserAdmin)
        ```
    """

    def __init__(  # type: ignore[no-any-unimported]
        self,
        app: Starlette,
        engine: ENGINE_TYPE | None = None,
        session_maker: SESSION_MAKER | None = None,
        base_url: str = "/admin",
        title: str = "Admin",
        logo_url: str | None = None,
        favicon_url: str | None = None,
        middlewares: Sequence[Middleware] | None = None,
        debug: bool = False,
        templates_dir: str = "templates",
        authentication_backend: AuthenticationBackend | None = None,
    ) -> None:
        """
        Args:
            app: Starlette or FastAPI application.
            engine: SQLAlchemy engine instance.
            session_maker: SQLAlchemy sessionmaker instance.
            base_url: Base URL for Admin interface.
            title: Admin title.
            logo_url: URL of logo to be displayed instead of title.
            favicon_url: URL of favicon to be displayed.
        """

        super().__init__(
            app=app,
            engine=engine,
            session_maker=session_maker,  # type: ignore[arg-type]
            base_url=base_url,
            title=title,
            logo_url=logo_url,
            favicon_url=favicon_url,
            templates_dir=templates_dir,
            middlewares=middlewares,
            authentication_backend=authentication_backend,
        )

        statics = StaticFiles(packages=["sqladmin"])

        async def http_exception(
            request: Request, exc: Exception
        ) -> Response | Awaitable[Response]:
            pass

        routes = [
            Mount("/statics", app=statics, name="statics"),
            Route("/", endpoint=self.index, name="index"),
            Route("/{identity}/list", endpoint=self.list, name="list"),
            Route(
                "/{identity}/details/{pk:path}", endpoint=self.details, name="details"
            ),
            Route(
                "/{identity}/delete",
                endpoint=self.delete,
                name="delete",
                methods=["DELETE"],
            ),
            Route(
                "/{identity}/create",
                endpoint=self.create,
                name="create",
                methods=["GET", "POST"],
            ),
            Route(
                "/{identity}/edit/{pk:path}",
                endpoint=self.edit,
                name="edit",
                methods=["GET", "POST"],
            ),
            Route(
                "/{identity}/export/{export_type}", endpoint=self.export, name="export"
            ),
            Route(
                "/{identity}/ajax/lookup", endpoint=self.ajax_lookup, name="ajax_lookup"
            ),
            Route("/login", endpoint=self.login, name="login", methods=["GET", "POST"]),
            Route("/logout", endpoint=self.logout, name="logout", methods=["GET"]),
        ]

        self.admin.router.routes = routes
        self.admin.exception_handlers = {HTTPException: http_exception}
        self.admin.debug = debug
        self.app.mount(base_url, app=self.admin, name="admin")

    @login_required
    async def index(self, request: Request) -> Response:
        """Index route which can be overridden to create dashboards."""
        pass

    @login_required
    async def list(self, request: Request) -> Response:
        """List route to display paginated Model instances."""
        pass

    @login_required
    async def details(self, request: Request) -> Response:
        """Details route."""
        pass

    @login_required
    async def delete(self, request: Request) -> Response:
        """Delete route."""
        pass

    @login_required
    async def create(self, request: Request) -> Response:
        """Create model endpoint."""
        pass

    @login_required
    async def edit(self, request: Request) -> Response:
        """Edit model endpoint."""
        pass

    @login_required
    async def export(self, request: Request) -> Response:
        """Export model endpoint."""
        pass

    async def login(self, request: Request) -> Response:
        pass

    async def logout(self, request: Request) -> Response:
        pass

    async def ajax_lookup(self, request: Request) -> Response:
        """Ajax lookup route."""
        pass

    @staticmethod
    def get_save_redirect_url(
        request: Request, form: FormData, model_view: ModelView, obj: Any
    ) -> str | URL:
        """
        Get the redirect URL after a save action
        which is triggered from create/edit page.
        """
        pass

    @staticmethod
    async def _handle_form_data(request: Request, obj: Any = None) -> FormData:
        """
        Handle form data and modify in case of UploadFile.
        This is needed since in edit page
        there's no way to show current file of object.
        """
        pass

    @staticmethod
    def _normalize_wtform_data(obj: Any) -> dict:
        pass

    @staticmethod
    def _denormalize_wtform_data(form_data: dict, obj: Any) -> dict:
        pass


def expose(
    path: str,
    *,
    methods: list[str] | None = None,
    identity: str | None = None,
    include_in_schema: bool = True,
) -> Callable[..., Any]:
    """Expose View with information."""

    @no_type_check
    def wrap(func):
        pass

    return wrap


def action(
    name: str,
    label: str | None = None,
    confirmation_message: str | None = None,
    *,
    include_in_schema: bool = True,
    add_in_detail: bool = True,
    add_in_list: bool = True,
) -> Callable[..., Any]:
    """Decorate a [`ModelView`][sqladmin.models.ModelView] function
    with this to:

    * expose it as a custom "action" route
    * add a button to the admin panel to invoke the action

    When invoked from the admin panel, the following query parameter(s) are passed:

    * `pks`: the comma-separated list of selected object PKs - can be empty

    Args:
        name: Unique name for the action - should be alphanumeric, dash and underscore
        label: Human-readable text describing action
        confirmation_message: Message to show before confirming action
        include_in_schema: Indicating if the endpoint be included in the schema
        add_in_detail: Indicating if action should be dispalyed on model detail page
        add_in_list: Indicating if action should be dispalyed on model list page
    """

    @no_type_check
    def wrap(func):
        pass

    return wrap
