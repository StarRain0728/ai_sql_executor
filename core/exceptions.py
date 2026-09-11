from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from schemas.base import BaseResponse


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        status_code: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class AppSystemError(AppError):
    code = "SYSTEM_ERROR"
    status_code = "999"

    def __init__(self) -> None:
        super().__init__(
            message=f"SYSTEM_ERROR",
            code=self.code,
            status_code=self.status_code,
            details={},
        )


class SqlExecutionError(AppError):
    code = "SQL_EXECUTION_ERROR"
    status_code = "100"

    def __init__(self, sql: str, reason: str) -> None:
        super().__init__(
            message=f"SQL execution error",
            code=self.code,
            status_code=self.status_code,
            details={"sql": sql, "reason": reason},
        )


class SqlValidationError(AppError):
    code = "SQL_VALIDATION_ERROR"
    status_code = "100"

    def __init__(self, sql: str, reason: str) -> None:
        super().__init__(
            message=f"SQL validation error",
            code=self.code,
            status_code=self.status_code,
            details={"sql": sql, "reason": reason},
        )


class TablePermissionDeniedError(AppError):
    code = "TABLE_PERMISSION_DENIED"
    status_code = "101"

    def __init__(self, table_names: list[str], datasource_id: str, user_code: str, sql: str) -> None:
        table_names_str = ",".join(table_names) if table_names else ""
        super().__init__(
            message=f"{user_code} Table {table_names_str} permission denied",
            code=self.code,
            status_code=self.status_code,
            details={"table_name": table_names_str, "datasource_id": datasource_id, "user_code": user_code, "sql": sql},
        )


class DatasourceTypeNotSupportedError(AppError):
    code = "DATASOURCE_TYPE_NOT_SUPPORTED"
    status_code = "103"

    def __init__(self, datasource_type: str) -> None:
        super().__init__(
            message=f"Datasource type {datasource_type} not supported",
            code=self.code,
            status_code=self.status_code,
            details={"datasource_type": datasource_type},
        )


class DatasourceNotFoundError(AppError):
    code = "DATASOURCE_NOT_FOUND"
    status_code = "104"

    def __init__(self, datasource_name: str) -> None:
        super().__init__(
            message=f"Datasource {datasource_name} not found",
            code=self.code,
            status_code=self.status_code,
            details={"datasource_name": datasource_name},
        )


def register_exceptions_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=BaseResponse(
                error_code=exc.status_code,
                error_message=exc.message,
                success=0,
                data=None,
                error_detail={
                    "code": exc.code,
                    "details": exc.details,
                },
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_other_error(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=BaseResponse(
                error_code="999",
                error_message="SYSTEM_ERROR",
                success=0,
                data=None,
                error_detail={},
            ).model_dump(),
        )
