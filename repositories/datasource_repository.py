import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.exceptions import DatasourceNotFoundError
from models.model import DatasourceConfig, DatasourceType
from repositories.entities import DatasourceEntity
import logging

from utils.sm2_util import SM2Util

logger = logging.getLogger(__name__)


class DatasourceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_name(self, datasource_name: str) -> DatasourceConfig:
        stmt = select(DatasourceEntity).where(
            DatasourceEntity.datasource_name == datasource_name
        )
        entity = self._session.scalars(stmt).first()
        if not entity:
            logger.error("未找到数据源:%s", datasource_name)
            raise DatasourceNotFoundError(datasource_name)

        option_raw = entity.options_json
        options = {}
        if option_raw:
            options = json.loads(option_raw) if isinstance(option_raw, str) else option_raw

        settings = get_settings()
        password = SM2Util(private_key=settings.sm2_private_key, public_key=settings.sm2_public_key, mode=1).decrypt(entity.datasource_password)
        return DatasourceConfig(
            datasource_name=entity.datasource_name,
            datasource_type=DatasourceType(entity.datasource_type),
            host=entity.datasource_host,
            port=entity.datasource_port,
            username=entity.datasource_user,
            password=password,
            database=entity.datasource_database,
            options=options,
            id=entity.id,
        )
