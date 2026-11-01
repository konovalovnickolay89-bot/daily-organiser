from datetime import date, datetime
from zoneinfo import ZoneInfo


def house_today(tz_name: str) -> date:
    return datetime.now(ZoneInfo(tz_name)).date()


def utcnow() -> datetime:
    return datetime.now(ZoneInfo("UTC"))
