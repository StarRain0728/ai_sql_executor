"""执行器单元测试：MySQL / ClickHouse 结果装配一致性。"""
from types import SimpleNamespace

import pytest

from clients import clickhouse as clickhouse_module
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


class TestClickHouseClient:
    def test_disable_autogenerate_session_id(self, monkeypatch):
        """回归用例：client 按数据源缓存、被并发请求共用。

        clickhouse_connect 默认自动生成 session_id，同一 client 上并发执行会抛
        "Attempt to execute concurrent queries within the same session"，
        必须显式关闭自动生成。
        """
        captured = {}

        def _fake_get_client(**kwargs):
            captured.update(kwargs)
            return object()

        monkeypatch.setattr(clickhouse_module.clickhouse_connect, "get_client", _fake_get_client)
        config = SimpleNamespace(host="h", port=8123, username="u", password="p", database="db")
        clickhouse_module.ClickHouseClient(config)

        assert captured["autogenerate_session_id"] is False
