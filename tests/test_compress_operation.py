import pytest

from app.operations.compress import CompressOperation


def test_compress_basic_command():
    op = CompressOperation()
    params = {
        "ffmpeg_path": "ffmpeg",
        "input": "input.mp4",
        "output": "output.mp4",
        "codec": "h264",
        "crf": 23,
        "preset": "medium",
        "resolution": None,
        "audio_mode": "aac",
        "audio_bitrate": "192k",
        "overwrite": False,
    }
    cmd = op.build_command(params)
    assert cmd[0] == "ffmpeg"
    assert "-n" in cmd
    assert "-i" in cmd and "input.mp4" in cmd
    assert "-c:v" in cmd and "libx264" in cmd
    assert "-crf" in cmd and "23" in cmd
    assert "-c:a" in cmd and "aac" in cmd
    assert "-b:a" in cmd and "192k" in cmd
    assert cmd[-1] == "output.mp4"


def test_compress_audio_copy_omits_bitrate():
    op = CompressOperation()
    params = {
        "ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4",
        "codec": "h265", "crf": 28, "preset": "fast", "resolution": "1080p",
        "audio_mode": "copy", "overwrite": True,
    }
    cmd = op.build_command(params)
    assert "-y" in cmd
    assert "-c:a" in cmd and "copy" in cmd
    assert "-b:a" not in cmd
    assert any("scale=-2:1080" in part for part in cmd)


def test_compress_rejects_bad_crf():
    op = CompressOperation()
    params = {
        "ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4",
        "codec": "h264", "crf": 999, "preset": "medium",
    }
    with pytest.raises(ValueError):
        op.build_command(params)


def test_compress_rejects_unknown_codec():
    op = CompressOperation()
    errors = CompressOperation().validate({
        "ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4",
        "codec": "vp9000", "crf": 23, "preset": "medium",
    })
    assert any("codec" in e.lower() for e in errors)
