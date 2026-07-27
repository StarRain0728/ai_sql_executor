from core.exceptions import DatasourceTypeNotSupportedError
from models.model import DatasourceType
from executors.base import SqlExecutor
from executors.clickhouse import ClickHouseExecutor
from executors.mysql import MySQLExecutor


class SqlExecutorFactory:
    def __init__(self):
        self._registry: dict[DatasourceType, type[SqlExecutor]] = {}
        self.registry(DatasourceType.MYSQL, MySQLExecutor)
        self.registry(DatasourceType.CLICKHOUSE, ClickHouseExecutor)

    def registry(self, datasource_type: DatasourceType, executor_class: type[SqlExecutor]) -> None:
        self._registry[datasource_type] = executor_class

    def create(self, datasource_type: DatasourceType, client) -> SqlExecutor:
        executor_class = self._registry.get(datasource_type)
        if executor_class is None:
            raise DatasourceTypeNotSupportedError(f"Unsupported datasource type: {datasource_type}")
        return executor_class(client=client)
