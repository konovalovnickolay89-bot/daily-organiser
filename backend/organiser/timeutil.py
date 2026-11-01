from datetime import date, datetime
from zoneinfo import ZoneInfo


def house_now(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def house_today(tz_name: str) -> date:
    return house_now(tz_name).date()


def utcnow() -> datetime:
    return datetime.now(ZoneInfo("UTC"))
