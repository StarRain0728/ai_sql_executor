from typing import Any

from core.context import get_user_context
from models.model import TableRuleInfo
from repositories.table_filter_rule_repository import TableFilterRuleRepository
from utils import param_resolve


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
        user_info = get_user_context()
        result_list = []
        for table_rule_info in table_rule_info_list:
            param_map = {table_rule_info.table_name: table_rule_info.condition}
            param_map.update(user_info.model_dump())
            result_list.append(param_resolve.resolve(param_map))
        return result_list
