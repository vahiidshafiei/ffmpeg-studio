import pytest

from app.operations.storyboard import StoryboardVideoOperation


def test_storyboard_basic_command(tmp_path):
    op = StoryboardVideoOperation()
    list_file = tmp_path / "list.txt"
    entries = [(str(tmp_path / "a.jpg"), 3.0), (str(tmp_path / "b.jpg"), 5.5)]
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "entries": entries, "audio_path": str(tmp_path / "voice.mp3"),
        "output": str(tmp_path / "out.mp4"), "list_file_path": str(list_file),
        "fps": 30, "resolution": (1920, 1080), "fit_mode": "fit",
    })
    content = list_file.read_text()
    assert "a.jpg" in content and "duration 3.0" in content
    assert "b.jpg" in content and "duration 5.5" in content
    # last image repeated without a trailing duration line (ffmpeg concat quirk)
    assert content.count("b.jpg") == 2
    assert "-shortest" in cmd
    assert any("voice.mp3" in part for part in cmd)


def test_storyboard_two_images_one_audio_matches_two_to_one():
    op = StoryboardVideoOperation()
    entries = [("img1.jpg", 4.0), ("img2.jpg", 6.0)]
    errors = op.validate({
        "entries": entries, "audio_path": "a.mp3", "output": "out.mp4", "list_file_path": "l.txt",
    })
    assert errors == []


def test_storyboard_rejects_zero_or_negative_duration():
    op = StoryboardVideoOperation()
    errors = op.validate({
        "entries": [("img1.jpg", 0)], "audio_path": "a.mp3", "output": "out.mp4", "list_file_path": "l.txt",
    })
    assert any("non-positive duration" in e for e in errors)


def test_storyboard_requires_audio():
    op = StoryboardVideoOperation()
    with pytest.raises(ValueError):
        op.build_command({
            "entries": [("img1.jpg", 3.0)], "output": "out.mp4", "list_file_path": "l.txt",
            "ffmpeg_path": "ffmpeg",
        })


def test_storyboard_requires_at_least_one_entry():
    op = StoryboardVideoOperation()
    errors = op.validate({
        "entries": [], "audio_path": "a.mp3", "output": "out.mp4", "list_file_path": "l.txt",
    })
    assert any("at least one image" in e for e in errors)


def test_storyboard_audio_copy_mode(tmp_path):
    op = StoryboardVideoOperation()
    list_file = tmp_path / "list.txt"
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "entries": [(str(tmp_path / "a.jpg"), 3.0)],
        "audio_path": str(tmp_path / "voice.mp3"), "output": str(tmp_path / "out.mp4"),
        "list_file_path": str(list_file), "audio_codec": "copy",
    })
    ca_index = cmd.index("-c:a")
    assert cmd[ca_index + 1] == "copy"
    # video is still freshly encoded from images regardless of audio_codec
    assert "libx264" in cmd


def test_storyboard_audio_default_is_aac(tmp_path):
    op = StoryboardVideoOperation()
    list_file = tmp_path / "list.txt"
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "entries": [(str(tmp_path / "a.jpg"), 3.0)],
        "audio_path": str(tmp_path / "voice.mp3"), "output": str(tmp_path / "out.mp4"),
        "list_file_path": str(list_file),
    })
    ca_index = cmd.index("-c:a")
    assert cmd[ca_index + 1] == "aac"
