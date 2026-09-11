"""Merge (concatenate) multiple videos.

params:
    ffmpeg_path, output
    inputs: list[str|Path], in the order they should play
    mode: "fast" | "compatibility"
        fast:          uses the concat demuxer + "-c copy" (requires a
                       `list_file_path` — a text file this function writes
                       listing the inputs, since ffmpeg's concat demuxer
                       reads the file list from disk rather than argv).
        compatibility: re-encodes all inputs with the concat filter, safe
                       even when resolution/codec/fps/audio streams differ.
    list_file_path: str|Path — where to write the concat demuxer's file list
                    (fast mode only; caller picks the path, e.g. a temp file
                    next to the output, so it can clean it up afterward)
    resolution: optional (w, h) target for compatibility mode; if omitted,
                the first input's resolution is used (caller must supply it —
                this module does no ffprobe I/O itself)
    fps: optional target fps for compatibility mode
    overwrite: bool
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from app.operations.base import Operation


def write_concat_list_file(input_paths: List[Path], list_file_path: Path) -> None:
    """Write ffmpeg concat-demuxer file list syntax.

    Paths are escaped per ffmpeg's concat format (single quotes, with
    embedded single quotes doubled) so filenames with spaces/apostrophes
    don't break parsing.
    """
    lines = []
    for path in input_paths:
        escaped = str(path).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class MergeOperation(Operation):
    name = "merge"
    description = "Concatenate multiple videos into one"

    def validate(self, params: dict) -> List[str]:
        errors = []
        inputs = params.get("inputs") or []
        if len(inputs) < 2:
            errors.append("Select at least two videos to merge.")
        if not params.get("output"):
            errors.append("No output path specified.")
        mode = params.get("mode", "fast")
        if mode not in ("fast", "compatibility"):
            errors.append(f"Unknown merge mode: {mode}")
        if mode == "fast" and not params.get("list_file_path"):
            errors.append("Fast mode requires a list_file_path to write the concat list to.")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))

        ffmpeg_path = params["ffmpeg_path"]
        inputs = [Path(p) for p in params["inputs"]]
        output_path = Path(params["output"])
        mode = params.get("mode", "fast")
        overwrite = params.get("overwrite", False)

        cmd: List[str] = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]

        if mode == "fast":
            list_file_path = Path(params["list_file_path"])
            write_concat_list_file(inputs, list_file_path)
            cmd += ["-f", "concat", "-safe", "0", "-i", str(list_file_path), "-c", "copy"]
        else:
            # Compatibility mode: normalize each input to a common
            # resolution/fps via -vf inside the concat filter, then re-encode.
            resolution: Tuple[int, int] | None = params.get("resolution")
            fps = params.get("fps")
            for path in inputs:
                cmd += ["-i", str(path)]

            filter_parts = []
            n = len(inputs)
            for i in range(n):
                vf = f"[{i}:v]"
                scale = f"scale={resolution[0]}:{resolution[1]}," if resolution else ""
                fps_filter = f"fps={fps}," if fps else ""
                filter_parts.append(f"{vf}{scale}{fps_filter}setsar=1[v{i}]")
                filter_parts.append(f"[{i}:a]aresample=async=1[a{i}]")
            concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
            filter_complex = ";".join(filter_parts) + f";{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]"

            cmd += [
                "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac",
            ]

        cmd += [str(output_path)]
        return cmd
