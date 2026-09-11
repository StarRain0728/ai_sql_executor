from __future__ import annotations

import json
from typing import Any

import sqlglot
from sqlglot import exp, ParseError

from core.exceptions import SqlValidationError, AppError
from models.model import TableInfo, ColumnInfo
import logging

from utils.json_utils import to_json_default

logger = logging.getLogger(__name__)


class SqlParser:
    def __init__(self, sql: str, dialect: str):
        self._sql = sql.strip().rstrip(";")
        self._dialect = dialect
        self._tree = None
        self._ref_table_columns: list[TableInfo] = []
        self._shrink_record_result = []

    @property
    def sql(self):
        return self._sql

    @property
    def ref_table_columns(self):
        return self._ref_table_columns

    @property
    def shrink_record_result(self):
        return self._shrink_record_result

    def parse(self, strict_mode: bool) -> SqlParser:
        """
        解析SQL语句并构建语法树。
        参数:
        - strict_mode: bool类型，指示是否启用严格模式。在严格模式下，不允许执行多个SQL语句或非SELECT语句。
        返回:
        - SqlParser对象自身，支持链式调用。
        异常:
        - 如果SQL为空，则抛出SqlValidationError。
        - 如果在严格模式下检测到分号或非SELECT语句，则抛出SqlValidationError。
        - 如果SQL解析失败，则抛出SqlValidationError。
        """
        # 检查SQL是否为空
        if not self._sql:
            raise SqlValidationError(sql="", reason="SQL 为空")

        try:
            # 使用sqlglot库解析SQL语句
            self._tree = sqlglot.parse_one(self._sql, read=self._dialect)

            # 在严格模式下检查是否存在分号，存在则表示尝试执行多条SQL语句
            if strict_mode and ";" in self._sql:
                logger.error("%s is not a select statement", self._sql)
                raise SqlValidationError(self._sql, reason="禁止多sql执行")

            # 处理WITH子句，寻找最外层的查询表达式
            outer = self._tree.this if isinstance(self._tree, exp.With) else self._tree

            # 跳过子查询和括号表达式，直到找到最外层的查询表达式
            while isinstance(outer, (exp.Subquery, exp.Paren)):
                outer = outer.this

            # 检查最外层表达式是否为SELECT、UNION、INTERSECT或EXCEPT之一，否则视为非法SQL
            if not isinstance(outer, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
                logger.error("%s is not a select statement", self._sql)
                raise SqlValidationError(self._sql, reason="禁止执行的sql语句")
        except AppError as ax:
            raise ax
        except Exception as exc:
            # 捕获并记录解析过程中出现的异常
            logger.error("SQL 校验失败: %s", self._sql, exc)
            raise SqlValidationError(self._sql, str(exc))

        # 返回SqlParser对象自身，支持链式调用
        return self

    def add_limit(self, max_limit: int) -> SqlParser:
        """
        向SQL查询添加或更新LIMIT限制。

        参数:
        - max_limit: int, 要设置的最大LIMIT值。

        返回:
        - SqlParser: 返回SqlParser实例自身，支持链式调用。
        """
        # 确定要修改的外部查询部分
        outer = self._tree.this if isinstance(self._tree, exp.With) else self._tree

        # 获取当前的LIMIT值，如果存在的话
        existing_limit = getattr(outer, "args", {}).get("limit") if hasattr(outer, "args") else None

        # 检查并比较现有的LIMIT与传入的最大LIMIT值
        if isinstance(existing_limit, exp.Limit) and isinstance(existing_limit.expression, exp.Literal):
            try:
                current = int(existing_limit.expression.this)
                logger.info("sql已存在limit限制: %s", current)
                if current <= max_limit:
                    max_limit = current
            except Exception as exe:
                logger.error("更改limit限制失败: %s", str(exe))
                pass

        # 设置或更新LIMIT值
        if hasattr(outer, "set"):
            outer.set("limit", exp.Limit(expression=exp.Literal.number(max_limit)))
            self._sql = self._tree.sql(dialect=self._dialect)

        return self

    def parse_lineage(self) -> SqlParser:
        """
        解析SQL语句中的表和列信息，建立表别名和列别名的映射关系，并整理这些信息以便后续处理。

        Returns:
        SqlParser: 返回SqlParser实例本身，以便于方法链式调用。
        """
        # 初始化表信息字典，用于存储表名、别名和列信息
        table_entries: dict[str, dict[str, Any]] = {}
        # 初始化表别名映射字典，用于快速查找表别名对应的表名
        table_alias_mapping: dict[str, str] = {}
        # 初始化列别名映射字典，用于存储列别名信息
        columns_alias_mapping = {}

        # 遍历AST树中的所有表节点，收集表信息
        for node in self._tree.find_all(exp.Table):
            if isinstance(node, exp.Table):
                # 提取表名和别名，确保它们是字符串类型
                name = node.name if isinstance(node.name, str) and node.name else ""
                alias = node.alias if isinstance(node.alias, str) and node.alias else ""
                # 在表信息字典中设置表名对应的默认值
                table_entries.setdefault(
                    name,
                    {
                        "table_name": name,
                        "alias": alias,
                        "columns": {}
                    }
                )
                # 如果表有别名，则在表别名映射字典中记录别名和表名的对应关系
                if alias:
                    table_alias_mapping[alias] = name

        # 遍历AST树中的所有节点，收集列别名信息
        for node in self._tree.walk():
            if not isinstance(node, exp.Alias):
                continue

            if isinstance(node.this, exp.Column):
                col = node.this
                # 提取列名，确保它是字符串类型
                name = col.name if isinstance(col.name, str) and col.name else ""
                if not name:
                    continue
                # 提取表名，确保它是字符串类型，并通过表别名映射字典找到实际的表名
                table = col.table if isinstance(col.table, str) and col.table else ""
                table_name = table_alias_mapping.get(table, table)
                # 提取列别名
                col_alias = node.alias if isinstance(node.alias, str) else ""

                # 如果列有别名，则在列别名映射字典中记录(表名, 列名)与列别名的对应关系
                if col_alias:
                    columns_alias_mapping[(table_name, name)] = str(col_alias)

        # 再次遍历AST树中的所有列节点，完善表信息字典中的列信息
        for node in self._tree.walk():
            if not isinstance(node, exp.Column):
                continue

            name = node.name if isinstance(node.name, str) and node.name else ""
            if not name:
                continue

            table = node.table if isinstance(node.table, str) and node.table else ""
            table_name = table_alias_mapping.get(table, table)

            table_entry = table_entries.setdefault(
                table_name,
                {
                    "table_name": table_name,
                    "alias": "",
                    "columns": {}
                }
            )
            # 在表的列信息中记录列名和对应的列别名
            table_entry["columns"][name] = {
                "column_name": name,
                "alias": columns_alias_mapping.get((table_name, name), ""),
            }

        # 根据表名排序，整理表信息，准备添加到引用表列表中
        for table_name in sorted(table_entries.keys()):
            row = table_entries[table_name]
            # 构建TableInfo对象，并添加到引用表列表
            self._ref_table_columns.append(
                TableInfo(
                    name=row["table_name"],
                    alias=row["alias"],
                    columns=[
                        ColumnInfo(
                            name=column["column_name"],
                            alias=column["alias"]
                        )
                        for column in row["columns"].values()
                    ]
                )
            )

        # 返回SqlParser实例本身，支持方法链式调用
        return self

    def shrink_records(self, records: list[dict[str, Any]], shrink_limit: int) -> SqlParser:
        """
        缩减记录集以适应token限制。

        此函数遍历给定的记录列表，将每条记录转换为JSON字符串，并检查其长度是否超过指定的缩减限制。
        如果首条记录长度超过限制，直接记录警告并停止处理。
        如果累计长度加上下一条记录的长度超过限制，则记录信息并停止处理，确保不超过token限制。

        参数:
        - records: 一个字典列表，每个字典代表一条记录。
        - shrink_limit: 一个整数，表示token的最大限制。

        返回:
        - 返回SqlParser实例，支持链式调用。
        """
        # 初始化结果列表和总长度计数器
        result = []
        total_len = 0

        # 遍历记录列表
        for i, record in enumerate(records):
            # 将记录转换为JSON字符串
            record_str = json.dumps(record, ensure_ascii=False, default=to_json_default)
            # 计算记录的长度
            record_len = len(record_str)

            # 检查首条记录是否过长
            if i == 0 and record_len > shrink_limit:
                logger.warning("结果集第一条token过长:%s", record_len)
                break

            # 检查累计长度是否达到限制
            if total_len + record_len > shrink_limit:
                logger.info("截止第%d条, token已达到限制:%s", i)
                break

            # 添加记录到结果列表，并更新总长度
            result.append(json.loads(record_str))
            total_len += record_len

        # 存储处理后的记录结果
        self._shrink_record_result = result
        # 支持链式调用，返回当前实例
        return self

    def rewrite(self, table_rules: dict[str, list[str]]) -> SqlParser:
        """
        重写SQL解析器中的表规则。

        参数:
        - table_rules: 一个字典，其中键是表名，值是该表对应的规则列表。

        返回:
        - SqlParser: 返回重写后的SqlParser对象。

        此方法用于根据提供的表规则重写SQL查询。如果未提供表规则或规则为空，
        则直接返回当前SqlParser实例。通过规范化规则并处理所有选择节点来实现重写。
        """
        # 检查是否提供了表规则，如果没有，则直接返回当前实例
        if not table_rules:
            return self

        # 规范化输入的规则，以便于后续处理
        normalized_rules = self._normalize_rules(table_rules)

        # 遍历SQL树中的所有选择节点，并应用规范化后的规则进行处理
        for select_node in self._tree.find_all(exp.Select):
            self._process_select_node(select_node, normalized_rules)

        # 更新SQL字符串，反映重写后的结果
        self._sql = self._tree.sql(dialect=self._dialect)

        return self

    @staticmethod
    def _normalize_rules(table_rules: dict[str, list[str]]) -> dict[str, list[str]]:
        """
        处理表规则
        """
        normalized = {}
        for table_name, rules in table_rules.items():
            if not rules:
                continue

            # Clean up the table name
            cleaned_table_name = table_name.strip().strip("`\"[]").lower()
            if not cleaned_table_name:
                continue

            # Clean up the rules
            cleaned_rules = [rule.strip() for rule in rules if isinstance(rule, str) and rule.strip()]
            if cleaned_rules:
                normalized[cleaned_table_name] = cleaned_rules

        return normalized

    def _process_select_node(self, select_node: exp.Select, table_rules: dict[str, list[str]]) -> None:
        """
        处理选择节点(select_node)，根据表规则(table_rules)修改选择节点的条件。

        参数:
        - select_node: 表示SQL查询中的SELECT语句的部分结构。
        - table_rules: 包含表名及其对应规则的字典。
        """
        # 获取选择节点中的FROM子句
        from_clause = select_node.args.get("from")
        # 如果没有FROM子句，则直接返回
        if not from_clause:
            return

        # 提取FROM子句中的表节点
        table_node = from_clause.this
        # 如果表节点不是期望的Table类型，则直接返回
        if not isinstance(table_node, exp.Table):
            return

        # 分别获取表的名称、数据库名和目录名
        name = table_node.name or ""
        db = table_node.db or ""
        catalog = table_node.catalog or ""

        # 初始化候选列表，用于存储可能匹配的表全名
        candidates = []
        # 根据目录、数据库和表名是否存在，生成所有可能的表标识符
        if catalog and db and name:
            candidates.append(f"{catalog}.{db}.{name}".lower())
        if db and name:
            candidates.append(f"{db}.{name}".lower())
        if name:
            candidates.append(name.lower())

        # 初始化匹配的规则和候选标识符
        matched_rules = None
        matched_candidate = None
        # 遍历候选列表，寻找匹配的表规则
        for candidate in candidates:
            if candidate in table_rules:
                matched_rules = table_rules[candidate]
                matched_candidate = candidate
                break

        # 如果没有找到匹配的规则，则直接返回
        if not matched_rules:
            return

        # 调用内部方法，根据匹配的规则追加条件到选择节点
        self._append_conditions(select_node, matched_candidate, matched_rules)

    def _append_conditions(self, select_node: exp.Select, table_name: str, condition_strings: list[str]) -> None:
        if not condition_strings:
            return

        condition_nodes = []
        for cond_str in condition_strings:
            try:
                cond_node = sqlglot.parse_one(cond_str, read=self._dialect, into=exp.Condition)
                condition_nodes.append(cond_node)
            except ParseError as e:
                logger.error(f"Failed to parse condition: {cond_str}. Error: {e}")
                raise SqlValidationError(sql=cond_str,
                                         reason=f"Invalid table filter rule for '{table_name}': {cond_str}") from e

        combined_new_condition = condition_nodes[0]
        for cond_node in condition_nodes[1:]:
            combined_new_condition = exp.and_(combined_new_condition, cond_node)

        existing_where = select_node.args.get("where")
        if existing_where and existing_where.this is not None:
            final_condition = exp.and_(existing_where.this, combined_new_condition)
        else:
            final_condition = combined_new_condition

        select_node.set("where", exp.Where(this=final_condition))

