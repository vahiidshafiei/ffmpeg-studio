"""Audio operations: extract from video, convert format, merge many files.

Three separate command builders since each has a genuinely different ffmpeg
shape, but they share one module because they're presented as tabs on one
Audio page.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.operations.base import Operation
from app.operations.merge import write_concat_list_file

_AUDIO_ENCODER_MAP = {
    "mp3": "libmp3lame",
    "aac": "aac",
    "wav": "pcm_s16le",
    "flac": "flac",
    "opus": "libopus",
}


class ExtractAudioOperation(Operation):
    """Video -> audio-only file."""
    name = "extract_audio"
    description = "Extract the audio track from a video"

    def validate(self, params: dict) -> List[str]:
        errors = []
        if not params.get("input"):
            errors.append("No input file selected.")
        if not params.get("output"):
            errors.append("No output path specified.")
        fmt = params.get("format", "mp3")
        if fmt != "copy" and fmt not in _AUDIO_ENCODER_MAP:
            errors.append(f"Unknown audio format: {fmt}")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))
        ffmpeg_path = params["ffmpeg_path"]
        overwrite = params.get("overwrite", False)
        fmt = params.get("format", "mp3")

        cmd = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]
        # "copy" pulls the audio stream out byte-for-byte with no re-encoding
        # — fastest and lossless, but keeps whatever codec the source has
        # (which is why the page forces a .mka output — see audio_page.py —
        # a container that can hold essentially any audio codec).
        encoder = "copy" if fmt == "copy" else _AUDIO_ENCODER_MAP[fmt]
        cmd += ["-i", str(params["input"]), "-vn", "-c:a", encoder]
        if fmt != "copy" and params.get("bitrate") and fmt not in ("wav", "flac"):
            cmd += ["-b:a", params["bitrate"]]
        cmd += [str(params["output"])]
        return cmd


class ConvertAudioOperation(Operation):
    """Audio -> audio, changing format/bitrate/sample rate."""
    name = "convert_audio"
    description = "Convert an audio file's format, bitrate, or sample rate"

    def validate(self, params: dict) -> List[str]:
        errors = []
        if not params.get("input"):
            errors.append("No input file selected.")
        if not params.get("output"):
            errors.append("No output path specified.")
        fmt = params.get("format", "mp3")
        if fmt != "copy" and fmt not in _AUDIO_ENCODER_MAP:
            errors.append(f"Unknown audio format: {fmt}")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))
        ffmpeg_path = params["ffmpeg_path"]
        overwrite = params.get("overwrite", False)
        fmt = params.get("format", "mp3")

        cmd = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]
        # Same rationale as ExtractAudioOperation: "copy" remuxes without
        # touching the audio at all, so bitrate/sample_rate (which require
        # re-encoding) are meaningless and skipped in that case.
        encoder = "copy" if fmt == "copy" else _AUDIO_ENCODER_MAP[fmt]
        cmd += ["-i", str(params["input"]), "-c:a", encoder]
        if fmt != "copy":
            if params.get("bitrate") and fmt not in ("wav", "flac"):
                cmd += ["-b:a", params["bitrate"]]
            if params.get("sample_rate"):
                cmd += ["-ar", str(params["sample_rate"])]
        cmd += [str(params["output"])]
        return cmd


class MergeAudioOperation(Operation):
    """Concatenate many audio files, in natural-sorted (or manually reordered) order."""
    name = "merge_audio"
    description = "Merge multiple audio files into one, in order"

    def validate(self, params: dict) -> List[str]:
        errors = []
        inputs = params.get("inputs") or []
        if len(inputs) < 2:
            errors.append("Select at least two audio files to merge.")
        if not params.get("output"):
            errors.append("No output path specified.")
        if not params.get("list_file_path"):
            errors.append("A list_file_path is required to write the concat list to.")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))
        ffmpeg_path = params["ffmpeg_path"]
        inputs = [Path(p) for p in params["inputs"]]
        list_file_path = Path(params["list_file_path"])
        overwrite = params.get("overwrite", False)

        write_concat_list_file(inputs, list_file_path)

        cmd = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]
        cmd += ["-f", "concat", "-safe", "0", "-i", str(list_file_path), "-c", "copy"]
        cmd += [str(params["output"])]
        return cmd
