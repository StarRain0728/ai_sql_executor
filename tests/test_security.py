"""安全测试：SQL 注入 / 多语句绕过 / 行级过滤规则绕过 / 表名注入。

覆盖引擎侧「不可信输入」的三条路径：
1. 用户 SQL 文本 → SqlParser（只读校验 + 多语句拦截 + 行级过滤规则改写）
2. 请求体中的表名 → /tables/samples（标识符拼接，不得注入 SQL 片段）
3. 表级权限 → SqlPermissionService（越权拦截）
"""
from types import SimpleNamespace

import pytest

from core.exceptions import SqlValidationError, TablePermissionDeniedError
from models.model import TableInfo
from services import sql_permission_service as sps
from services.sql_parser import SqlParser
from services.sql_permission_service import SqlPermissionService

DIALECT = "clickhouse"


def _parse(sql, strict=True):
    return SqlParser(sql, DIALECT).parse(strict_mode=strict)


def _rewrite(sql, rules, strict=True):
    return _parse(sql, strict=strict).rewrite(rules).add_limit(50).sql


class TestMultiStatementAndInjection:
    """严格模式下的多语句 / 注入文本必须整条拒绝。"""

    @pytest.mark.parametrize("sql", [
        "select 1; drop table t",
        "select 1;\ndrop table t",
        "select 1; select 2",
        "select 1 /*x*/ ; drop table t",
        "select * from t; truncate table t",
        "select 1;insert into t values(1)",
    ])
    def test_semicolon_batch_rejected(self, sql):
        with pytest.raises(SqlValidationError) as exc:
            _parse(sql, strict=True)
        assert "多sql" in exc.value.details["reason"]

    @pytest.mark.parametrize("sql", [
        "/* ; */ select 1",           # 注释中夹带分号：宁可误拒不可放过
        "select 'a;b' as v",          # 字符串字面量含分号：fail-closed
    ])
    def test_semicolon_in_comment_or_literal_fails_closed(self, sql):
        with pytest.raises(SqlValidationError):
            _parse(sql, strict=True)

    @pytest.mark.parametrize("sql", [
        "drop table t",
        "delete from t",
        "update t set a = 1",
        "insert into t values (1)",
        "truncate table t",
        "alter table t add column c int",
        "create table t (a int)",
        "grant select on t to u",
        "/* c */ drop table t",
    ])
    def test_write_statements_rejected(self, sql):
        with pytest.raises(SqlValidationError):
            _parse(sql, strict=True)

    def test_batch_rejected_even_when_strict_mode_disabled(self):
        """纵深防御：即便调用方关闭 strict_mode，AST 层也不接受一批语句。"""
        with pytest.raises(SqlValidationError):
            _parse("select 1; drop table t", strict=False)

    def test_single_trailing_semicolon_is_tolerated(self):
        assert _parse("select 1;", strict=True).sql


class TestRowFilterRuleBypass:
    """行级过滤规则（table_filter_rule）不得被 JOIN / 子查询等写法绕过。"""

    RULES = {"t2": ["dept_id = '1'"]}

    @pytest.mark.parametrize("sql", [
        "select * from t2",
        "select * from db1.t2",
        "select * from (select * from t2) x",
        "with c as (select * from t2) select * from c",
        "select * from t2 union all select * from t2",
    ])
    def test_rule_applied_on_common_shapes(self, sql):
        assert "dept_id = '1'" in _rewrite(sql, self.RULES)

    @pytest.mark.parametrize("sql", [
        "select * from t1 join t2 on t1.id = t2.id",
        "select * from t1 left join t2 on t1.id = t2.id",
        "select * from t1 right join t2 on t1.id = t2.id",
        "select * from t1 inner join t2 on t1.id = t2.id",
        "select * from t1, t2",
    ])
    def test_rule_applied_on_joined_table(self, sql):
        """回归：此前只对 FROM 主表生效，`from 允许表 join 受限表` 可读到未过滤数据。"""
        result = _rewrite(sql, self.RULES)
        assert "dept_id = '1'" in result, f"JOIN 表规则被绕过: {result}"

    def test_rule_applied_on_each_joined_table(self):
        rules = {"t2": ["a = 1"], "t3": ["b = 2"]}
        result = _rewrite("select * from t1 join t2 on t1.id = t2.id join t3 on t1.id = t3.id", rules)
        assert "a = 1" in result and "b = 2" in result

    def test_self_join_applies_rule_once(self):
        rules = {"t2": ["dept_id = '1'"]}
        result = _rewrite("select * from t2 a join t2 b on a.id = b.id", rules)
        assert result.count("dept_id = '1'") == 1

    def test_join_rules_merge_with_existing_where(self):
        result = _rewrite("select * from t1 join t2 on t1.id = t2.id where t1.x = 1", self.RULES)
        assert "t1.x = 1" in result and "dept_id = '1'" in result

    def test_invalid_rule_condition_raises_instead_of_passing(self):
        """规则本身不合法时应整条拒绝，而不是静默跳过过滤条件。"""
        with pytest.raises(SqlValidationError):
            _rewrite("select * from t2", {"t2": ["not a valid condition !!!"]})


class TestTableFunctionAndSsrf:
    """表函数必须被拒绝：绕过数据源配置与表权限，可造成 SSRF / 任意文件读取。"""

    @pytest.mark.parametrize("sql", [
        "select * from url('http://169.254.169.254/latest/meta-data/', CSV)",   # 云元数据 SSRF
        "select * from url('http://127.0.0.1:6379/', CSV)",                    # 内网探测
        "select * from file('/etc/passwd', CSV)",                              # 任意文件读取
        "select * from file('../../etc/shadow', LineAsString)",                # 路径穿越
        "select * from s3('http://minio:9000/b/k', 'ak', 'sk', CSV)",          # 对象存储外联
        "select * from mysql('10.0.0.1:3306', 'db', 't', 'u', 'p')",           # 越权直连他库
        "select * from remote('10.0.0.1', db, t)",                             # 集群外联
        "select * from numbers(10)",
    ])
    def test_dangerous_table_function_rejected(self, sql):
        with pytest.raises(SqlValidationError) as exc:
            _parse(sql, strict=True)
        assert "表函数" in exc.value.details["reason"]

    def test_table_function_rejected_in_subquery_and_join(self):
        """藏在子查询 / JOIN 中的表函数同样必须被拦下。"""
        with pytest.raises(SqlValidationError):
            _parse("select * from (select * from url('http://x/', CSV)) t", strict=True)
        with pytest.raises(SqlValidationError):
            _parse("select * from t1 join file('/etc/passwd', CSV) t2 on 1=1", strict=True)

    def test_table_function_rejected_even_when_strict_mode_disabled(self):
        """纵深防御：关闭 strict_mode 也不放开表函数。"""
        with pytest.raises(SqlValidationError):
            _parse("select * from url('http://127.0.0.1/', CSV)", strict=False)

    @pytest.mark.parametrize("sql", [
        "select * from t",
        "select * from db1.t",
        "select * from `t`",
        "select * from system.numbers limit 3",
        "with c as (select * from t) select * from c",
        "select * from t1 join t2 on t1.id = t2.id",
    ])
    def test_ordinary_table_sources_still_accepted(self, sql):
        """普通表 / 库表 / 引号表 / CTE / JOIN 不得被误拦截。"""
        assert _parse(sql, strict=True).sql


class TestSamplesTableNameInjection:
    """表名走标识符校验：不接受任何 SQL 片段拼接。"""

    @staticmethod
    def _build_sql(table_name, dialect=DIALECT):
        import sqlglot
        from sqlglot import exp
        table_expr = sqlglot.parse_one(table_name, read=dialect, into=exp.Table)
        return exp.Select().select("*").from_(table_expr).limit(10).sql(dialect=dialect)

    @pytest.mark.parametrize("name", ["t", "db.t", "`t`"])
    def test_plain_identifier_accepted(self, name):
        assert "select" in self._build_sql(name).lower()

    @pytest.mark.parametrize("name", [
        "(select * from secret) s",   # 子查询注入：可绕过规则与权限读到任意表
        "t where 1=1",
        "t; drop table t",
        "t union all select * from secret",
        "t) -- x",
        "t limit 1-- ",
    ])
    def test_sql_fragment_rejected(self, name):
        import sqlglot
        with pytest.raises(sqlglot.errors.ParseError):
            self._build_sql(name)


class TestPermissionEnforcement:
    """表级权限：受限表必须拒绝，除非显式 skip_permission（系统旁路）。"""

    class _Repo:
        def __init__(self, unauthorized):
            self._unauthorized = unauthorized
            self.calls = []

        def find_unauthorized_tables(self, **kwargs):
            self.calls.append(kwargs)
            return list(self._unauthorized)

    def _service(self, monkeypatch, unauthorized, enabled=True):
        monkeypatch.setattr(sps, "get_settings", lambda: SimpleNamespace(check_table_permission=enabled))
        repo = self._Repo(unauthorized)
        return SqlPermissionService(repo), repo

    def test_denied_table_raises_permission_error(self, monkeypatch):
        service, _ = self._service(monkeypatch, ["secret"])
        with pytest.raises(TablePermissionDeniedError) as exc:
            service.permission_check(dept_id="d1", user_code="u1", datasource_id="ds",
                                     sql="select * from secret",
                                     ref_table_columns=[TableInfo(name="secret")])
        assert exc.value.status_code == "101"

    def test_join_tables_are_all_checked(self, monkeypatch):
        service, repo = self._service(monkeypatch, [])
        service.permission_check(dept_id="d1", user_code="u1", datasource_id="ds",
                                 sql="select * from t1 join secret on t1.id = secret.id",
                                 ref_table_columns=[TableInfo(name="t1"), TableInfo(name="secret")])
        assert repo.calls[0]["table_names"] == ["t1", "secret"]

    def test_skip_permission_is_an_explicit_system_bypass(self, monkeypatch):
        """skip_permission=True 时不查权限库——仅限系统内部调用，调用方不得自行开启。"""
        service, repo = self._service(monkeypatch, ["secret"])
        service.permission_check(dept_id="d1", user_code="u1", datasource_id="ds",
                                 sql="select * from secret",
                                 ref_table_columns=[TableInfo(name="secret")], skip_permission=True)
        assert repo.calls == []
