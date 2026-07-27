from sqlalchemy import select
from sqlalchemy.orm import Session

from repositories.entities import TablePermissionEntity, TableEntity


class TablePermissionRepository:
    def __init__(self, session: Session):
        self._session = session

    def find_unauthorized_tables(self, dept_id: str, user_code: str, table_names: list[str], datasource_id: str) -> list[str]:
        if not table_names:
            return []

        unique_table_names = sorted(set[str](table_names))

        table_id_stmt = select(TableEntity.id, TableEntity.table_name).where(
            TableEntity.datasource_id == datasource_id,
            TableEntity.table_name.in_(unique_table_names)
        )

        table_rows = self._session.execute(table_id_stmt).fetchall()
        table_name_by_id = {table_id: table_name for table_id, table_name in table_rows}

        if not table_name_by_id:
            return unique_table_names

        stmt_user = select(TablePermissionEntity.table_id).where(
            TablePermissionEntity.principal_id == user_code,
            TablePermissionEntity.datasource_id == datasource_id,
            TablePermissionEntity.principal_type == "user",
            TablePermissionEntity.table_id.in_(table_name_by_id.keys())
        )

        stmt_dept = select(TablePermissionEntity.table_id).where(
            TablePermissionEntity.principal_id == dept_id,
            TablePermissionEntity.datasource_id == datasource_id,
            TablePermissionEntity.principal_type == "dept",
            TablePermissionEntity.table_id.in_(table_name_by_id.keys())
        )

        authorized_table_ids_by_user = self._session.scalars(stmt_user).all()
        authorized_table_ids_by_dept = self._session.scalars(stmt_dept).all()
        authorized_table_ids = set(authorized_table_ids_by_user) | set(authorized_table_ids_by_dept)
        authorized_table_names = [table_name_by_id[table_id] for table_id in authorized_table_ids]

        return sorted([name for name in unique_table_names if name not in authorized_table_names])
