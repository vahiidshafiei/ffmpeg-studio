import pytest
from pathlib import Path

from app.operations.merge import MergeOperation, write_concat_list_file


def test_merge_fast_mode_writes_concat_list(tmp_path):
    op = MergeOperation()
    list_file = tmp_path / "list.txt"
    inputs = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg",
        "inputs": [str(p) for p in inputs],
        "output": str(tmp_path / "out.mp4"),
        "mode": "fast",
        "list_file_path": str(list_file),
    })
    assert list_file.exists()
    content = list_file.read_text()
    assert "a.mp4" in content and "b.mp4" in content
    assert "-f" in cmd and "concat" in cmd
    assert "-c" in cmd and "copy" in cmd


def test_merge_compatibility_mode_builds_filter_complex():
    op = MergeOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg",
        "inputs": ["a.mp4", "b.mp4", "c.mp4"],
        "output": "out.mp4",
        "mode": "compatibility",
        "resolution": (1280, 720),
        "fps": 30,
    })
    assert "-filter_complex" in cmd
    fc_index = cmd.index("-filter_complex")
    filter_str = cmd[fc_index + 1]
    assert "concat=n=3:v=1:a=1" in filter_str
    assert "scale=1280:720" in filter_str
    assert cmd.count("-i") == 3


def test_merge_requires_at_least_two_inputs():
    op = MergeOperation()
    errors = op.validate({"inputs": ["only_one.mp4"], "output": "out.mp4", "mode": "fast", "list_file_path": "x.txt"})
    assert any("at least two" in e for e in errors)


def test_write_concat_list_file_escapes_quotes(tmp_path):
    list_file = tmp_path / "list.txt"
    write_concat_list_file([Path("it's a file.mp4")], list_file)
    content = list_file.read_text()
    assert "it'\\''s a file.mp4" in content
