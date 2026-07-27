from typing import Any

import clickhouse_connect
from clients.base import DatabaseClient
from models.model import DatasourceConfig

import logging
logger = logging.getLogger(__name__)


class ClickHouseClient(DatabaseClient):
    def __init__(self, datasource_config: DatasourceConfig) -> None:
        super().__init__(datasource_config)
        self._client = clickhouse_connect.get_client(
            host=datasource_config.host,
            port=datasource_config.port,
            user=datasource_config.username,
            password=datasource_config.password,
            database=datasource_config.database,
            secure=False,
            connect_timeout=120,
        )

    def execute(self, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
        result = self._client.query(sql)
        rows: list[dict[str, Any]] = []
        for row in result.result_rows:
            item: dict[str, Any] = {}
            for idx, col in enumerate(result.column_names):
                if idx >= len(row):
                    break
                item[col] = row[idx]
            rows.append(item)
        logger.info(msg="sql 执行结果: %s", *rows)
        return list[Any](result.column_names), rows

    def close(self) -> None:
        self._client.close()
