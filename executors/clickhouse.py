from models.model import SqlExecutionResult
from executors.base import SqlExecutor


class ClickHouseExecutor(SqlExecutor):
    def _do_execute(self, sql: str) -> SqlExecutionResult:
        columns, rows = self._client.execute(sql)
        return SqlExecutionResult(
            columns=columns,
            rows=rows,
            rowcount=len(rows),
            sql=sql
        )
