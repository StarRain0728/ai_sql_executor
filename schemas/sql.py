import json
from typing import Optional, Any

from pydantic import BaseModel, Field

from models.model import SqlExecutionResult
from schemas.base import BaseResponse, BaseRequest


class QueryRequest(BaseRequest):
    sql: str
    max_limit: Optional[int] = 50
    datasource_name: str
    strict_mode: Optional[bool] = True
    shrink_limit: Optional[int] = 10000
    # 系统旁路：元数据管理采集 information_schema 时跳过表级权限校验，默认关闭
    skip_permission: Optional[bool] = False


class QueryTestRequest(BaseRequest):
    sql: str


class QueryResponse(BaseResponse):
    sql: str
    data: Optional[SqlExecutionResult] = None


class TableSamplesRequest(BaseRequest):
    datasource_name: str
    table_info: dict[str, Any]
    n: int
    order_by: Optional[str] = None


class TableSamplesResponse(BaseModel):
    samples: dict[str, list[dict]]
