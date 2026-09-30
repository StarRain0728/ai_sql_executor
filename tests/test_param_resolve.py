"""param_resolve 单元测试：日期占位符解析。"""
import re
from datetime import datetime, timedelta

from utils import param_resolve as pr

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class TestResolveSpecial:
    def test_plain_value_untouched(self):
        assert pr.resolve_special("abc", "p") == "abc"

    def test_today_format(self):
        v = pr.resolve_special(pr.TODAY, "p")
        assert _DATE_RE.match(v)

    def test_nc_today_is_one_second_before_today(self):
        today = datetime.strptime(pr.resolve_special(pr.TODAY, "p"), pr.DEFAULT_DATE_FORMAT)
        nc = datetime.strptime(pr.resolve_special(pr.NC_TODAY, "p"), pr.DEFAULT_DATE_FORMAT)
        assert (today - nc).total_seconds() == 1

    def test_today_before(self):
        base = datetime.now() - timedelta(days=3)
        v = datetime.strptime(pr.resolve_special("%%TODAY-3", "p"), pr.DEFAULT_DATE_FORMAT)
        assert abs((v - base).total_seconds()) < 2

    def test_today_after(self):
        base = datetime.now() + timedelta(days=3)
        v = datetime.strptime(pr.resolve_special("%%TODAY+3", "p"), pr.DEFAULT_DATE_FORMAT)
        assert abs((v - base).total_seconds()) < 2

    def test_nc_today_before_minus_one_second(self):
        nc = datetime.strptime(pr.resolve_special("%%NCTODAY-3", "p"), pr.DEFAULT_DATE_FORMAT)
        base = datetime.now() - timedelta(days=3)
        assert abs((nc - base).total_seconds()) < 2

    def test_nc_today_after_minus_one_second(self):
        nc = datetime.strptime(pr.resolve_special("%%NCTODAY+3", "p"), pr.DEFAULT_DATE_FORMAT)
        base = datetime.now() + timedelta(days=3) - timedelta(seconds=1)
        assert abs((nc - base).total_seconds()) < 2

    def test_today_zero_is_midnight(self):
        v = pr.resolve_special(pr.TODAY_ZERO, "p")
        dt = datetime.strptime(v, pr.DEFAULT_DATE_FORMAT)
        assert dt.date() == datetime.now().date()
        assert dt.hour == 0

    def test_today_zero_with_hour_suffix(self):
        dt = datetime.strptime(pr.resolve_special("%%TODAYZERO~9", "p"), pr.DEFAULT_DATE_FORMAT)
        assert dt.hour == 9

    def test_nc_today_zero_parses_correctly(self):
        """%%NCTODAYZERO 应为「当日零点前 1 秒」。

        回归用例：旧实现按 TODAY_ZERO 长度切片，残留 'NC' 导致 int('NC') 抛错，
        解析失败后原样返回未解析的占位符。
        """
        v = pr.resolve_special(pr.NC_TODAY_ZERO, "p")
        assert v != pr.NC_TODAY_ZERO, "占位符未被解析"
        dt = datetime.strptime(v, pr.DEFAULT_DATE_FORMAT)
        expected = datetime.combine(datetime.now().date(), datetime.min.time()) - timedelta(seconds=1)
        assert dt == expected

    def test_nc_today_zero_with_day_and_hour(self):
        v = pr.resolve_special("%%NCTODAYZERO1~9", "p")
        assert v != "%%NCTODAYZERO1~9"
        dt = datetime.strptime(v, pr.DEFAULT_DATE_FORMAT)
        expected = (datetime.combine(datetime.now().date(), datetime.min.time())
                    + timedelta(days=1)).replace(hour=9) - timedelta(seconds=1)
        assert dt == expected

    def test_custom_format_via_ampersand(self):
        v = pr.resolve_special("%%TODAY&%Y%m%d", "p")
        assert re.match(r"^\d{8}$", v)

    def test_unknown_prefix_returned_as_is(self):
        assert pr.resolve_special("%%UNKNOWN", "p") == "%%UNKNOWN"


class TestResolve:
    def test_none_map(self):
        assert pr.resolve(None) == {}

    def test_placeholder_substitution(self):
        result = pr.resolve({"a": "hello", "b": "${a} world"})
        assert result["b"] == "hello world"

    def test_special_and_placeholder_together(self):
        result = pr.resolve({"d": pr.TODAY, "q": "${d}"})
        assert _DATE_RE.match(result["q"])
