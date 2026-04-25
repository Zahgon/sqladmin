from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from starlette.datastructures import URL


@dataclass
class PageControl:
    number: int
    url: str


@dataclass
class Pagination:
    rows: list[Any]
    page: int
    page_size: int
    count: int
    page_controls: list[PageControl] = field(default_factory=list)
    max_page_controls: int = 7

    @property
    def has_previous(self) -> bool:
        pass

    @property
    def has_next(self) -> bool:
        pass

    @property
    def previous_page(self) -> PageControl:
        pass

    @property
    def next_page(self) -> PageControl:
        pass

    def __post_init__(self) -> None:
        # Clamp page
        self.page = min(self.page, max(1, self.count // self.page_size + 1))

    def resize(self, page_size: int) -> Pagination:
        pass

    def add_pagination_urls(self, base_url: URL) -> None:
        # Previous pages
        pass

    def _add_page_control(self, base_url: URL, page: int) -> None:
        pass
