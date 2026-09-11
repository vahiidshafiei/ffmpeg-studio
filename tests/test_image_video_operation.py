from app.operations.image_video import ImagesToVideoOperation, write_image_list_file
from pathlib import Path


def test_images_to_video_basic_command(tmp_path):
    op = ImagesToVideoOperation()
    list_file = tmp_path / "images.txt"
    images = [str(tmp_path / f"img{i}.jpg") for i in range(1, 4)]
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "images": images, "output": str(tmp_path / "out.mp4"),
        "list_file_path": str(list_file), "seconds_per_image": 3, "fps": 25,
        "resolution": (1920, 1080), "fit_mode": "fit",
    })
    assert list_file.exists()
    assert "-vf" in cmd
    assert "fps=25" in cmd[cmd.index("-vf") + 1]
    assert "-c:v" in cmd and "libx264" in cmd


def test_images_to_video_with_audio_adds_shortest():
    op = ImagesToVideoOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "images": ["a.jpg", "b.jpg"], "output": "out.mp4",
        "list_file_path": "list.txt", "audio_path": "music.mp3",
    })
    assert "-shortest" in cmd
    assert "music.mp3" in cmd


def test_write_image_list_file_repeats_last_image(tmp_path):
    list_file = tmp_path / "list.txt"
    images = [Path("a.jpg"), Path("b.jpg")]
    write_image_list_file(images, 5.0, list_file)
    content = list_file.read_text()
    assert content.count("b.jpg") == 2  # once with duration, once repeated
    assert content.count("a.jpg") == 1


def test_images_to_video_rejects_empty_list():
    op = ImagesToVideoOperation()
    errors = op.validate({"images": [], "output": "out.mp4", "list_file_path": "l.txt"})
    assert any("at least one image" in e for e in errors)
