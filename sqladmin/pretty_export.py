from typing import TYPE_CHECKING, Any, AsyncGenerator, List

from starlette.responses import StreamingResponse

from sqladmin.helpers import Writer, secure_filename, stream_to_csv

if TYPE_CHECKING:
    from .models import ModelView


class PrettyExport:
    @staticmethod
    async def _base_export_cell(
        model_view: "ModelView", name: str, value: Any, formatted_value: Any
    ) -> str:
        """
        Default formatting logic for a cell in pretty export.

        Used when `custom_export_cell` returns None.
        Applies standard rules for related fields, booleans, etc.

        Only used when `use_pretty_export = True`.
        """
        pass

    @classmethod
    async def _get_export_row_values(
        cls, model_view: "ModelView", row: Any, column_names: List[str]
    ) -> List[Any]:
        pass

    @classmethod
    async def pretty_export_csv(
        cls, model_view: "ModelView", rows: List[Any]
    ) -> StreamingResponse:
        pass
