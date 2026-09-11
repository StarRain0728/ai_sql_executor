from models.model import SqlExecutionResult
from executors.base import SqlExecutor


class MySQLExecutor(SqlExecutor):
    def _do_execute(self, sql: str) -> SqlExecutionResult:
        columns, rows = self._client.execute(sql)
        return SqlExecutionResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            sql=sql
        )
