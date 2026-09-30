"""执行器单元测试：MySQL / ClickHouse 结果装配一致性。"""
import pytest

from executors.clickhouse import ClickHouseExecutor
from executors.mysql import MySQLExecutor


class _FakeClient:
    def __init__(self, columns, rows):
        self._columns = columns
        self._rows = rows

    def execute(self, sql, params=None):
        return self._columns, self._rows


ROWS = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
COLUMNS = ["id", "name"]


class TestMySQLExecutor:
    def test_result_fields(self):
        result = MySQLExecutor(_FakeClient(COLUMNS, ROWS)).execute("select * from t")
        assert result.columns == COLUMNS
        assert result.rows == ROWS
        assert result.row_count == 2
        assert result.sql == "select * from t"


class TestClickHouseExecutor:
    def test_result_fields(self):
        """ClickHouse 执行器必须与 MySQL 一致装配 row_count。

        回归用例：旧实现误用 rowcount=，与 dataclass 字段 row_count 不匹配，
        构造时抛 TypeError，被 execute 包装成 SqlExecutionError，导致所有
        ClickHouse 查询直接失败。
        """
        result = ClickHouseExecutor(_FakeClient(COLUMNS, ROWS)).execute("select * from t")
        assert result.columns == COLUMNS
        assert result.rows == ROWS
        assert result.row_count == 2
        assert result.sql == "select * from t"

    def test_empty_result(self):
        result = ClickHouseExecutor(_FakeClient([], [])).execute("select 1")
        assert result.row_count == 0
