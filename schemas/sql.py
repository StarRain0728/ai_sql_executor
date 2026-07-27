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


class QueryTestRequest(BaseRequest):
    sql: str


class QueryResponse(BaseResponse):
    sql: str
    data: SqlExecutionResult | None


class TableSamplesRequest(BaseRequest):
    datasource_name: str
    table_info: dict[str, Any]
    n: int
    order_by: Optional[str] = None


class TableSamplesResponse(BaseModel):
    samples: dict[str, list[dict]]
