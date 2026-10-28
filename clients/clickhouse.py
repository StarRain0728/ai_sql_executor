from typing import Any

import clickhouse_connect
from clients.base import DatabaseClient
from models.model import DatasourceConfig

import logging
logger = logging.getLogger(__name__)


class ClickHouseClient(DatabaseClient):
    def __init__(self, datasource_config: DatasourceConfig) -> None:
        super().__init__(datasource_config)
        # 本 client 由工厂按数据源缓存、被 FastAPI 线程池里的多个请求共用（周报多片段并发执行）。
        # clickhouse_connect 默认自动生成 session_id，同一 client 上并发的请求会命中
        # "Attempt to execute concurrent queries within the same session" 而失败。
        # 本服务只跑只读 SELECT，不依赖会话态（临时表/session 级 settings），
        # 关闭自动生成即可让并发请求各走独立的无状态 HTTP 请求。
        self._client = clickhouse_connect.get_client(
            host=datasource_config.host,
            port=datasource_config.port,
            user=datasource_config.username,
            password=datasource_config.password,
            database=datasource_config.database,
            secure=False,
            connect_timeout=120,
            autogenerate_session_id=False,
        )

    def execute(self, sql: str, params: list | None = None) -> tuple[list[str], list[dict[str, Any]]]:
        # clickhouse_connect 原生支持 parameters（? 占位符）：值在驱动层绑定，不拼接文本
        result = self._client.query(sql, parameters=params) if params else self._client.query(sql)
        rows: list[dict[str, Any]] = []
        for row in result.result_rows:
            item: dict[str, Any] = {}
            for idx, col in enumerate(result.column_names):
                if idx >= len(row):
                    break
                item[col] = row[idx]
            rows.append(item)
        logger.info("sql 执行完成，返回 %d 行", len(rows))
        return list[Any](result.column_names), rows

    def close(self) -> None:
        self._client.close()
