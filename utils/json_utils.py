from dataclasses import is_dataclass, asdict
from datetime import date


def to_json_default(obj):
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    try:
        return vars(obj)
    except TypeError:
        pass
    return str(obj)
