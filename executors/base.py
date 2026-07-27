from abc import ABC, abstractmethod

import sqlglot
from sqlglot import exp

from clients.base import DatabaseClient
from core.exceptions import SqlExecutionError
from models.model import SqlExecutionResult
import logging

logger = logging.getLogger(__name__)


class SqlExecutor(ABC):
    def __init__(self, client: DatabaseClient) -> None:
        self._client = client

    @property
    def dialect(self) -> str:
        return self._client.datasource_config.datasource_type

    def execute(self, sql: str) -> SqlExecutionResult:
        try:
            return self._do_execute(sql)
        except Exception as e:
            logger.error("sql %s 执行失败: %s", sql, e)
            raise SqlExecutionError(sql, str(e))

    @abstractmethod
    def _do_execute(self, sql: str) -> SqlExecutionResult:
        """run sql"""


if __name__ == '__main__':

    ast = sqlglot.parse_one("select sum(u.cc), up.aaa as c from user u left join up on up.id = u.id  where aaa = (select * from ppp where id = 1) and  ccc >1 ", dialect="clickhouse")
    # ast = sqlglot.parse_one("select * from user where aaa = 1", dialect="clickhouse")
    # ast = sqlglot.parse_one("select * from user where aaa = 1", dialect="clickhouse")
    tables = []
    columns = []
    for node in ast.find_all(exp.Table):
        if isinstance(node, exp.Table):
            table_info = TableInfo(
                name=node.name,
                alias=node.alias if hasattr(node, 'alias') and node.alias else "",
                schema=node.db if hasattr(node, 'db') and node.db else ""
            )
            if table_info not in tables:
                tables.append(table_info)
    for node in ast.walk():
        if isinstance(node, exp.Column):
            col_info = ColumnInfo(
                name=node.name,
                alias=node.alias if hasattr(node, 'alias') and node.alias else "",
                table_ref=node.table if hasattr(node, 'table') and node.table else ""
            )
            if col_info not in columns:
                columns.append(col_info)

    print(tables)
    print(columns)
