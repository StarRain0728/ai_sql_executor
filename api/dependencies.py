from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database import get_metadata_session
from services.sql_execution_service import SqlExecutionService


def get_sql_execution_service(
    session: Session = Depends(get_metadata_session),
) -> Generator[SqlExecutionService, None, None]:
    yield SqlExecutionService(session=session)
