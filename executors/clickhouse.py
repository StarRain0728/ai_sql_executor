from models.model import SqlExecutionResult
from executors.base import SqlExecutor


class ClickHouseExecutor(SqlExecutor):
    def _do_execute(self, sql: str, params: list | None = None) -> SqlExecutionResult:
        # clickhouse_connect 的 client.execute 原生支持 parameters 列表（? 占位符）
        columns, rows = self._client.execute(sql, params)
        return SqlExecutionResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            sql=sql
        )
