"""表级权限校验单元测试。"""
from types import SimpleNamespace

import pytest

from core.exceptions import TablePermissionDeniedError
from models.model import TableInfo
from repositories.table_permission_repository import TablePermissionRepository
from services import sql_permission_service as sps
from services.sql_permission_service import SqlPermissionService


class _FakeRepo:
    def __init__(self, unauthorized):
        self._unauthorized = unauthorized
        self.calls = []

    def find_unauthorized_tables(self, **kwargs):
        self.calls.append(kwargs)
        return list(self._unauthorized)


def _settings(check=True):
    return SimpleNamespace(check_table_permission=check)


def _tables(*names):
    return [TableInfo(name=n) for n in names]


def _svc(repo):
    return SqlPermissionService(repo)


def test_skip_permission_bypasses_repo(monkeypatch):
    monkeypatch.setattr(sps, "get_settings", lambda: _settings(True))
    repo = _FakeRepo(["t"])
    _svc(repo).permission_check(dept_id="d", user_code="u", datasource_id="ds",
                                sql="select 1", ref_table_columns=_tables("t"), skip_permission=True)
    assert repo.calls == []


def test_global_check_disabled_skips(monkeypatch):
    monkeypatch.setattr(sps, "get_settings", lambda: _settings(False))
    repo = _FakeRepo(["t"])
    _svc(repo).permission_check(dept_id="d", user_code="u", datasource_id="ds",
                                sql="select 1", ref_table_columns=_tables("t"))
    assert repo.calls == []


def test_no_tables_short_circuits(monkeypatch):
    monkeypatch.setattr(sps, "get_settings", lambda: _settings(True))
    repo = _FakeRepo([])
    _svc(repo).permission_check(dept_id="d", user_code="u", datasource_id="ds",
                                sql="select 1", ref_table_columns=[])
    assert repo.calls == []


def test_unauthorized_table_raises(monkeypatch):
    monkeypatch.setattr(sps, "get_settings", lambda: _settings(True))
    repo = _FakeRepo(["secret"])
    with pytest.raises(TablePermissionDeniedError) as exc:
        _svc(repo).permission_check(dept_id="d", user_code="u", datasource_id="ds",
                                    sql="select * from secret", ref_table_columns=_tables("secret"))
    assert exc.value.status_code == "101"


def test_authorized_table_passes(monkeypatch):
    monkeypatch.setattr(sps, "get_settings", lambda: _settings(True))
    repo = _FakeRepo([])
    _svc(repo).permission_check(dept_id="d", user_code="u", datasource_id="ds",
                                sql="select * from t", ref_table_columns=_tables("t"))
    assert repo.calls and repo.calls[0]["table_names"] == ["t"]


def test_extract_table_names_skips_empty():
    tables = [TableInfo(name="t"), TableInfo(name="")]
    assert SqlPermissionService._extract_table_names(tables) == ["t"]


class TestTablePermissionRepository:
    def test_empty_table_names_returns_empty_without_db(self):
        # 不触发数据库访问（session=None 也能安全返回）
        assert TablePermissionRepository(None).find_unauthorized_tables(
            dept_id="d", user_code="u", table_names=[], datasource_id="ds") == []
