import pytest

from app.operations.convert import ConvertOperation


def test_convert_friendly_quality_maps_to_crf():
    op = ConvertOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "in.mov", "output": "out.mp4",
        "video_codec": "h264", "audio_codec": "aac", "quality": "high", "preset": "medium",
    })
    crf_index = cmd.index("-crf")
    assert cmd[crf_index + 1] == "20"


def test_convert_custom_quality_uses_explicit_crf():
    op = ConvertOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "in.mov", "output": "out.mp4",
        "video_codec": "h265", "audio_codec": "flac", "quality": "custom", "crf": 30, "preset": "slow",
    })
    crf_index = cmd.index("-crf")
    assert cmd[crf_index + 1] == "30"
    assert "libx265" in cmd


def test_convert_copy_codec_skips_quality_args():
    op = ConvertOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "in.mov", "output": "out.mkv",
        "video_codec": "copy", "audio_codec": "copy", "quality": "medium",
    })
    assert "-crf" not in cmd
    assert "-preset" not in cmd
    assert cmd.count("copy") == 2


def test_convert_custom_without_crf_or_bitrate_rejected():
    op = ConvertOperation()
    with pytest.raises(ValueError):
        op.build_command({
            "ffmpeg_path": "ffmpeg", "input": "in.mov", "output": "out.mp4",
            "video_codec": "h264", "audio_codec": "aac", "quality": "custom",
        })
