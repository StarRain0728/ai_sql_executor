from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import create_engine, Engine, text

from clients.base import DatabaseClient
from models.model import DatasourceConfig


class MySQLClient(DatabaseClient):
    def __init__(self, datasource_config: DatasourceConfig) -> None:
        super().__init__(datasource_config)

        connect_args = {
            key: value
            for key, value in datasource_config.options.items()
            if key in ("pool_size", "max_overflow")
        }

        self.engine: Engine = create_engine(
            f"mysql+pymysql://{quote_plus(datasource_config.username)}:{quote_plus(datasource_config.password)}"
            f"@{datasource_config.host}:{datasource_config.port}/{datasource_config.database}"
            f"?charset=utf8mb4",
            pool_pre_ping=True,
            pool_size=int(datasource_config.options.get("pool_size", 5)),
            max_overflow=int(datasource_config.options.get("max_overflow", 10)),
            connect_args=connect_args,
            future=True
        )

    def execute(self, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
        with self.engine.connect() as connection:
            result = connection.execute(text(sql))
            connection.commit()
            if result.returns_rows:
                columns = list[str](result.keys())
                rows = [dict[Any, Any](row) for row in result.mappings().all()]
                return columns, rows
            return [], []

    def close(self) -> None:
        self.engine.dispose()
