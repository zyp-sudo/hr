from datetime import date, datetime
from typing import Any


def to_iso(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value
