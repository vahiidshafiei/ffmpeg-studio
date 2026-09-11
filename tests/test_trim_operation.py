import pytest

from app.operations.trim import TrimOperation


def test_trim_with_duration_fast_mode():
    op = TrimOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4",
        "start": "00:02:30", "duration": "00:01:00", "mode": "fast",
    })
    assert "-ss" in cmd and "00:02:30" in cmd
    assert "-t" in cmd and "00:01:00" in cmd
    assert "-c" in cmd and "copy" in cmd


def test_trim_with_end_time_computes_duration():
    op = TrimOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4",
        "start": "00:00:10", "end": "00:00:40", "mode": "accurate",
    })
    t_index = cmd.index("-t")
    assert cmd[t_index + 1] == "30.0"
    assert "libx264" in cmd


def test_trim_rejects_end_before_start():
    op = TrimOperation()
    with pytest.raises(ValueError):
        op.build_command({
            "ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4",
            "start": "00:00:40", "end": "00:00:10", "mode": "fast",
        })


def test_trim_requires_end_or_duration():
    errors = TrimOperation().validate({
        "ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4",
        "start": "00:00:10",
    })
    assert any("end time or a duration" in e for e in errors)
