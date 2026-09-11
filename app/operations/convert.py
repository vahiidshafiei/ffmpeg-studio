"""Video format conversion.

params:
    ffmpeg_path, input, output
    video_codec: "h264" | "h265" | "vp9" | "av1" | "copy"
    audio_codec: "aac" | "mp3" | "opus" | "flac" | "copy"
    quality: "very_high" | "high" | "medium" | "low" | "custom"
        Friendly presets map to a CRF; "custom" requires crf/bitrate/preset
        to be supplied directly.
    crf, preset, bitrate, profile, pixel_format: advanced overrides, all optional
    extra_args: list[str]
    overwrite: bool
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.operations.base import Operation

_VIDEO_ENCODER_MAP = {
    "h264": "libx264",
    "h265": "libx265",
    "vp9": "libvpx-vp9",
    "av1": "libaom-av1",
    "copy": "copy",
}

_AUDIO_ENCODER_MAP = {
    "aac": "aac",
    "mp3": "libmp3lame",
    "opus": "libopus",
    "flac": "flac",
    "copy": "copy",
}

# Friendly quality -> CRF. Lower CRF = higher quality/larger file. These are
# ffmpeg's own documented sane defaults for libx264-family encoders.
_QUALITY_CRF_MAP = {
    "very_high": 18,
    "high": 20,
    "medium": 23,
    "low": 28,
}


class ConvertOperation(Operation):
    name = "convert"
    description = "Convert between video containers/codecs"

    def validate(self, params: dict) -> List[str]:
        errors = []
        if not params.get("input"):
            errors.append("No input file selected.")
        if not params.get("output"):
            errors.append("No output path specified.")
        if params.get("video_codec", "h264") not in _VIDEO_ENCODER_MAP:
            errors.append(f"Unknown video codec: {params.get('video_codec')}")
        if params.get("audio_codec", "aac") not in _AUDIO_ENCODER_MAP:
            errors.append(f"Unknown audio codec: {params.get('audio_codec')}")
        quality = params.get("quality", "medium")
        if quality not in (*_QUALITY_CRF_MAP, "custom"):
            errors.append(f"Unknown quality preset: {quality}")
        if quality == "custom" and params.get("crf") is None and not params.get("bitrate"):
            errors.append("Custom quality requires either a CRF or a bitrate.")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))

        ffmpeg_path = params["ffmpeg_path"]
        input_path = Path(params["input"])
        output_path = Path(params["output"])
        video_codec = params.get("video_codec", "h264")
        audio_codec = params.get("audio_codec", "aac")
        quality = params.get("quality", "medium")
        preset = params.get("preset", "medium")
        pixel_format = params.get("pixel_format")
        profile = params.get("profile")
        extra_args = params.get("extra_args") or []
        overwrite = params.get("overwrite", False)

        cmd: List[str] = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]
        cmd += ["-i", str(input_path)]

        cmd += ["-c:v", _VIDEO_ENCODER_MAP[video_codec]]
        if video_codec != "copy":
            if quality == "custom":
                if params.get("crf") is not None:
                    cmd += ["-crf", str(params["crf"])]
                if params.get("bitrate"):
                    cmd += ["-b:v", str(params["bitrate"])]
            else:
                cmd += ["-crf", str(_QUALITY_CRF_MAP[quality])]
            cmd += ["-preset", preset]
            if profile:
                cmd += ["-profile:v", profile]
            if pixel_format:
                cmd += ["-pix_fmt", pixel_format]

        cmd += ["-c:a", _AUDIO_ENCODER_MAP[audio_codec]]
        if audio_codec != "copy" and params.get("audio_bitrate"):
            cmd += ["-b:a", params["audio_bitrate"]]

        cmd += list(extra_args)
        cmd += [str(output_path)]
        return cmd
