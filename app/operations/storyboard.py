"""Build a video from ONE audio track plus a sequence of images, each shown
for an explicit [start, end) time window (in seconds, relative to that
video's own timeline — i.e. the first image typically starts at 0).

This is the per-audio building block behind the Storyboard page: a user with
10 audios and 15 images assigns images (with explicit timing) to each audio,
this operation renders each audio's video, and MergeOperation then combines
the resulting videos in whatever order the user picks.

Unlike ImagesToVideoOperation (uniform seconds-per-image), this takes
explicit per-image durations computed by the caller from (end - start), so
"2 images on this audio, 1 image on that one" and irregular timings are both
just different duration lists — no special-casing needed here.

params:
    ffmpeg_path, output
    entries: list of (image_path: str, duration_seconds: float), already
             sorted in display order — the caller (page) is responsible for
             sorting by start time and validating that intervals don't
             overlap or leave gaps, since only the page has the raw
             start/end values to give a good error message about which
             interval is wrong.
    audio_path: str|Path — required; this operation always attaches audio
    list_file_path: str|Path — where to write the concat list
    fps: int (default 30)
    resolution: (w, h) (default 1920x1080)
    fit_mode: "fit" | "crop" | "stretch" | "pad" (default "fit")
    audio_codec: "aac" | "copy" (default "aac") — the video track always has
        to be freshly encoded (it's built from a sequence of images, there's
        no "original" to copy), but the audio being attached doesn't need
        touching at all — "copy" stream-copies it as-is for a faster render
        with zero re-encoding loss on the audio.
    overwrite: bool
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from app.operations.base import Operation
from app.operations.image_video import _FIT_FILTERS


class StoryboardVideoOperation(Operation):
    name = "storyboard_video"
    description = "Build a video from one audio track and a timed sequence of images"

    def validate(self, params: dict) -> List[str]:
        errors = []
        entries = params.get("entries") or []
        if not entries:
            errors.append("Assign at least one image to this audio.")
        for image_path, duration in entries:
            if duration is None or duration <= 0:
                errors.append(f"'{Path(image_path).name}' has a non-positive duration ({duration}).")
        if not params.get("audio_path"):
            errors.append("An audio file is required.")
        if not params.get("output"):
            errors.append("No output path specified.")
        if not params.get("list_file_path"):
            errors.append("A list_file_path is required to write the image list to.")
        fit_mode = params.get("fit_mode", "fit")
        if fit_mode not in _FIT_FILTERS:
            errors.append(f"Unknown fit mode: {fit_mode}")
        audio_codec = params.get("audio_codec", "aac")
        if audio_codec not in ("aac", "copy"):
            errors.append(f"Unknown audio_codec: {audio_codec}")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))

        ffmpeg_path = params["ffmpeg_path"]
        entries: List[Tuple[str, float]] = params["entries"]
        list_file_path = Path(params["list_file_path"])
        audio_path = params["audio_path"]
        fps = params.get("fps", 30)
        resolution = params.get("resolution", (1920, 1080))
        fit_mode = params.get("fit_mode", "fit")
        audio_codec = params.get("audio_codec", "aac")
        overwrite = params.get("overwrite", False)
        output_path = Path(params["output"])

        # Per-image durations aren't uniform here, so the concat list is
        # written directly rather than via image_video's uniform-duration helper.
        lines = []
        for image_path, duration in entries:
            escaped = str(image_path).replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
            lines.append(f"duration {duration}")
        if entries:
            escaped = str(entries[-1][0]).replace("'", "'\\''")
            lines.append(f"file '{escaped}'")  # required repeat — ffmpeg concat quirk
        list_file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        w, h = resolution
        vf = _FIT_FILTERS[fit_mode].format(w=w, h=h)

        cmd = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]
        cmd += ["-f", "concat", "-safe", "0", "-i", str(list_file_path)]
        cmd += ["-i", str(audio_path)]
        cmd += ["-vf", f"{vf},fps={fps}", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        cmd += ["-c:a", audio_codec, "-shortest"]
        cmd += [str(output_path)]
        return cmd
