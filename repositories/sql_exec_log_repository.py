import json

from sqlalchemy.orm import Session

from models.model import SqlExecutionLogRecord
from repositories.entities import SqlExecLogEntity
from utils.json_util import to_json_default


class SqlExecutionLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: SqlExecutionLogRecord) -> None:
        entity = SqlExecLogEntity(
            datasource_id=record.datasource_id,
            sql_text=record.sql_text,
            is_success=record.success,
            error_msg=record.error_msg,
            sql_api_cost_ms=record.sql_api_cost_ms,
            ref_tables_columns=json.dumps(record.ref_tables_columns, ensure_ascii=False, default=to_json_default),
            user_code=record.user_id,
            result_preview=json.dumps(record.result_preview, ensure_ascii=False, default=to_json_default)
        )
        self._session.add(entity)
        self._session.commit()
