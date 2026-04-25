from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import String, cast, inspect, or_, select

from sqladmin.helpers import get_object_identifier, get_primary_keys

if TYPE_CHECKING:
    from sqladmin.models import ModelView


DEFAULT_PAGE_SIZE = 10


class QueryAjaxModelLoader:
    def __init__(
        self,
        name: str,
        model: type,
        model_admin: "ModelView",
        **options: Any,
    ):
        self.name = name
        self.model = model
        self.model_admin = model_admin
        self.fields = options.get("fields", {})
        self.order_by = options.get("order_by")
        self.limit = options.get("limit", DEFAULT_PAGE_SIZE)

        pks = get_primary_keys(self.model)
        self.pk = pks[0] if len(pks) == 1 else None

        if not self.fields:
            raise ValueError(
                "AJAX loading requires `fields` to be specified for "
                f"{self.model}.{self.name}"
            )

        self._cached_fields = self._process_fields()

    def _process_fields(self) -> list:
        pass

    def format(self, model: type) -> dict[str, Any]:
        pass

    async def get_list(self, term: str) -> list[Any]:
        pass


def create_ajax_loader(
    *,
    model_admin: "ModelView",
    name: str,
    options: dict,
) -> QueryAjaxModelLoader:
    pass
