import time
from typing import Optional
from sqlalchemy.orm import Session

import sqlglot
from clients.factory import DatabaseClientFactory
from core.exceptions import AppError, AppSystemError, SqlValidationError
from models.model import SqlExecutionResult, DatasourceConfig, SqlExecutionLogRecord, TableInfo, GetSamplesParam, \
    SqlExecuteParam
from executors.factory import SqlExecutorFactory
from repositories.datasource_repository import DatasourceRepository
from repositories.sql_exec_log_repository import SqlExecutionLogRepository
from repositories.table_filter_rule_repository import TableFilterRuleRepository
from repositories.table_permission_repository import TablePermissionRepository
from services.datasource_service import DatasourceService
from sqlglot import expressions as exp
from services.sql_parser import SqlParser
from services.sql_permission_service import SqlPermissionService
import logging

from services.table_rule_service import TableRuleService

logger = logging.getLogger(__name__)


class SqlExecutionService:
    def __init__(self, session: Session) -> None:
        self._datasource_service = DatasourceService(DatasourceRepository(session=session))
        self._sql_permission_service = SqlPermissionService(TablePermissionRepository(session=session))

        self._table_rule_service = TableRuleService(TableFilterRuleRepository(session=session))
        self._log_repository = SqlExecutionLogRepository(session=session)
        self._executor_factory = SqlExecutorFactory()
        self._session = session

    def execute_sql(self, sql_execute_param: SqlExecuteParam) -> SqlExecutionResult:
        success = False
        error_message: Optional[str] = ""
        result: Optional[SqlExecutionResult] = None
        datasource_config: Optional[DatasourceConfig] = None
        start_time = time.perf_counter()
        tables_columns: list[TableInfo] = []
        sql = sql_execute_param.sql
        try:
            # 获取数据源配置
            datasource_config: DatasourceConfig = self._datasource_service.get_datasource_by_name(
                sql_execute_param.datasource_name)
            # 获取client
            client = DatabaseClientFactory.get_client(datasource_config)
            # 获取所有表规则
            table_rules = self._table_rule_service.build_rules_by_datasource_id(datasource_id=datasource_config.id)
            # 初始化parser
            parser = SqlParser(sql_execute_param.sql, datasource_config.datasource_type)
            # 校验().增加表筛选规则().增加limit().解析表和字段
            parser.parse(strict_mode=sql_execute_param.strict_mode).rewrite(table_rules).add_limit(
                max_limit=sql_execute_param.max_limit).parse_lineage()
            # 获取最终sql
            sql = parser.sql
            # 获取解析的表和字段
            tables_columns = parser.ref_table_columns

            # 权限校验
            self._sql_permission_service.permission_check(sql=sql, user_code=sql_execute_param.user_code,
                                                          dept_id=sql_execute_param.dept_id,
                                                          datasource_id=datasource_config.id,
                                                          ref_table_columns=tables_columns,
                                                          skip_permission=sql_execute_param.skip_permission)

            # 获取执行器
            executor = self._executor_factory.create(datasource_config.datasource_type, client)
            # 执行结果（params 非空时按 ? 占位符参数绑定：审核/行级规则改写作用于占位符版 SQL，
            # 真实值只在驱动层绑定，杜绝拼接注入）
            result: SqlExecutionResult = executor.execute(sql, sql_execute_param.params or None)
            # 缩小返回结果
            self._shrink_rows(parser, result, shrink_limit=sql_execute_param.shrink_limit)
            # 执行完成
            success = True

        except AppError as app_error:
            error_message = str(app_error.message)
            raise app_error
        except Exception as exc:
            logger.error("执行sql系统异常: %s", exc)
            error_message = str(exc)
            raise AppSystemError() from exc
        finally:
            self._persist_exec_log(
                datasource_id=datasource_config.id if datasource_config else "",
                sql=sql,
                result_preview=result.rows[:5] if result else [],
                success="1" if success else "0",
                error_msg=error_message[:200] if error_message else "",
                tables_columns=tables_columns,
                sql_api_cos_ms=int((time.perf_counter() - start_time) * 1000),
                user_id=sql_execute_param.user_code,
            )
        return result

    def get_data_samples(self, get_samples_param: GetSamplesParam) -> dict[str, list[dict]]:
        datasource_config = self._datasource_service.get_datasource_by_name(get_samples_param.datasource_name)
        client = DatabaseClientFactory.get_client(datasource_config)
        executor = self._executor_factory.create(datasource_config.datasource_type, client)
        samples = {}
        for table_name, order_by in get_samples_param.table_info.items():
            # 表名必须是纯表标识符：into=exp.Table 可拦截 `(select * from 敏感表) x`、`t where 1=1` 等注入片段
            try:
                table_expr = sqlglot.parse_one(table_name, read=datasource_config.datasource_type, into=exp.Table)
            except Exception as exc:
                raise SqlValidationError(sql=table_name, reason=f"非法的表名: {table_name}") from exc
            query_node = exp.Select().select("*").from_(table_expr)
            query_node = query_node.order_by(exp.Ordered(this=exp.column(order_by))) if order_by else query_node
            query_node = query_node.limit(get_samples_param.max_limit)
            sql = query_node.sql(dialect=datasource_config.datasource_type)
            try:
                result = executor.execute(sql)
                samples[table_name] = result.rows
            except Exception as exc:
                logger.error(f"获取{table_name}数据示例，系统异常:{exc}")
                samples[table_name] = []
        return samples

    def _persist_exec_log(self, datasource_id: str,
                          sql: str,
                          result_preview: list[dict],
                          error_msg: Optional[str],
                          success: str,
                          user_id: str,
                          tables_columns: list[TableInfo],
                          sql_api_cos_ms: int):
        record = SqlExecutionLogRecord(
            datasource_id=datasource_id,
            sql_text=sql,
            success=success,
            error_msg=error_msg,
            sql_api_cos_ms=sql_api_cos_ms,
            user_id=user_id,
            result_preview=result_preview,
            ref_tables_columns=tables_columns,
        )

        try:
            self._log_repository.create(record)
        except Exception as exc:
            logger.error(f"Failed to persist execution log: {exc}")
            self._session.rollback()

    @staticmethod
    def _shrink_rows(parser, result, shrink_limit):
        result.rows = parser.shrink_records(result.rows, shrink_limit).shrink_record_result
        result.row_count = len(result.rows)
