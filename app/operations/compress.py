"""Video compression operation.

params:
    ffmpeg_path: str
    input: str | Path
    output: str | Path
    codec: "h264" | "h265" | "av1"
    crf: int
    preset: "ultrafast".."veryslow"
    resolution: None | "2160p" | "1440p" | "1080p" | "720p" | "480p" | (w, h)
    audio_mode: "copy" | "aac" | "mp3" | "opus"
    audio_bitrate: str, e.g. "192k" (ignored if audio_mode == "copy")
    extra_args: list[str] (advanced/custom ffmpeg arguments, appended before output)
    overwrite: bool
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.operations.base import Operation

_CODEC_MAP = {
    "h264": "libx264",
    "h265": "libx265",
    "av1": "libaom-av1",
}

_RESOLUTION_HEIGHTS = {
    "2160p": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
}

_VALID_PRESETS = {
    "ultrafast", "superfast", "veryfast", "faster", "fast",
    "medium", "slow", "slower", "veryslow",
}

_AUDIO_ENCODER_MAP = {
    "aac": "aac",
    "mp3": "libmp3lame",
    "opus": "libopus",
}


class CompressOperation(Operation):
    name = "compress"
    description = "Reduce file size while balancing quality"

    def validate(self, params: dict) -> List[str]:
        errors = []
        if not params.get("input"):
            errors.append("No input file selected.")
        if not params.get("output"):
            errors.append("No output path specified.")
        codec = params.get("codec", "h264")
        if codec not in _CODEC_MAP:
            errors.append(f"Unknown codec: {codec}")
        crf = params.get("crf", 23)
        if not isinstance(crf, int) or not (0 <= crf <= 51):
            errors.append("CRF must be an integer between 0 and 51.")
        preset = params.get("preset", "medium")
        if preset not in _VALID_PRESETS:
            errors.append(f"Unknown preset: {preset}")
        resolution = params.get("resolution")
        if resolution and isinstance(resolution, str) and resolution not in _RESOLUTION_HEIGHTS:
            errors.append(f"Unknown resolution preset: {resolution}")
        audio_mode = params.get("audio_mode", "copy")
        if audio_mode not in ("copy", *_AUDIO_ENCODER_MAP):
            errors.append(f"Unknown audio mode: {audio_mode}")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))

        ffmpeg_path = params["ffmpeg_path"]
        input_path = Path(params["input"])
        output_path = Path(params["output"])
        codec = params.get("codec", "h264")
        crf = params.get("crf", 23)
        preset = params.get("preset", "medium")
        resolution = params.get("resolution")
        audio_mode = params.get("audio_mode", "copy")
        audio_bitrate = params.get("audio_bitrate", "192k")
        extra_args = params.get("extra_args") or []
        overwrite = params.get("overwrite", False)

        cmd: List[str] = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]
        cmd += ["-i", str(input_path)]

        cmd += ["-c:v", _CODEC_MAP[codec], "-crf", str(crf), "-preset", preset]

        if resolution:
            if isinstance(resolution, tuple):
                w, h = resolution
                cmd += ["-vf", f"scale={w}:{h}"]
            elif resolution in _RESOLUTION_HEIGHTS:
                # Scale by height, preserve aspect ratio, force even dimensions
                # (required by most video codecs).
                height = _RESOLUTION_HEIGHTS[resolution]
                cmd += ["-vf", f"scale=-2:{height}"]

        if audio_mode == "copy":
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", _AUDIO_ENCODER_MAP[audio_mode], "-b:a", audio_bitrate]

        cmd += list(extra_args)
        cmd += [str(output_path)]
        return cmd
