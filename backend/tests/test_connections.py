"""Scaffolding for later connections. No client calls Google, TfL, or a geocoder."""

from organiser.config import (
    COMMUTE_ORIGIN,
    WEMBLEY_POINT,
    calendar_id_list,
    commute_point_for_label,
    get_settings,
)


def test_calendar_ids_default_to_primary(monkeypatch):
    assert calendar_id_list("") == ("primary",)
    assert calendar_id_list("  ") == ("primary",)
    assert calendar_id_list(" primary , house ") == ("primary", "house")

    monkeypatch.setenv("GOOGLE_CALENDAR_IDS", "")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.calendar_ids == ("primary",)
        assert settings.diary_configured is False
    finally:
        get_settings.cache_clear()


def test_calendar_ids_are_not_in_the_settings_repr(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_IDS", "house-calendar,other-calendar")
    get_settings.cache_clear()
    try:
        assert get_settings().calendar_ids == ("house-calendar", "other-calendar")
        text = repr(get_settings())
        assert "house-calendar" not in text
        assert "other-calendar" not in text
    finally:
        get_settings.cache_clear()


def test_home_location_kind_prefers_coordinates_and_hides_values(monkeypatch):
    monkeypatch.setenv("HOUSE_LAT", "")
    monkeypatch.setenv("HOUSE_LON", "")
    monkeypatch.setenv("HOUSE_POSTCODE", "")
    get_settings.cache_clear()
    assert get_settings().home_location_kind is None

    monkeypatch.setenv("HOUSE_POSTCODE", "POSTCODE-PLACEHOLDER")
    get_settings.cache_clear()
    assert get_settings().home_location_kind == "postcode"
    assert get_settings().weather_location_configured is True

    monkeypatch.setenv("HOUSE_LAT", "LAT-PLACEHOLDER")
    monkeypatch.setenv("HOUSE_LON", "LON-PLACEHOLDER")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.home_location_kind == "coordinates"
        text = repr(settings)
        assert "POSTCODE-PLACEHOLDER" not in text
        assert "LAT-PLACEHOLDER" not in text
        assert "LON-PLACEHOLDER" not in text
    finally:
        get_settings.cache_clear()


def test_wembley_maps_to_wembley_park_and_origin_is_home():
    assert COMMUTE_ORIGIN == "home"
    assert WEMBLEY_POINT == "Wembley Park"
    assert commute_point_for_label("Wembley") == "Wembley Park"
    assert commute_point_for_label("  wembley ") == "Wembley Park"
    assert commute_point_for_label("Wembley Park") is None
    assert commute_point_for_label("hotel") is None
    assert commute_point_for_label("") is None
