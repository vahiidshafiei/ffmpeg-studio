"""Trim/cut operation.

params:
    ffmpeg_path: str
    input: str | Path
    output: str | Path
    start: str  (HH:MM:SS or HH:MM:SS.ms or plain seconds)
    end: str | None
    duration: str | None   # used instead of "end" if provided
    mode: "fast" | "accurate"
        fast:     stream copy (-c copy), very quick but cuts only on keyframes
        accurate: re-encodes (-c:v libx264 -c:a aac) so the cut is frame-exact
    overwrite: bool
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.operations.base import Operation
from app.utils.formatting import parse_timecode


class TrimOperation(Operation):
    name = "trim"
    description = "Cut a clip out of a video by start/end time"

    def validate(self, params: dict) -> List[str]:
        errors = []
        if not params.get("input"):
            errors.append("No input file selected.")
        if not params.get("output"):
            errors.append("No output path specified.")
        start = params.get("start")
        if not start:
            errors.append("Start time is required.")
        else:
            try:
                parse_timecode(str(start))
            except ValueError:
                errors.append(f"Invalid start time: {start}")

        end = params.get("end")
        duration = params.get("duration")
        if not end and not duration:
            errors.append("Provide either an end time or a duration.")
        if end:
            try:
                parse_timecode(str(end))
            except ValueError:
                errors.append(f"Invalid end time: {end}")
        if duration:
            try:
                parse_timecode(str(duration))
            except ValueError:
                errors.append(f"Invalid duration: {duration}")

        mode = params.get("mode", "fast")
        if mode not in ("fast", "accurate"):
            errors.append(f"Unknown trim mode: {mode}")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))

        ffmpeg_path = params["ffmpeg_path"]
        input_path = Path(params["input"])
        output_path = Path(params["output"])
        start = str(params["start"])
        end = params.get("end")
        duration = params.get("duration")
        mode = params.get("mode", "fast")
        overwrite = params.get("overwrite", False)

        cmd: List[str] = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]

        # Placing -ss before -i uses ffmpeg's fast input-seeking (keyframe-based
        # for "fast" mode). For "accurate" mode we still seek before -i for
        # speed, then let re-encoding land on the exact frame.
        cmd += ["-ss", start, "-i", str(input_path)]

        if duration:
            cmd += ["-t", str(duration)]
        elif end:
            # -to after -i is measured from the start of the (already-seeked)
            # input in this ffmpeg invocation style; we instead compute an
            # explicit duration to avoid ambiguity between -ss placement rules.
            start_s = parse_timecode(start)
            end_s = parse_timecode(str(end))
            if end_s <= start_s:
                raise ValueError("End time must be after start time.")
            cmd += ["-t", str(round(end_s - start_s, 3))]

        if mode == "fast":
            cmd += ["-c", "copy"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac"]

        cmd += [str(output_path)]
        return cmd
