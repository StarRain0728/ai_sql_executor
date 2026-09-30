"""SQL 改写服务单元测试：追加过滤条件、去重、类型处理。"""
from services.sql_rewrite_service import append_filters, append_user_filter

DIALECT = "clickhouse"


class TestAppendFilters:
    def test_append_numeric_filter(self):
        sql = append_filters("select * from t", DIALECT, [("dept_id", 1)])
        assert "dept_id = 1" in sql

    def test_append_string_filter(self):
        sql = append_filters("select * from t", DIALECT, [("name", "abc")])
        assert "name = 'abc'" in sql

    def test_skip_empty_string_value(self):
        # 空字符串过滤值应被跳过（不追加条件），SQL 结构保持等价
        sql = append_filters("select * from t", DIALECT, [("name", "")])
        assert "name" not in sql

    def test_dedup_existing_equal_filter(self):
        sql = append_filters("select * from t where dept_id = 1", DIALECT, [("dept_id", 1)])
        assert sql.count("dept_id") == 1

    def test_append_merges_with_existing_where(self):
        sql = append_filters("select * from t where a = 1", DIALECT, [("dept_id", 1)])
        assert "a = 1" in sql and "dept_id = 1" in sql

    def test_invalid_sql_returned_unchanged(self):
        assert append_filters("select * from where", DIALECT, [("a", 1)]) == "select * from where"

    def test_union_sql_not_modified(self):
        # 顶层非 Select 时保持原样，避免把过滤条件加错位置
        sql = "select * from t union all select * from t2"
        assert append_filters(sql, DIALECT, [("a", 1)]) == sql


class TestAppendUserFilter:
    def test_default_column_user(self):
        sql = append_user_filter("select * from t", DIALECT, "u1")
        assert "user = 'u1'" in sql
