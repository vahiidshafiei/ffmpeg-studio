import pytest

from app.utils.formatting import parse_timecode, format_duration, format_size


def test_parse_timecode_hms():
    assert parse_timecode("00:02:30") == 150.0


def test_parse_timecode_hms_with_ms():
    assert parse_timecode("00:00:01.500") == pytest.approx(1.5)


def test_parse_timecode_plain_seconds():
    assert parse_timecode("90") == 90.0


def test_parse_timecode_rejects_bad_input():
    with pytest.raises(ValueError):
        parse_timecode("not-a-time")
    with pytest.raises(ValueError):
        parse_timecode("00:99:00")


def test_format_duration_roundtrip():
    assert format_duration(150) == "00:02:30"


def test_format_size():
    assert format_size(1500) == "1.46 KB"
    assert format_size(500) == "500 B"
