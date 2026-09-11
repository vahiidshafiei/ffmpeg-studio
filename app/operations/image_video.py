"""Build a video from a sequence of images (+ optional audio).

Uses the concat demuxer with per-image `duration` directives rather than
`-framerate`+glob, because that approach requires images to already be
consecutively numbered with no gaps — the concat list works with any
filenames/order the user (or natural sort) has already established.

ffmpeg quirk: the concat demuxer ignores the `duration` on the *last* listed
image, so the list must repeat the final image once more without a duration
directive to make its display time apply. `write_image_list_file` handles this.

params:
    ffmpeg_path, output
    images: list[str|Path], in display order
    list_file_path: str|Path — where to write the concat list
    seconds_per_image: float
    fps: int
    resolution: (w, h)
    fit_mode: "fit" | "crop" | "stretch" | "pad"
    audio_path: str|Path | None
    overwrite: bool
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.operations.base import Operation


def write_image_list_file(image_paths: List[Path], seconds_per_image: float, list_file_path: Path) -> None:
    lines = []
    for path in image_paths:
        escaped = str(path).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
        lines.append(f"duration {seconds_per_image}")
    if image_paths:
        # Repeat the last image without a duration line — required by the
        # concat demuxer, which otherwise drops the final image's display time.
        escaped = str(image_paths[-1]).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


_FIT_FILTERS = {
    # scale to fit within the target box, then pad to exact size (letterbox)
    "fit": "scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
    # scale to fill the target box, then crop the overflow
    "crop": "scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
    # ignore aspect ratio entirely
    "stretch": "scale={w}:{h}",
    # same as fit but explicit for clarity in the UI
    "pad": "scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
}


class ImagesToVideoOperation(Operation):
    name = "images_to_video"
    description = "Create a video from a sequence of images"

    def validate(self, params: dict) -> List[str]:
        errors = []
        images = params.get("images") or []
        if len(images) < 1:
            errors.append("Select at least one image.")
        if not params.get("output"):
            errors.append("No output path specified.")
        if not params.get("list_file_path"):
            errors.append("A list_file_path is required to write the image list to.")
        fit_mode = params.get("fit_mode", "fit")
        if fit_mode not in _FIT_FILTERS:
            errors.append(f"Unknown fit mode: {fit_mode}")
        seconds = params.get("seconds_per_image", 5)
        if not isinstance(seconds, (int, float)) or seconds <= 0:
            errors.append("Seconds per image must be a positive number.")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))

        ffmpeg_path = params["ffmpeg_path"]
        images = [Path(p) for p in params["images"]]
        list_file_path = Path(params["list_file_path"])
        seconds_per_image = params.get("seconds_per_image", 5)
        fps = params.get("fps", 30)
        resolution = params.get("resolution", (1920, 1080))
        fit_mode = params.get("fit_mode", "fit")
        audio_path = params.get("audio_path")
        overwrite = params.get("overwrite", False)
        output_path = Path(params["output"])

        write_image_list_file(images, seconds_per_image, list_file_path)

        w, h = resolution
        vf = _FIT_FILTERS[fit_mode].format(w=w, h=h)

        cmd = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]
        cmd += ["-f", "concat", "-safe", "0", "-i", str(list_file_path)]
        if audio_path:
            cmd += ["-i", str(audio_path)]
        cmd += ["-vf", f"{vf},fps={fps}", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if audio_path:
            # -shortest stops at the end of the shorter stream so a long audio
            # track doesn't produce a video that freezes on the last frame.
            cmd += ["-c:a", "aac", "-shortest"]
        cmd += [str(output_path)]
        return cmd
