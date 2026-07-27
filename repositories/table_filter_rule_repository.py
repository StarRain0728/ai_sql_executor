from sqlalchemy import select
from sqlalchemy.orm import Session

from models.model import TableRuleInfo
from repositories.entities import TableFilterRuleEntity, TableEntity


class TableFilterRuleRepository:
    def __init__(self, session: Session):
        self._session = session

    def find_rules_by_datasource_id(self, datasource_id: str) -> list[TableRuleInfo]:
        # 查询table_filter_rule表中符合条件的规则条件及对应的表名
        filter_rule_stmt = select(
            TableEntity.table_name,
            TableFilterRuleEntity.rule_condition
        ).join(
            TableFilterRuleEntity, TableEntity.id == TableFilterRuleEntity.table_id
        ).filter(
            TableFilterRuleEntity.datasource_id == datasource_id,
        )

        # 执行查询并将结果整理成字典形式
        table_rule_info_list = []
        results = self._session.execute(filter_rule_stmt).fetchall()
        for table_name, rule_condition in results:
            table_rule_info_list.append(TableRuleInfo(table_name=table_name, condition=rule_condition))

        return table_rule_info_list
