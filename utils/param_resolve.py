from datetime import datetime, timedelta

DATE_PREFIX = "%%"
TODAY = "%%TODAY"
NC_TODAY = "%%NCTODAY"
TODAY_ZERO = "%%TODAYZERO"
TODAY_BEFORE = "%%TODAY-"
TODAY_AFTER = "%%TODAY+"
NC_TODAY_ZERO = "%%NCTODAYZERO"
NC_TODAY_BEFORE = "%%NCTODAY-"
NC_TODAY_AFTER = "%%NCTODAY+"
PLACEHOLDER = "${%s}"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def resolve(param_map):
    resolver_map = {}
    if not param_map:
        return resolver_map

    for key, value in param_map.items():
        # 解析特殊表达式
        value = resolve_special(value, key)
        resolver_map[key] = value

    for key, value in resolver_map.items():
        # 解析占位符
        value = resolve_placeholders(value, resolver_map)
        resolver_map[key] = value

    return resolver_map


def resolve_placeholders(value, param_map):
    result = value
    for key, val in param_map.items():
        placeholder = PLACEHOLDER % key
        if placeholder in result:
            result = result.replace(placeholder, val)
    return result


def resolve_special(value, param_name):
    if not value.startswith(DATE_PREFIX):
        return value
    custom_format = DEFAULT_DATE_FORMAT
    ampersand_idx = value.find('&')
    if ampersand_idx != -1:
        custom_format = value[ampersand_idx + 1:]
        value = value[:ampersand_idx]  # 移除自定义格式部分以便后续处理

    if value == TODAY:
        return format_date(datetime.now(), custom_format)
    elif value == NC_TODAY:
        return format_date(datetime.now() - timedelta(seconds=1), custom_format)
    elif value.startswith(TODAY_BEFORE):
        n = int(value[len(TODAY_BEFORE):])
        return format_date(datetime.now() - timedelta(days=n), custom_format)
    elif value.startswith(TODAY_AFTER):
        n = int(value[len(TODAY_AFTER):])
        return format_date(datetime.now() + timedelta(days=n), custom_format)
    elif value.startswith(NC_TODAY_BEFORE):
        n = int(value[len(NC_TODAY_BEFORE):])
        return format_date(datetime.now() - timedelta(days=n, seconds=1), custom_format)
    elif value.startswith(NC_TODAY_AFTER):
        n = int(value[len(NC_TODAY_AFTER):])
        return format_date(datetime.now() + timedelta(days=n, seconds=-1), custom_format)
    elif value.startswith(TODAY_ZERO):
        return format_date(deal_hour(value[len(TODAY_ZERO):]), custom_format)
    elif value.startswith(NC_TODAY_ZERO):
        return format_date(deal_hour(value[len(TODAY_ZERO):]) - timedelta(seconds=1), custom_format)
    else:
        return value


def deal_hour(value):
    today = datetime.now().date()
    hour = 0
    tilde_idx = value.find("~")
    if tilde_idx != -1:
        hour = int(value[tilde_idx + 1:])
        value = value[:tilde_idx]
    if value:
        today += timedelta(days=int(value))
    return datetime.combine(today, datetime.min.time()).replace(hour=hour)


def format_date(date, format_str=DEFAULT_DATE_FORMAT):
    return date.strftime(format_str)
