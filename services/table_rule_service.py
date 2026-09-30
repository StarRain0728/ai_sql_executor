from typing import Any

from core.context import get_user_context
from models.model import TableRuleInfo
from repositories.table_filter_rule_repository import TableFilterRuleRepository
from utils import param_resolve

# 规则条件在占位符解析过程中的临时键名，避免与用户上下文字段（user_code 等）冲突
_RULE_CONDITION_KEY = "__rule_condition__"


class TableRuleService:
    def __init__(self, repository: TableFilterRuleRepository):
        self._table_filter_repository = repository

    def build_rules_by_datasource_id(self, datasource_id: str) -> dict[str, list[str]]:
        rules_by_table = {}
        table_rule_info_list = self._table_filter_repository.find_rules_by_datasource_id(datasource_id)

        resolve_result: list[dict[str, Any]] = self.rule_param_resolve(table_rule_info_list)
        for resolved_dict in resolve_result:
            for table_name, condition in resolved_dict.items():
                if table_name not in rules_by_table:
                    rules_by_table[table_name] = []
                rules_by_table[table_name].append(condition)
        return rules_by_table

    @staticmethod
    def rule_param_resolve(table_rule_info_list: list[TableRuleInfo]) -> list[dict[str, Any]]:
        """
        解析表规则条件中的占位符。

        用户上下文（user_code/user_name/user_dept_id/user_dept_name）只作为 `${...}` 的
        取值来源，不能混进返回值：返回值会被 build_rules_by_datasource_id 当作
        「表名 -> 规则条件」逐项展开，混入的上下文字段会被误认为是表名，
        导致 `user_code` / `user_name` 这类同名字表被追加无关条件；
        且表名与上下文字段重名时，规则条件会被上下文取值覆盖掉。
        """
        user_info = get_user_context()
        result_list = []
        for table_rule_info in table_rule_info_list:
            param_map = {_RULE_CONDITION_KEY: table_rule_info.condition}
            param_map.update(user_info.model_dump())
            resolved = param_resolve.resolve(param_map)
            result_list.append({table_rule_info.table_name: resolved[_RULE_CONDITION_KEY]})
        return result_list
