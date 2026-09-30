"""行级过滤规则装配 + JSON 序列化工具单元测试。

TableRuleService 是行级数据权限的入口：把表规则里的占位符（${user_dept_id} 等）
按「当前请求用户身份」解析后交给 SqlParser 追加 WHERE。若解析拿错身份或丢规则，
就会出现越权或漏过滤，因此这里单独覆盖。
"""
from __future__ import annotations

import re
from datetime import date

from core.context import UserContext, set_user_context
from models.model import TableRuleInfo, TableInfo
from services.table_rule_service import TableRuleService
from utils.json_utils import to_json_default


class _FakeRuleRepository:
    def __init__(self, rows):
        self._rows = rows
        self.datasource_ids = []

    def find_rules_by_datasource_id(self, datasource_id):
        self.datasource_ids.append(datasource_id)
        return self._rows


def _rule(table_name: str, condition: str) -> TableRuleInfo:
    return TableRuleInfo(datasource_id="ds-1", table_name=table_name, condition=condition)


class TestBuildRulesByDatasourceId:
    def test_groups_rules_per_table_and_substitutes_user_context(self):
        repository = _FakeRuleRepository([
            _rule("orders", "dept_id = '${user_dept_id}'"),
            _rule("orders", "status = 1"),
            _rule("users", "1 = 1"),
        ])
        set_user_context(UserContext(user_code="u1", user_dept_id="d1", user_name="张三"))

        rules = TableRuleService(repository).build_rules_by_datasource_id("ds-1")

        assert repository.datasource_ids == ["ds-1"]
        assert rules == {"orders": ["dept_id = 'd1'", "status = 1"], "users": ["1 = 1"]}

    def test_no_rules_yields_empty_mapping(self):
        set_user_context(UserContext(user_code="u1"))
        assert TableRuleService(_FakeRuleRepository([])).build_rules_by_datasource_id("ds-1") == {}

    def test_user_context_fields_are_not_exposed_as_table_names(self):
        """回归：用户上下文字段曾被混入「表名 -> 规则」映射，成了 user_code/user_name 等伪表规则。"""
        repository = _FakeRuleRepository([_rule("orders", "dept_id = '${user_dept_id}'")])
        set_user_context(UserContext(user_code="u1", user_dept_id="d1", user_name="张三"))

        rules = TableRuleService(repository).build_rules_by_datasource_id("ds-1")

        assert set(rules) == {"orders"}

    def test_table_name_equal_to_context_field_keeps_its_own_rule(self):
        """回归：表名与上下文字段重名时，规则条件不能被上下文取值覆盖。"""
        repository = _FakeRuleRepository([_rule("user_name", "org_id = '7'")])
        set_user_context(UserContext(user_code="u1", user_name="张三"))

        rules = TableRuleService(repository).build_rules_by_datasource_id("ds-1")

        assert rules == {"user_name": ["org_id = '7'"]}

    def test_condition_that_is_a_date_placeholder_is_resolved(self):
        """条件整体为 %%TODAY 时走特殊表达式解析（与 param_resolve 语义保持一致）。"""
        repository = _FakeRuleRepository([_rule("orders", "%%TODAY")])
        set_user_context(UserContext(user_code="u1"))

        rules = TableRuleService(repository).build_rules_by_datasource_id("ds-1")

        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", rules["orders"][0])


class TestToJsonDefault:
    def test_dataclass_is_serialized_to_dict(self):
        assert to_json_default(TableInfo(name="orders", alias="o")) == {
            "name": "orders", "alias": "o", "schema": "", "columns": [],
        }

    def test_date_is_serialized_to_isoformat(self):
        assert to_json_default(date(2026, 1, 2)) == "2026-01-02"

    def test_object_with_to_dict_uses_that_method(self):
        class _HasToDict:
            def to_dict(self):
                return {"k": "v"}

        assert to_json_default(_HasToDict()) == {"k": "v"}

    def test_unknown_object_falls_back_to_str(self):
        assert to_json_default(object()).startswith("<object object at")
