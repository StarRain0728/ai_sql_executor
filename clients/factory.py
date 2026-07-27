import threading

from clients.base import DatabaseClient
from clients.clickhouse import ClickHouseClient
from clients.mysql import MySQLClient
from core.exceptions import DatasourceTypeNotSupportedError
from models.model import DatasourceType, DatasourceConfig
import logging

logger = logging.getLogger(__name__)


class DatabaseClientFactory:
    _clients: dict[str, DatabaseClient] = {}
    _lock = threading.Lock()

    @classmethod
    def get_client(cls, datasource_config: DatasourceConfig) -> DatabaseClient:
        ds_name = datasource_config.datasource
        with cls._lock:
            if ds_name not in cls._clients:
                if datasource_config.datasource_type == DatasourceType.MYSQL:
                    cls._clients[ds_name] = MySQLClient(datasource_config)
                elif datasource_config.datasource_type == DatasourceType.CLICKHOUSE:
                    cls._clients[ds_name] = ClickHouseClient(datasource_config)
                else:
                    logger.error(msg="不支持的数据源类型:%s", *(datasource_config.datasource))
                    raise DatasourceTypeNotSupportedError(datasource_config.datasource_type)
            return cls._clients[ds_name]

    @classmethod
    def close_all_clients(cls) -> None:
        with cls._lock:
            for client in cls._clients.values():
                client.close()
            cls._clients.clear()
