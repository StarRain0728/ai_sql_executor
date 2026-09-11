from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DatasourceType(str, Enum):
    MYSQL = "mysql"
    CLICKHOUSE = "clickhouse"


@dataclass
class DatasourceConfig:
    datasource_name: str = ""
    datasource_type: DatasourceType = DatasourceType.MYSQL
    host: str = ""
    port: int = 3306
    username: str = ""
    password: str = ""
    database: str = ""
    options: dict = field(default_factory=dict)
    id: str = ""


@dataclass
class SqlExecutionResult:
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    sql: str = ""


@dataclass
class TableInfo:
    name: str = ""
    alias: str = ""
    schema: str = ""
    columns: list = field(default_factory=list)


@dataclass
class ColumnInfo:
    name: str = ""
    alias: str = ""
    table_ref: str = ""


@dataclass
class SqlExecuteParam:
    sql: str = ""
    datasource_name: str = ""
    max_limit: int = 50
    strict_mode: bool = True
    shrink_limit: int = 10000
    user_code: str = ""
    dept_id: str = ""
    skip_permission: bool = False


@dataclass
class GetSamplesParam:
    datasource_name: str = ""
    table_info: dict = field(default_factory=dict)
    max_limit: int = 10


@dataclass
class SqlExecutionLogRecord:
    datasource_id: str = ""
    sql_text: str = ""
    success: str = "0"
    error_msg: str = ""
    sql_api_cos_ms: int = 0
    user_id: str = ""
    result_preview: list = field(default_factory=list)
    ref_tables_columns: list = field(default_factory=list)


@dataclass
class TableRuleInfo:
    id: str = ""
    datasource_id: str = ""
    table_id: str = ""
    rule_name: str = ""
    rule_condition: str = ""
    rule_description: str = ""
    create_user: str = ""
