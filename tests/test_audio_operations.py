import pytest

from app.operations.audio import ExtractAudioOperation, ConvertAudioOperation, MergeAudioOperation


def test_extract_audio_basic():
    op = ExtractAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "video.mp4", "output": "audio.mp3", "format": "mp3", "bitrate": "192k",
    })
    assert "-vn" in cmd
    assert "-c:a" in cmd and "libmp3lame" in cmd
    assert "-b:a" in cmd and "192k" in cmd


def test_extract_audio_wav_skips_bitrate():
    op = ExtractAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "video.mp4", "output": "audio.wav", "format": "wav", "bitrate": "192k",
    })
    assert "-b:a" not in cmd
    assert "pcm_s16le" in cmd


def test_extract_audio_copy_mode_no_reencode():
    op = ExtractAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "video.mp4", "output": "audio.mka", "format": "copy",
    })
    ca_index = cmd.index("-c:a")
    assert cmd[ca_index + 1] == "copy"
    assert "-b:a" not in cmd


def test_convert_audio_sets_sample_rate():
    op = ConvertAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "in.wav", "output": "out.aac",
        "format": "aac", "bitrate": "128k", "sample_rate": 44100,
    })
    assert "-ar" in cmd and "44100" in cmd


def test_convert_audio_copy_mode_skips_bitrate_and_sample_rate():
    op = ConvertAudioOperation()
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "input": "in.wav", "output": "out.mka",
        "format": "copy", "bitrate": "128k", "sample_rate": 44100,
    })
    ca_index = cmd.index("-c:a")
    assert cmd[ca_index + 1] == "copy"
    assert "-ar" not in cmd
    assert "-b:a" not in cmd


def test_merge_audio_natural_order_list(tmp_path):
    op = MergeAudioOperation()
    list_file = tmp_path / "list.txt"
    files = [str(tmp_path / f"{i}.mp3") for i in [1, 2, 10]]
    cmd = op.build_command({
        "ffmpeg_path": "ffmpeg", "inputs": files, "output": str(tmp_path / "merged.mp3"),
        "list_file_path": str(list_file),
    })
    content = list_file.read_text()
    # order in the list file should match the order passed in (caller is
    # responsible for natural-sorting before calling build_command)
    assert content.index("1.mp3") < content.index("2.mp3") < content.index("10.mp3")
    assert "-f" in cmd and "concat" in cmd


def test_merge_audio_requires_two_files():
    op = MergeAudioOperation()
    errors = op.validate({"inputs": ["one.mp3"], "output": "out.mp3", "list_file_path": "x.txt"})
    assert any("at least two" in e for e in errors)
