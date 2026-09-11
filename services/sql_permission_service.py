import json

from core.config import get_settings
from core.exceptions import TablePermissionDeniedError
from models.model import TableInfo
from repositories.table_permission_repository import TablePermissionRepository


class SqlPermissionService:
    def __init__(self, repository: TablePermissionRepository):
        self._permission_repository = repository

    def permission_check(self, dept_id: str, user_code: str, datasource_id: str, sql: str,
                         ref_table_columns: list[TableInfo], skip_permission: bool = False) -> None:
        settings = get_settings()
        if skip_permission:
            return
        if not settings.check_table_permission:
            return
        table_names = self._extract_table_names(ref_table_columns)
        if not table_names:
            return

        missing_tables = self._permission_repository.find_unauthorized_tables(
            dept_id=dept_id,
            datasource_id=datasource_id,
            user_code=user_code,
            table_names=table_names,
        )
        if missing_tables:
            raise TablePermissionDeniedError(
                sql=sql,
                table_names=missing_tables,
                datasource_id=datasource_id,
                user_code=user_code,
            )

    @staticmethod
    def _extract_table_names(ref_table_columns: list[TableInfo]) -> list[str]:
        table_names: list[str] = []
        for item in ref_table_columns:
            if item.name:
                table_names.append(item.name)
        return table_names
