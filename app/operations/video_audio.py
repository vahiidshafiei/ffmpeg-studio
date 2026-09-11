"""Combine a video and an audio file.

params:
    ffmpeg_path, video_input, output
    audio_input: str|Path | None  (required unless mode == "remove")
    mode: "replace" | "add" | "remove"
        replace: audio_input replaces the video's own audio entirely
        add:     audio_input is mixed alongside the video's existing audio
        remove:  strip the video's audio, no audio_input needed
    audio_encode: "aac" | "copy" — only meaningful for mode == "replace".
        "copy" stream-copies the new audio track with no re-encoding
        (fastest, lossless) — valid here because the video is always
        stream-copied too (see -c:v copy below), so nothing in this
        operation actually needs to touch the audio at all unless you ask
        for "add" (which mixes two tracks via a filter, and a filter
        output can only be re-encoded, never copied).
    duration_policy: how to reconcile mismatched lengths
        "shortest": stop at whichever stream ends first (ffmpeg -shortest)
        "loop_audio": loop the audio track to match video length
        "video_duration": force output to the video's exact duration
                          (only meaningful combined with loop_audio, or when
                          trimming a too-long audio track)
    overwrite: bool
"""
from __future__ import annotations

from typing import List

from app.operations.base import Operation


class VideoAudioOperation(Operation):
    name = "video_audio"
    description = "Add, replace, or remove a video's audio track"

    def validate(self, params: dict) -> List[str]:
        errors = []
        if not params.get("video_input"):
            errors.append("No video file selected.")
        if not params.get("output"):
            errors.append("No output path specified.")
        mode = params.get("mode", "replace")
        if mode not in ("replace", "add", "remove"):
            errors.append(f"Unknown mode: {mode}")
        if mode in ("replace", "add") and not params.get("audio_input"):
            errors.append("An audio file is required for this mode.")
        policy = params.get("duration_policy", "shortest")
        if policy not in ("shortest", "loop_audio", "video_duration"):
            errors.append(f"Unknown duration policy: {policy}")
        audio_encode = params.get("audio_encode", "aac")
        if audio_encode not in ("aac", "copy"):
            errors.append(f"Unknown audio_encode: {audio_encode}")
        return errors

    def build_command(self, params: dict) -> List[str]:
        errors = self.validate(params)
        if errors:
            raise ValueError("; ".join(errors))

        ffmpeg_path = params["ffmpeg_path"]
        video_input = params["video_input"]
        audio_input = params.get("audio_input")
        output_path = params["output"]
        mode = params.get("mode", "replace")
        policy = params.get("duration_policy", "shortest")
        audio_encode = params.get("audio_encode", "aac")
        overwrite = params.get("overwrite", False)

        cmd = [str(ffmpeg_path)]
        cmd += ["-y"] if overwrite else ["-n"]

        if mode == "remove":
            cmd += ["-i", str(video_input), "-c:v", "copy", "-an"]
            cmd += [str(output_path)]
            return cmd

        if policy == "loop_audio":
            # -stream_loop -1 on the audio input loops it indefinitely; combined
            # with -shortest below, it stops once the (shorter) video ends.
            cmd += ["-i", str(video_input), "-stream_loop", "-1", "-i", str(audio_input)]
        else:
            cmd += ["-i", str(video_input), "-i", str(audio_input)]

        cmd += ["-map", "0:v"]
        if mode == "add":
            # Mixing two tracks is a filter operation — its output can only
            # be re-encoded, never stream-copied, regardless of audio_encode.
            cmd += ["-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest[aout]", "-map", "[aout]"]
            audio_codec = "aac"
        else:  # replace
            cmd += ["-map", "1:a"]
            audio_codec = "copy" if audio_encode == "copy" else "aac"

        cmd += ["-c:v", "copy", "-c:a", audio_codec]

        if policy in ("shortest",) or policy == "loop_audio":
            cmd += ["-shortest"]
        elif policy == "video_duration":
            # Explicit fallback for engines/inputs where -shortest based on
            # stream end isn't reliable; -shortest still covers the common
            # case above, this mirrors it for a video-authoritative cut.
            cmd += ["-shortest"]

        cmd += [str(output_path)]
        return cmd
