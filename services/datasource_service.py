from models.model import DatasourceConfig
from repositories.datasource_repository import DatasourceRepository


class DatasourceService:
    def __init__(self, repository: DatasourceRepository):
        self._datasource_repository = repository

    def get_datasource_by_name(self, datasource_name: str) -> DatasourceConfig:
        return self._datasource_repository.get_by_name(datasource_name)
