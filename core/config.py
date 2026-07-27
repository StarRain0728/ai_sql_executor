import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = os.getenv("SQL_EXECUTOR_ENV", "dev")
ENV_FILE = Path(__file__).parent.parent / "env" / ENV / ".env"
print(f"==========ENV_FILE={ENV_FILE}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "SQL Executor Service"

    log_level: str = "INFO"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 20
    log_encoding: str = "utf-8"
    log_dir: str = Field(..., description="日志目录")

    check_table_permission: bool = Field(description="日志目录", default=True)

    sm2_private_key: str = Field(..., description="sm2私钥")
    sm2_public_key: str = Field(..., description="sm2公钥")

    metadata_db_host: str = Field(..., description="AI门户数据库地址")
    metadata_db_port: int = Field(..., description="AI门户数据库端口")
    metadata_db_name: str = Field(..., description="AI门户数据库名称")
    metadata_db_user: str = Field(..., description="AI门户数据库用户名")
    metadata_db_password: str = Field(..., description="AI门户数据库密码")
    metadata_db_pool_size: int = 10
    metadata_db_max_overflow: int = 20

    sql_query_timeout_seconds: int = 60

    @property
    def metadata_database_url(self) -> str:
        return (f"mysql+pymysql://{quote_plus(self.metadata_db_user)}:{quote_plus(self.metadata_db_password)}"
                f"@{self.metadata_db_host}:{self.metadata_db_port}/{self.metadata_db_name}"
                "?charset=utf8mb4")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
