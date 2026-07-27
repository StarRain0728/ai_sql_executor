import uuid
from typing import Any

from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class DatasourceEntity(Base):
    __tablename__ = "datasource_config"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    datasource_name: Mapped[str] = mapped_column(String(128))
    datasource_host: Mapped[str] = mapped_column(String(128))
    datasource_port: Mapped[int] = mapped_column(String(20))
    datasource_user: Mapped[str] = mapped_column(String(128))
    datasource_password: Mapped[str] = mapped_column(String(255))
    datasource_database: Mapped[str] = mapped_column(String(255))
    datasource_type: Mapped[str] = mapped_column(String(128))
    datasource_description: Mapped[str] = mapped_column(String(255))
    options_json: Mapped[str] = mapped_column(Text)
    is_enabled: Mapped[str] = mapped_column(String(1))
    create_time: Mapped[str] = mapped_column(DateTime)
    create_user: Mapped[str] = mapped_column(String(128))
    update_time: Mapped[str] = mapped_column(DateTime)
    update_user: Mapped[str] = mapped_column(String(128))


class SqlExecLogEntity(Base):
    __tablename__ = "sql_exec_log"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=lambda: uuid.uuid4())
    datasource_id: Mapped[str] = mapped_column(String(128))
    sql_text: Mapped[str] = mapped_column(Text)
    is_success: Mapped[str] = mapped_column(String(1))
    error_msg: Mapped[str] = mapped_column(String(255))
    sql_api_cost_ms: Mapped[int] = mapped_column(Integer)
    ref_tables_columns: Mapped[str] = mapped_column(Text)
    user_code: Mapped[str] = mapped_column(String(128))
    result_preview: Mapped[str] = mapped_column(Text)
    create_time: Mapped[Any] = mapped_column(DateTime, default=func.now())


class TablePermissionEntity(Base):
    __tablename__ = "table_permission"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    datasource_id: Mapped[str] = mapped_column(String(128))
    table_id: Mapped[str] = mapped_column(String(128))
    principal_id: Mapped[str] = mapped_column(String(128))
    principal_type: Mapped[str] = mapped_column(String(128))
    create_user: Mapped[str] = mapped_column(String(128))
    create_time: Mapped[Any] = mapped_column(DateTime, server_default=func.now())


class TableEntity(Base):
    __tablename__ = "table_config"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    datasource_id: Mapped[str] = mapped_column(String(128))
    table_name: Mapped[str] = mapped_column(Text)
    table_description: Mapped[str] = mapped_column(String(128))
    create_user: Mapped[str] = mapped_column(String(128))
    create_time: Mapped[Any] = mapped_column(DateTime)
    update_time: Mapped[str] = mapped_column(DateTime)
    update_user: Mapped[str] = mapped_column(String(128))


class TableFilterRuleEntity(Base):
    __tablename__ = "table_filter_rule"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    datasource_id: Mapped[str] = mapped_column(String(128))
    table_id: Mapped[str] = mapped_column(String(128))
    rule_name: Mapped[str] = mapped_column(String(255))
    rule_condition: Mapped[str] = mapped_column(Text)
    rule_description: Mapped[str] = mapped_column(String(255))
    create_user: Mapped[str] = mapped_column(String(128))
    create_time: Mapped[Any] = mapped_column(DateTime)
    update_user: Mapped[str] = mapped_column(String(128))
    update_time: Mapped[str] = mapped_column(DateTime)
