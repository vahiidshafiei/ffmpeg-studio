"""Convert landscape video to vertical (YouTube Shorts / 9:16) format.

params:
    ffmpeg_path, input, output
    mode: "crop" | "fit" | "blur" | "custom"
        crop:   scale to fill the vertical frame, cropping the overflow
        fit:    scale to fit within the frame, padding with black bars
        blur:   original video centered over a blurred, enlarged copy of itself
        custom: caller supplies width/height directly, crop-style fill
    width, height: only used when mode == "custom" (default 1080x1920)
    fps: int (default 30)
    codec: "h264" | "h265" (default h264)
    crf: int (default 23)
    audio_codec: "aac" | "copy" (default "aac") — "copy" stream-copies the
        original audio track untouched. Valid here even though the video is
        always re-encoded (the crop/scale/blur transform only ever touches
        -vf, never the audio stream), so skipping audio re-encoding is free
        speed with zero quality loss.
    audio_bitrate: str (default "192k"), ignored when audio_codec == "copy"
    overwrite: bool
"""
from __future__ import annotations

from typing import List

from app.operations.base import Operation

_CODEC_MAP = {"h264": "libx264", "h265": "libx265"}

_TARGET_W, _TARGET_H = 1080, 1920


class ShortsOperation(Operation):
    name = "shorts"
    description = "Convert landscape video to vertical (9:16) for Shorts/Reels/TikTok"

    def validate(self, params: dict) -> List[str]:
        errors = []
        if not params.get("input"):
            errors.append("No input file selected.")
        if not params.get("output"):
            errors.append("No output path specified.")
        mode = params.get("mode", "crop")
        if mode not in ("crop", "fit", "blur", "custom"):
            errors.append(f"Unknown mode: {mode}")
        if params.get("codec", "h264") not in _CODEC_MAP:
            errors.append(f"Unknown codec: {params.get('codec')}")
        audio_codec = params.get("audio_codec", "aac")
        if audio_codec not in ("aac", "copy"):
            errors.append(f"Unknown audio_codec: {audio_codec}")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))

        ffmpeg_path = params["ffmpeg_path"]
        input_path = params["input"]
        output_path = params["output"]
        mode = params.get("mode", "crop")
        width = params.get("width", _TARGET_W)
        height = params.get("height", _TARGET_H)
        fps = params.get("fps", 30)
        codec = params.get("codec", "h264")
        crf = params.get("crf", 23)
        audio_codec = params.get("audio_codec", "aac")
        audio_bitrate = params.get("audio_bitrate", "192k")
        overwrite = params.get("overwrite", False)

        if mode in ("crop", "custom"):
            vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
        elif mode == "fit":
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
            )
        else:  # blur
            # Background: enlarge + blur the source to fill the frame.
            # Foreground: scale the source to fit, centered on top.
            vf = (
                f"split=2[bg][fg];"
                f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},gblur=sigma=20[bg];"
                f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
            )

        cmd = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]
        cmd += ["-i", str(input_path)]
        cmd += ["-vf", vf, "-r", str(fps)]
        cmd += ["-c:v", _CODEC_MAP[codec], "-crf", str(crf), "-preset", "medium"]
        if audio_codec == "copy":
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", "aac", "-b:a", audio_bitrate]
        cmd += [str(output_path)]
        return cmd
