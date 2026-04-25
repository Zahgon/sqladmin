from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.expression import Select, and_, or_
from starlette.requests import Request

from sqladmin._types import MODEL_PROPERTY
from sqladmin.helpers import (
    get_column_python_type,
    get_direction,
    get_primary_keys,
    is_falsy_value,
    object_identifier_values,
)

if TYPE_CHECKING:
    from sqladmin.models import ModelView


class Query:
    def __init__(self, model_view: "ModelView") -> None:
        self.model_view = model_view

    def _get_to_many_stmt(self, relation: MODEL_PROPERTY, values: list[Any]) -> Select:
        pass

    def _get_to_one_stmt(self, relation: MODEL_PROPERTY, value: Any) -> Select:
        pass

    def _set_many_to_one(self, obj: Any, relation: MODEL_PROPERTY, ident: Any) -> Any:
        pass

    def _set_attributes_sync(self, session: Session, obj: Any, data: dict) -> Any:
        pass

    async def _set_attributes_async(
        self, session: AsyncSession, obj: Any, data: dict
    ) -> Any:
        pass

    def _update_sync(self, pk: Any, data: dict[str, Any], request: Request) -> Any:
        pass

    async def _update_async(
        self, pk: Any, data: dict[str, Any], request: Request
    ) -> Any:
        pass

    def _get_delete_stmt(self, pk: str) -> Select:
        pass

    def _delete_sync(self, pk: str, request: Request) -> None:
        pass

    async def _delete_async(self, pk: str, request: Request) -> None:
        pass

    def _get_model_object(self, data: dict[str, Any]) -> Any:
        pass

    def _insert_sync(self, data: dict[str, Any], request: Request) -> Any:
        pass

    async def _insert_async(self, data: dict[str, Any], request: Request) -> Any:
        pass

    async def delete(self, obj: Any, request: Request) -> None:
        pass

    async def insert(self, data: dict, request: Request) -> Any:
        pass

    async def update(self, pk: Any, data: dict, request: Request) -> Any:
        pass
