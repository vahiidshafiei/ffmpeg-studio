import pytest

from app.operations.video_audio import VideoAudioOperation


def test_replace_audio_maps_second_input():
    op = VideoAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "video_input": "v.mp4", "audio_input": "a.mp3",
        "output": "out.mp4", "mode": "replace",
    })
    assert cmd.count("-map") == 2
    assert "1:a" in cmd
    assert "-shortest" in cmd


def test_add_audio_uses_amix_filter():
    op = VideoAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "video_input": "v.mp4", "audio_input": "a.mp3",
        "output": "out.mp4", "mode": "add",
    })
    assert "-filter_complex" in cmd
    assert "amix" in cmd[cmd.index("-filter_complex") + 1]


def test_remove_audio_strips_track():
    op = VideoAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "video_input": "v.mp4", "output": "out.mp4", "mode": "remove",
    })
    assert "-an" in cmd
    assert "-map" not in cmd  # simple copy path, no explicit mapping needed


def test_loop_audio_policy_adds_stream_loop():
    op = VideoAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "video_input": "v.mp4", "audio_input": "a.mp3",
        "output": "out.mp4", "mode": "replace", "duration_policy": "loop_audio",
    })
    assert "-stream_loop" in cmd


def test_replace_mode_audio_encode_copy():
    op = VideoAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "video_input": "v.mp4", "audio_input": "a.mp3",
        "output": "out.mp4", "mode": "replace", "audio_encode": "copy",
    })
    ca_index = cmd.index("-c:a")
    assert cmd[ca_index + 1] == "copy"
    assert cmd[cmd.index("-c:v") + 1] == "copy"  # video is always copy regardless


def test_add_mode_ignores_audio_encode_copy_since_filter_requires_reencode():
    op = VideoAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "video_input": "v.mp4", "audio_input": "a.mp3",
        "output": "out.mp4", "mode": "add", "audio_encode": "copy",
    })
    ca_index = cmd.index("-c:a")
    assert cmd[ca_index + 1] == "aac"  # amix output can't be stream-copied


def test_replace_mode_without_audio_input_rejected():
    op = VideoAudioOperation()
    with pytest.raises(ValueError):
        op.build_command({"ffmpeg_path": "ffmpeg", "video_input": "v.mp4", "output": "out.mp4", "mode": "replace"})
