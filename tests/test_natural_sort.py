from pathlib import Path

from app.utils.natural_sort import natural_sort_key, natural_sorted_paths, natural_sorted_strings


def test_natural_sort_numeric_order():
    values = ["10.mp3", "2.mp3", "1.mp3", "11.mp3", "3.mp3"]
    assert natural_sorted_strings(values) == ["1.mp3", "2.mp3", "3.mp3", "10.mp3", "11.mp3"]


def test_natural_sort_paths():
    paths = [Path(p) for p in ["track10.mp3", "track2.mp3", "track1.mp3"]]
    result = [p.name for p in natural_sorted_paths(paths)]
    assert result == ["track1.mp3", "track2.mp3", "track10.mp3"]


def test_natural_sort_mixed_prefixes():
    values = ["Lecture1.mp4", "Lecture10.mp4", "Lecture2.mp4"]
    assert natural_sorted_strings(values) == ["Lecture1.mp4", "Lecture2.mp4", "Lecture10.mp4"]


def test_natural_sort_key_is_stable_for_pure_text():
    assert natural_sort_key("abc") < natural_sort_key("abd")
