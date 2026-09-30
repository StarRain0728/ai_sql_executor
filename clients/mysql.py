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

    def execute(self, sql: str, params: list | None = None) -> tuple[list[str], list[dict[str, Any]]]:
        """执行 SQL；params 非空时按 ? 占位符顺序做参数绑定（值永不进 SQL 文本）。

        实现方式：? 依序替换为 SQLAlchemy text() 命名参数 :p0/:p1...，绑定执行。
        """
        with self.engine.connect() as connection:
            bind_params: dict[str, Any] = {}
            bound_sql = sql
            if params:
                def _to_named(sql_text: str) -> str:
                    out, idx = [], 0
                    for ch in sql_text:
                        if ch == "?":
                            out.append(f":p{idx}")
                            idx += 1
                        else:
                            out.append(ch)
                    return "".join(out)

                bound_sql = _to_named(sql)
                bind_params = {f"p{i}": v for i, v in enumerate(params)}
            result = connection.execute(text(bound_sql), bind_params)
            connection.commit()
            if result.returns_rows:
                columns = list[str](result.keys())
                rows = [dict[Any, Any](row) for row in result.mappings().all()]
                return columns, rows
            return [], []

    def close(self) -> None:
        self.engine.dispose()
