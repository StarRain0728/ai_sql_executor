"""SqlExecutionService 编排层单元测试（引擎主入口）。

execute_sql 串起「取数据源 → 解析/行级规则改写/limit → 权限校验 → 执行 → 落审计日志」，
是安全边界最集中的地方。这里用替身隔离 DB 与真实执行器，聚焦安全关键接线：

  - strict_mode 是否真正生效（多语句被拦下且不触达执行器）；
  - 行级过滤规则是否进入最终 SQL、规则是否按解析出的数据源加载；
  - 权限校验入参（user_code/dept_id/datasource_id/skip_permission）是否正确透传；
  - 失败路径「异常也必须落审计日志」「日志落库失败不阻断主流程」。
"""
from __future__ import annotations

import pytest

from core.exceptions import (
    AppSystemError,
    DatasourceNotFoundError,
    SqlValidationError,
    TablePermissionDeniedError,
)
from models.model import (
    DatasourceConfig,
    DatasourceType,
    GetSamplesParam,
    SqlExecuteParam,
    SqlExecutionResult,
)
from services import sql_execution_service as svc_module
from services.sql_execution_service import SqlExecutionService
from services.sql_parser import SqlParser


class _FakeSession:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class _FakeDatasourceService:
    def __init__(self, config):
        self._config = config

    def get_datasource_by_name(self, name):
        if self._config is None:
            raise DatasourceNotFoundError(name)
        return self._config


class _FakeRuleService:
    def __init__(self, rules):
        self.rules = rules
        self.datasource_ids = []

    def build_rules_by_datasource_id(self, datasource_id):
        self.datasource_ids.append(datasource_id)
        return self.rules


class _FakePermissionService:
    def __init__(self, denied):
        self.calls = []
        self.denied = denied

    def permission_check(self, **kwargs):
        self.calls.append(kwargs)
        if self.denied:
            raise self.denied


class _FakeExecutor:
    def __init__(self, result, error):
        self.result = result
        self.error = error
        self.sqls = []

    def execute(self, sql, params=None):
        self.sqls.append(sql)
        if self.error:
            raise self.error
        return self.result


class _FakeExecutorFactory:
    def __init__(self, executor):
        self.executor = executor

    def create(self, datasource_type, client):
        return self.executor


class _FakeLogRepository:
    def __init__(self, error):
        self.records = []
        self.error = error

    def create(self, record):
        if self.error:
            raise self.error
        self.records.append(record)


def _build(*, rules=None, execution_result=None, executor_error=None, permission_denied=None,
           log_error=None, datasource_missing=False, datasource_id="ds-1",
           datasource_type=DatasourceType.MYSQL, datasource_name="ds"):
    """装配一个所有外部依赖均为替身的 SqlExecutionService。"""
    config = None if datasource_missing else DatasourceConfig(
        datasource_name=datasource_name, datasource_type=datasource_type, id=datasource_id
    )
    session = _FakeSession()
    service = SqlExecutionService(session)
    service._datasource_service = _FakeDatasourceService(config)
    service._table_rule_service = _FakeRuleService(rules or {})
    service._sql_permission_service = _FakePermissionService(permission_denied)
    executor = _FakeExecutor(execution_result if execution_result is not None else SqlExecutionResult(),
                             executor_error)
    service._executor_factory = _FakeExecutorFactory(executor)
    service._log_repository = _FakeLogRepository(log_error)
    service._session = session
    return service, executor, session


@pytest.fixture(autouse=True)
def _stub_db_client(monkeypatch):
    """DatabaseClientFactory 会真实建连，统一替换为无副作用替身。"""
    monkeypatch.setattr(svc_module.DatabaseClientFactory, "get_client", lambda _config: object())


class TestExecuteSqlHappyPath:
    def test_wires_parser_permission_executor_and_audit_log(self):
        service, executor, _ = _build(
            rules={"orders": ["dept_id = 'd1'"]},
            execution_result=SqlExecutionResult(rows=[{"a": 1}], row_count=1),
        )
        result = service.execute_sql(SqlExecuteParam(
            sql="select * from orders", datasource_name="ds", user_code="u1", dept_id="d1", max_limit=10,
        ))

        assert result.row_count == 1
        # 行级过滤规则必须进入真正执行的 SQL，且带上 limit
        executed_sql = executor.sqls[0]
        assert "dept_id" in executed_sql
        assert "limit 10" in executed_sql.lower()
        # 权限校验入参透传
        call = service._sql_permission_service.calls[0]
        assert call["user_code"] == "u1"
        assert call["dept_id"] == "d1"
        assert call["datasource_id"] == "ds-1"
        assert call["skip_permission"] is False
        # 审计日志：成功
        log = service._log_repository.records[0]
        assert log.success == "1"
        assert log.datasource_id == "ds-1"
        assert log.user_id == "u1"
        assert log.sql_api_cos_ms >= 0

    def test_table_rules_are_loaded_by_resolved_datasource_id(self):
        """规则必须按服务端解析出的数据源加载，避免用请求里的名字去查别人的规则。"""
        service, _, _ = _build(execution_result=SqlExecutionResult(), datasource_id="ds-9")
        service.execute_sql(SqlExecuteParam(sql="select * from orders", datasource_name="ds"))
        assert service._table_rule_service.datasource_ids == ["ds-9"]


class TestExecuteSqlSecurityBoundary:
    def test_strict_mode_blocks_multi_statement_before_execution(self):
        service, executor, _ = _build(execution_result=SqlExecutionResult())

        with pytest.raises(SqlValidationError):
            service.execute_sql(SqlExecuteParam(
                sql="select * from orders; drop table orders", datasource_name="ds", strict_mode=True,
            ))

        assert executor.sqls == []
        log = service._log_repository.records[0]
        assert log.success == "0"
        assert log.error_msg

    def test_skip_permission_is_passed_through_to_permission_service(self):
        service, _, _ = _build(execution_result=SqlExecutionResult())
        service.execute_sql(SqlExecuteParam(
            sql="select * from orders", datasource_name="ds", skip_permission=True,
        ))
        assert service._sql_permission_service.calls[0]["skip_permission"] is True

    def test_permission_denied_is_raised_and_never_executed(self):
        denied = TablePermissionDeniedError(
            table_names=["orders"], datasource_id="ds-1", user_code="u1", sql="select * from orders",
        )
        service, executor, _ = _build(permission_denied=denied, execution_result=SqlExecutionResult())

        with pytest.raises(TablePermissionDeniedError):
            service.execute_sql(SqlExecuteParam(
                sql="select * from orders", datasource_name="ds", user_code="u1",
            ))

        assert executor.sqls == []
        assert service._log_repository.records[0].success == "0"


class TestExecuteSqlFailurePaths:
    def test_unexpected_error_is_wrapped_as_system_error_and_audited(self):
        service, _, _ = _build(executor_error=RuntimeError("boom"))

        with pytest.raises(AppSystemError):
            service.execute_sql(SqlExecuteParam(sql="select * from orders", datasource_name="ds"))

        log = service._log_repository.records[0]
        assert log.success == "0"
        assert "boom" in log.error_msg

    def test_datasource_lookup_failure_is_audited_with_empty_datasource_id(self):
        service, _, _ = _build(datasource_missing=True)

        with pytest.raises(DatasourceNotFoundError):
            service.execute_sql(SqlExecuteParam(sql="select 1", datasource_name="nope"))

        log = service._log_repository.records[0]
        assert log.success == "0"
        assert log.datasource_id == ""

    def test_audit_log_failure_does_not_break_execution(self):
        """审计日志写库失败只回滚日志事务，不能把已成功的查询结果吞掉。"""
        service, _, session = _build(
            execution_result=SqlExecutionResult(rows=[{"a": 1}]), log_error=RuntimeError("db down"),
        )

        result = service.execute_sql(SqlExecuteParam(sql="select * from orders", datasource_name="ds"))

        assert result is not None
        assert len(result.rows) == 1
        assert session.rollbacks == 1


class TestGetDataSamples:
    def test_builds_limited_select_per_table(self):
        service, executor, _ = _build(execution_result=SqlExecutionResult(rows=[{"id": 1}]))
        samples = service.get_data_samples(GetSamplesParam(
            datasource_name="ds", table_info={"orders": "id"}, max_limit=5,
        ))

        assert samples == {"orders": [{"id": 1}]}
        assert "limit 5" in executor.sqls[0].lower()

    @pytest.mark.parametrize("bad_table_name", [
        "orders where 1=1",              # 追加条件绕过
        "(select * from secret) x",      # 子查询冒充表名
        "orders; drop table orders",     # 多语句
        "orders, other_table",           # 多表注入
    ])
    def test_rejects_injected_table_name(self, bad_table_name):
        service, executor, _ = _build(execution_result=SqlExecutionResult())

        with pytest.raises(SqlValidationError):
            service.get_data_samples(GetSamplesParam(datasource_name="ds", table_info={bad_table_name: None}))

        assert executor.sqls == []

    def test_per_table_failure_is_isolated(self):
        service, _, _ = _build(executor_error=RuntimeError("exec fail"))
        samples = service.get_data_samples(GetSamplesParam(datasource_name="ds", table_info={"orders": None}))
        assert samples == {"orders": []}


class TestShrinkRows:
    def test_truncates_rows_and_keeps_row_count_consistent(self):
        parser = SqlParser("select 1", "mysql")
        result = SqlExecutionResult(rows=[{"v": "x" * 50} for _ in range(10)])

        SqlExecutionService._shrink_rows(parser, result, shrink_limit=120)

        assert 0 < len(result.rows) < 10
        assert result.row_count == len(result.rows)

    def test_first_row_exceeding_limit_yields_empty_result(self):
        parser = SqlParser("select 1", "mysql")
        result = SqlExecutionResult(rows=[{"v": "x" * 200}])

        SqlExecutionService._shrink_rows(parser, result, shrink_limit=50)

        assert result.rows == []
        assert result.row_count == 0
