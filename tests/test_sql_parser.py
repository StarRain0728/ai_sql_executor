"""SqlParser 单元测试：只读校验 / 多语句拦截 / limit 改写 / 血缘解析 / 表规则改写。"""
import logging

import pytest

from core.exceptions import SqlValidationError
from services.sql_parser import SqlParser

DIALECT = "clickhouse"


def _parse(sql, strict=True, dialect=DIALECT):
    return SqlParser(sql, dialect).parse(strict_mode=strict)


class TestParseReadonlyGuard:
    def test_select_allowed(self):
        parser = _parse("select * from t")
        assert parser.sql == "select * from t"

    def test_with_allowed(self):
        parser = _parse("with c as (select 1) select * from c")
        assert "with" in parser.sql.lower()

    def test_union_allowed(self):
        assert _parse("select 1 union all select 2").sql

    def test_subquery_paren_allowed(self):
        assert _parse("select * from (select 1 as a) x").sql

    def test_empty_sql_rejected(self):
        with pytest.raises(SqlValidationError):
            _parse("   ")

    @pytest.mark.parametrize("sql", [
        "drop table t",
        "delete from t",
        "insert into t values (1)",
        "update t set a = 1",
        "alter table t add column c int",
        "truncate table t",
        "create table t (a int)",
    ])
    def test_write_statements_rejected(self, sql):
        with pytest.raises(SqlValidationError):
            _parse(sql)


class TestMultiStatementGuard:
    def test_trailing_semicolon_tolerated(self):
        # 尾部单分号被 strip 掉，属正常单语句
        assert _parse("select 1;").sql

    def test_multi_statement_rejected_in_strict(self):
        with pytest.raises(SqlValidationError) as exc:
            _parse("select 1; select 2", strict=True)
        assert "多sql" in exc.value.details["reason"]

    def test_injection_via_semicolon_rejected(self):
        with pytest.raises(SqlValidationError) as exc:
            _parse("select 1; drop table t", strict=True)
        assert "多sql" in exc.value.details["reason"]

    def test_parse_failure_raises_validation_error(self):
        with pytest.raises(SqlValidationError):
            _parse("select * from where")


class TestAddLimit:
    def test_add_limit_when_absent(self):
        parser = _parse("select * from t").add_limit(50)
        assert "limit 50" in parser.sql.lower()

    def test_keep_smaller_existing_limit(self):
        parser = _parse("select * from t limit 10").add_limit(100)
        assert "limit 10" in parser.sql.lower()

    def test_cap_larger_existing_limit(self):
        parser = _parse("select * from t limit 100").add_limit(10)
        assert "limit 10" in parser.sql.lower()

    def test_limit_applied_on_with_clause(self):
        parser = _parse("with c as (select 1) select * from c").add_limit(20)
        assert "limit 20" in parser.sql.lower()


class TestParseLineage:
    def test_collect_tables_and_alias(self):
        parser = _parse("select a.id from t a").parse_lineage()
        names = [t.name for t in parser.ref_table_columns]
        assert "t" in names
        table = next(t for t in parser.ref_table_columns if t.name == "t")
        assert table.alias == "a"

    def test_collect_join_tables(self):
        parser = _parse("select * from t1 join t2 on t1.id = t2.id").parse_lineage()
        names = {t.name for t in parser.ref_table_columns}
        assert {"t1", "t2"}.issubset(names)

    def test_column_alias_recorded(self):
        parser = _parse("select t.c as cnt from t").parse_lineage()
        table = next(t for t in parser.ref_table_columns if t.name == "t")
        col = next(c for c in table.columns if c.name == "c")
        assert col.alias == "cnt"

    def test_no_table_select_literal(self):
        parser = _parse("select 1").parse_lineage()
        assert parser.ref_table_columns == []


class TestShrinkRecords:
    def test_shrink_breaks_on_first_oversized(self):
        parser = _parse("select 1")
        big = [{"a": "x" * 100}]
        parser.shrink_records(big, shrink_limit=10)
        assert parser.shrink_record_result == []

    def test_shrink_accumulates_until_limit(self):
        parser = _parse("select 1")
        records = [{"a": 1}, {"a": 2}, {"a": 3}]
        parser.shrink_records(records, shrink_limit=15)
        assert 0 < len(parser.shrink_record_result) < len(records)

    def test_shrink_keeps_all_when_under_limit(self):
        parser = _parse("select 1")
        records = [{"a": 1}, {"a": 2}]
        parser.shrink_records(records, shrink_limit=1000)
        assert parser.shrink_record_result == records

    def test_shrink_limit_log_is_formatted(self, caplog):
        """回归：触发缩容时日志占位符数多于参数，会抛 logging 格式化错误并丢失该行日志。"""
        parser = _parse("select 1")
        with caplog.at_level(logging.INFO, logger="services.sql_parser"):
            parser.shrink_records([{"a": 1}, {"a": 2}, {"a": 3}], shrink_limit=15)
        # getMessage() 在占位符/参数不匹配时会抛 TypeError，即旧实现的缺陷
        messages = [record.getMessage() for record in caplog.records]
        assert any("token已达到限制" in message for message in messages)


class TestRewrite:
    def test_no_rules_returns_unchanged(self):
        parser = _parse("select * from t")
        assert parser.rewrite({}).sql == "select * from t"

    def test_append_rule_condition(self):
        parser = _parse("select * from t").rewrite({"t": ["dept_id = '1'"]})
        assert "dept_id" in parser.sql

    def test_merge_with_existing_where(self):
        parser = _parse("select * from t where a = 1").rewrite({"t": ["dept_id = '1'"]})
        assert "a = 1" in parser.sql
        assert "dept_id" in parser.sql

    def test_rule_matches_db_qualified_table(self):
        parser = _parse("select * from db1.t").rewrite({"db1.t": ["x = 1"]})
        assert "x = 1" in parser.sql

    def test_unmatched_table_untouched(self):
        parser = _parse("select * from other").rewrite({"t": ["x = 1"]})
        assert "x = 1" not in parser.sql

    def test_normalize_strips_quotes_and_lowercases(self):
        parser = _parse("select * from T").rewrite({"`T`": ["  x = 1  "]})
        assert "x = 1" in parser.sql

    def test_empty_rule_list_ignored(self):
        parser = _parse("select * from t").rewrite({"t": []})
        assert "x" not in parser.sql

    def test_invalid_rule_condition_raises(self):
        with pytest.raises(SqlValidationError):
            _parse("select * from t").rewrite({"t": ["not a valid condition !!!"]})
