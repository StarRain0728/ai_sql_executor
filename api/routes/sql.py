from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import get_sql_execution_service
from core.context import get_user_code, get_user_dept, UserContext, set_user_context
from models.model import SqlExecuteParam, GetSamplesParam
from schemas.base import BaseRequest, UserInfo
from schemas.sql import QueryResponse, QueryRequest, TableSamplesResponse, TableSamplesRequest, QueryTestRequest
import logging

sql_router = APIRouter()
logger = logging.getLogger(__name__)


def permission_check(user_info: UserInfo, white_list: str) -> bool:
    logger.info("白名单校验: 白名单: %s, 用户信息: %s", white_list, user_info)
    if not user_info or not white_list:
        return False
    user_name = user_info.user_name
    white_list = white_list.split(",")
    if user_name and user_name in white_list:
        return True
    return False


def _save_user_context(query_param: BaseRequest):
    if query_param.user_info:
        set_user_context(UserContext(user_code=query_param.user_info.user_code,
                                     user_dept_id=query_param.user_info.dept_id,
                                     user_dept_name=query_param.user_info.dept_name,
                                     user_name=query_param.user_info.user_name,
                                     ))


@sql_router.post(path="/query", response_model=QueryResponse)
def execute_sql(query_param: QueryRequest, service=Depends(get_sql_execution_service)) -> QueryResponse:

    logger.info("待执行SQL: %s", query_param.sql)
    logger.info("数据源: %s", query_param.datasource_name)
    _save_user_context(query_param)
    data = service.execute_sql(
        SqlExecuteParam(
            sql=query_param.sql,
            user_code=get_user_code(),
            dept_id=get_user_dept(),
            strict_mode=query_param.strict_mode,
            max_limit=query_param.max_limit,
            shrink_limit=query_param.shrink_limit,
            datasource_name=query_param.datasource_name,
            skip_permission=bool(query_param.skip_permission)
        )
    )
    return QueryResponse(
        data=data,
        error_message="",
        error_code="",
        success=1,
        sql=data.sql
    )


@sql_router.post(path="/tables/samples", response_model=TableSamplesResponse)
def get_samples(query_param: TableSamplesRequest, service=Depends(get_sql_execution_service)) -> TableSamplesResponse:
    logger.info("待获取示例数据表: %s", query_param.table_info)
    logger.info("数据源: %s", query_param.datasource_name)
    _save_user_context(query_param)
    return TableSamplesResponse(samples=service.get_data_samples(GetSamplesParam(
        table_info=query_param.table_info,
        datasource_name=query_param.datasource_name,
        order_by=query_param.order_by,
        max_limit=query_param.n
    )))


@sql_router.post(path="/query_test", response_model=QueryResponse)
def test_query(query_param: QueryTestRequest, service=Depends(get_sql_execution_service)) -> QueryResponse:
    logger.info("待执行SQL: %s", query_param.sql)
    _save_user_context(query_param)

    data = service.execute_sql(
        SqlExecuteParam(
            sql=query_param.sql,
            user_code="admin",
            dept_id="",
            strict_mode=False,
            max_limit=10000,
            shrink_limit=100000,
            datasource_name="数仓-zysc_rpt"
        )
    )
    return QueryResponse(
        data=data,
        error_message="",
        error_code="",
        success=1,
        sql=data.sql
    )
