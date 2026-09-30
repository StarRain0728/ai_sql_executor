"""引擎 HTTP 接口层单元测试 + 安全用例。

ai-data-query 的 venv 未安装 httpx，无法使用 FastAPI TestClient；
因此直接调用路由函数并注入 Fake Service，聚焦「入参落库/透传」与鉴权语义（安全边界）。
"""
import asyncio
import logging

import pytest
from starlette.responses import Response

from api.middleware import logging_middleware
from api.routes import sql as sql_routes
from core.context import set_user_context
from models.model import SqlExecutionResult
from schemas.base import UserInfo
from schemas.sql import QueryRequest, QueryTestRequest, TableSamplesRequest


class _FakeService:
    """记录路由最终传给 Service 的参数，用于断言「请求 → 引擎」的取值。"""

    def __init__(self):
        self.execute_calls = []
        self.sample_calls = []

    def execute_sql(self, param):
        self.execute_calls.append(param)
        return SqlExecutionResult(sql=param.sql)

    def get_data_samples(self, param):
        self.sample_calls.append(param)
        return {}


@pytest.fixture(autouse=True)
def _clear_context():
    set_user_context(None)
    yield
    set_user_context(None)


class TestWhitelistPermissionCheck:
    def test_empty_user_info_is_denied(self):
        assert sql_routes.permission_check(None, "zhangsan,lisi") is False

    def test_empty_whitelist_is_denied(self):
        user = UserInfo(realName="张三", userName="zhangsan")
        assert sql_routes.permission_check(user, "") is False

    def test_user_in_whitelist_is_allowed(self):
        # 注意：permission_check 用的是 user_info.user_name，而 UserInfo.user_name 的别名是 realName，
        # 因此这里实际比较的是「真实姓名」而非登录账号 userName；白名单需填姓名才命中。
        user = UserInfo(realName="张三", userName="zhangsan")
        assert sql_routes.permission_check(user, "lisi,张三") is True

    def test_user_not_in_whitelist_is_denied(self):
        user = UserInfo(realName="张三", userName="zhangsan")
        assert sql_routes.permission_check(user, "lisi,wangwu") is False

    def test_whitelist_exact_match_no_substring(self):
        """白名单是精确匹配：包含关系（如 zhang / zhangsa）不得放行，避免前缀绕过。"""
        user = UserInfo(realName="张三", userName="zhangsan")
        assert sql_routes.permission_check(user, "zhang") is False
        assert sql_routes.permission_check(user, "zhangsa,张三丰") is False


class TestQueryRoute:
    def test_defaults_are_secure(self):
        service = _FakeService()
        sql_routes.execute_sql(QueryRequest(sql="select 1", datasource_name="ds"), service=service)
        param = service.execute_calls[0]
        assert param.strict_mode is True
        assert param.skip_permission is False
        assert param.max_limit == 50
        assert param.shrink_limit == 10000

    def test_identity_taken_from_request_body(self):
        """安全风险：引擎无鉴权，身份完全取自请求体 user_info，调用方可自报任意用户/部门。"""
        service = _FakeService()
        sql_routes.execute_sql(
            QueryRequest(
                sql="select 1",
                datasource_name="ds",
                user_info={"realName": "张三", "userName": "zhangsan", "deptId": "d1", "deptName": "研发"},
            ),
            service=service,
        )
        param = service.execute_calls[0]
        assert param.user_code == "zhangsan"
        assert param.dept_id == "d1"

    def test_skip_permission_is_client_controllable(self):
        """安全风险：请求体可直接置 skip_permission=true，绕过表级权限校验。"""
        service = _FakeService()
        sql_routes.execute_sql(
            QueryRequest(sql="select 1", datasource_name="ds", skip_permission=True), service=service
        )
        assert service.execute_calls[0].skip_permission is True

    def test_strict_mode_can_be_disabled_by_caller(self):
        """安全风险：请求体可关闭 strict_mode，使多语句/写操作不再被拦截。"""
        service = _FakeService()
        sql_routes.execute_sql(
            QueryRequest(sql="select 1", datasource_name="ds", strict_mode=False), service=service
        )
        assert service.execute_calls[0].strict_mode is False


class TestQueryTestRoute:
    def test_hardcoded_admin_identity_and_relaxed_guards(self):
        """安全风险：/query_test 硬编码 admin 身份、关闭 strict_mode 且放宽限制，等于开放的任意 SQL 入口。"""
        service = _FakeService()
        sql_routes.test_query(QueryTestRequest(sql="drop table t"), service=service)
        param = service.execute_calls[0]
        assert param.sql == "drop table t"
        assert param.user_code == "admin"
        assert param.strict_mode is False
        assert param.max_limit == 10000
        assert param.shrink_limit == 100000
        assert param.datasource_name == "数仓-zysc_rpt"


class TestSamplesRoute:
    def test_samples_param_built_without_type_error(self):
        """回归：路由曾向 GetSamplesParam 传入不存在的 order_by 字段，接口调用即 TypeError。"""
        service = _FakeService()
        response = sql_routes.get_samples(
            TableSamplesRequest(datasource_name="ds", table_info={"t": "id"}, n=5), service=service
        )
        param = service.sample_calls[0]
        assert param.datasource_name == "ds"
        assert param.table_info == {"t": "id"}
        assert param.max_limit == 5
        assert response.samples == {}


class TestLoggingMiddleware:
    def test_headers_values_are_not_logged(self, caplog):
        """安全用例：中间件不得把请求头原文写入日志，否则 Authorization/Cookie 等凭据会泄露。"""

        class _FakeRequest:
            method = "POST"
            url = "http://engine.internal/query"
            headers = {"authorization": "Bearer SUPER-SECRET-TOKEN", "x-user-code": "u1"}

            async def body(self):
                return b'{"sql": "select 1"}'

        async def _call_next(_request):
            return Response(status_code=200)

        with caplog.at_level(logging.INFO, logger="api.middleware"):
            asyncio.run(logging_middleware(_FakeRequest(), _call_next))

        assert "SUPER-SECRET-TOKEN" not in caplog.text
        assert "select 1" in caplog.text
