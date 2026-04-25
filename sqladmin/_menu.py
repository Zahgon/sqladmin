from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.datastructures import URL
from starlette.requests import Request

if TYPE_CHECKING:
    from sqladmin.application import BaseView, ModelView


class ItemMenu:
    def __init__(self, name: str, icon: str | None = None) -> None:
        self.name = name
        self.icon = icon
        self.parent: "ItemMenu" | None = None
        self.children: list["ItemMenu"] = []

    def add_child(self, item: "ItemMenu") -> None:
        item.parent = self
        self.children.append(item)

    def is_visible(self, request: Request) -> bool:
        pass

    def is_accessible(self, request: Request) -> bool:
        pass

    def is_active(self, request: Request) -> bool:
        pass

    def url(self, request: Request) -> str | URL:
        pass

    @property
    def display_name(self) -> str:
        pass

    @property
    def type_(self) -> str:
        pass


class CategoryMenu(ItemMenu):
    def is_active(self, request: Request) -> bool:
        pass

    @property
    def type_(self) -> str:
        pass


class ViewMenu(ItemMenu):
    def __init__(
        self,
        view: "BaseView" | "ModelView",
        name: str,
        icon: str | None = None,
    ) -> None:
        super().__init__(name=name, icon=icon)
        self.view = view

    def is_visible(self, request: Request) -> bool:
        pass

    def is_accessible(self, request: Request) -> bool:
        pass

    def is_active(self, request: Request) -> bool:
        pass

    def url(self, request: Request) -> str | URL:
        pass

    @property
    def display_name(self) -> str:
        pass

    @property
    def type_(self) -> str:
        pass


class Menu:
    def __init__(self) -> None:
        self.items: list[ItemMenu] = []

    def add(self, item: ItemMenu) -> None:
        # Only works for one-level menu
        for root in self.items:
            if root.name == item.name:
                root.children.extend(item.children)
                return
        self.items.append(item)
