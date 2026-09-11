from app.operations.shorts import ShortsOperation


def test_shorts_crop_mode_default_resolution():
    op = ShortsOperation()
    cmd = op.build_command({"ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4", "mode": "crop"})
    vf = cmd[cmd.index("-vf") + 1]
    assert "1080:1920" in vf
    assert "crop=1080:1920" in vf


def test_shorts_fit_mode_pads():
    op = ShortsOperation()
    cmd = op.build_command({"ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4", "mode": "fit"})
    vf = cmd[cmd.index("-vf") + 1]
    assert "pad=1080:1920" in vf


def test_shorts_blur_mode_uses_split_and_overlay():
    op = ShortsOperation()
    cmd = op.build_command({"ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4", "mode": "blur"})
    vf = cmd[cmd.index("-vf") + 1]
    assert "split=2" in vf and "overlay" in vf and "gblur" in vf


def test_shorts_custom_resolution():
    op = ShortsOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4",
        "mode": "custom", "width": 720, "height": 1280,
    })
    vf = cmd[cmd.index("-vf") + 1]
    assert "720:1280" in vf


def test_shorts_audio_copy_skips_bitrate():
    op = ShortsOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4",
        "mode": "crop", "audio_codec": "copy",
    })
    ca_index = cmd.index("-c:a")
    assert cmd[ca_index + 1] == "copy"
    assert "-b:a" not in cmd
    # video is still re-encoded regardless of audio_codec
    assert "-crf" in cmd


def test_shorts_audio_aac_default_keeps_bitrate():
    op = ShortsOperation()
    cmd = op.build_command({"ffmpeg_path": "ffmpeg", "input": "in.mp4", "output": "out.mp4", "mode": "crop"})
    ca_index = cmd.index("-c:a")
    assert cmd[ca_index + 1] == "aac"
    assert "-b:a" in cmd
