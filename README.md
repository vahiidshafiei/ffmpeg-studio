# FFmpeg Studio

A modern PySide6 desktop GUI for FFmpeg on Windows — built to replace repetitive,
manually-typed FFmpeg PowerShell commands with a real application, while never
hiding what FFmpeg is actually doing.

> **GUI convenience + full FFmpeg transparency.** Every operation shows you the
> exact command it's about to run, before it runs.

## Status: Phases 1–4 complete

Every sidebar page is real and functional:

- **Compress, Convert, Trim, Merge, Shorts, Video+Audio** — each with its own
  options form, live command preview, async execution via `QProcess`, and
  real-time progress (time/speed/ETA) parsed from `-progress pipe:1`
- **Audio** — three tabs: extract from video, convert format/bitrate/sample
  rate, and batch-merge a folder of files in natural sort order (`1.mp3,
  2.mp3, … 10.mp3`, not lexicographic)
- **Images → Video** — natural-sorted image list, per-image duration, FPS,
  resolution, fit/crop/stretch/pad, optional audio track
- **Batch** — apply Compress across many files/a folder via a sequential job
  queue; one file failing doesn't stop the rest
- **Presets** — 5 built-in presets (YouTube 1080p, YouTube Shorts, Lecture
  Compression, Small File, High Quality) plus duplicate/delete/export/import
  for custom ones, stored as JSON
- **History** — every completed job (single or batch) is recorded with date,
  operation, input, output, and status; open output folder / copy command /
  delete / clear from the page
- FFmpeg/FFprobe detection (bundled → system PATH → user-configured), drag &
  drop file inputs, overwrite protection (respecting a global policy or
  asking each time), rotating file logging, JSON settings persistence
- 47 passing unit tests covering every command builder, natural sort,
  timecode parsing, and progress parsing — all without launching the GUI

Applying a preset directly into an operation page's controls is stubbed as a
management feature on the Presets page (browse/duplicate/delete/export/
import); auto-filling a page's form from a selected preset is the natural
next increment and isn't claimed as done here.

## Language

Settings → Language switches the interface between English 🇬🇧 and Turkish
🇹🇷 (flags shown in the selector). Takes full effect after restarting the
app. Adding another language means adding one file:
`app/i18n/locales/<code>.json` with the same keys as `en.json`, plus one
entry in `app/i18n/languages.py` (code, native name, flag emoji).

## Help documentation

The in-app **Help** sidebar entry opens `assets/help.html` in your default
browser — a single self-contained file (no external dependencies) covering
every page in detail: what each option does, when to use Fast vs Accurate
trim, why natural sort matters for audio merging, the full Storyboard
workflow, etc.

It's generated, not hand-written:

```powershell
python docs\generate_help.py
```

- **`docs/help_data.py`** is the actual documentation content — edit this
  when a page's behavior changes or a new page ships. Each entry is one
  sidebar module with a summary and HTML body fragments.
- **`docs/generate_help.py`** is the presentation layer (styling, sidebar
  nav, search) — it should rarely need touching.

Regenerate after any page's behavior changes, and before cutting a release
— `assets/help.html` is not committed to source-of-truth status; `help_data.py`
is. The generated file ships automatically with the packaged .exe since it
lands in `assets/`, which `build/build.py` already bundles.

## Project layout

```
FFmpegStudio/
├── app/
│   ├── main.py                # entry point
│   ├── ui/
│   │   ├── main_window.py     # sidebar + stacked pages, wiring
│   │   ├── widgets/           # sidebar, command preview
│   │   └── pages/             # one file per sidebar page
│   ├── core/
│   │   ├── ffmpeg_manager.py  # locate ffmpeg/ffprobe
│   │   ├── media_probe.py     # ffprobe -> MediaInfo
│   │   ├── process_manager.py # QProcess wrapper, async execution
│   │   └── progress_parser.py # parses -progress pipe:1 output
│   ├── operations/            # one file per operation; pure command builders
│   │   ├── base.py            # Operation interface
│   │   └── compress.py, convert.py, trim.py, merge.py, audio.py,
│   │       image_video.py, video_audio.py, shorts.py, storyboard.py
│   ├── models/                # dataclasses shared across layers
│   ├── config/                # settings, logging, theme application
│   └── utils/                 # natural sort, formatting, timecode parsing, output naming
├── assets/                    # stylesheets, icons, generated help.html
├── docs/                      # help_data.py (content) + generate_help.py (renderer)
├── tests/                     # pytest suite, no GUI required
├── build/build.py             # PyInstaller build script
├── requirements.txt
└── LICENSE
```

**Why this shape:** every `operations/*.py` file implements the same
interface (`validate(params)`, `build_command(params)`) as a pure function —
no Qt, no subprocess. Pages only collect user input into a `params` dict and
hand it to the operation. `process_manager.py` doesn't know anything about
compression or trimming — it just runs whatever command list it's given and
reports progress. This is what makes adding a new operation later a matter of
one new operation file + one new page, not a change to core.

## Installation (development)

Requires Python 3.10+ and FFmpeg.

```powershell
git clone <repo-url>
cd FFmpegStudio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### FFmpeg setup

FFmpeg Studio looks for FFmpeg in this order:

1. A path you set manually in **Settings → FFmpeg**
2. A bundled `ffmpeg/ffmpeg.exe` + `ffmpeg/ffprobe.exe` next to the app
3. `ffmpeg`/`ffprobe` on your system `PATH`

For development, the easiest option is installing FFmpeg normally (e.g. via
[gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/) or `winget install
ffmpeg`) and letting the app find it on `PATH`.

## Running

```powershell
python -m app.main
```

## Running tests

```powershell
pytest
```

## Building the .exe

```powershell
python build\build.py
```

This produces `dist/FFmpegStudio/FFmpegStudio.exe` (one-folder build — see
`build/build.py` for why one-folder was chosen over one-file). If a local
`ffmpeg/` folder with `ffmpeg.exe`/`ffprobe.exe` exists in the project root at
build time, it's copied into the dist output automatically.

**FFmpeg licensing note:** if you bundle FFmpeg binaries with a build you
distribute, you're responsible for complying with FFmpeg's own license (GPL
or LGPL depending on the build) — see `LICENSE` and https://ffmpeg.org/legal.html.

## Adding a new operation

1. Create `app/operations/your_operation.py` implementing the `Operation`
   interface (`validate`, `build_command`) — see `compress.py` for a
   reference implementation and `test_compress_operation.py` for how it's
   tested in isolation.
2. Add a page under `app/ui/pages/your_operation_page.py` that collects
   inputs into a `params` dict, shows a `CommandPreviewWidget`, and runs the
   command through `FFmpegProcess` (see `compress_page.py`).
3. Register the page in `MainWindow._build_pages()` and add a sidebar entry
   in `app/ui/widgets/sidebar.py`.

No changes to `core/` are needed for a new operation that just runs a single
ffmpeg invocation.

## Roadmap

Remaining from the original spec, roughly in priority order:
- Wire preset selection into each operation page's own form (currently only
  the Presets page itself manages presets)
- Media thumbnails in file pickers (info is shown as text today; a full
  preview player was explicitly out of scope for V1 per the spec)
- Job queue UI as its own page (currently embedded per-page/in Batch; a
  unified cross-operation queue is a natural Phase 5 extension)
- Advanced FFmpeg argument box (custom extra args) surfaced in the UI —
  the command builders already accept `extra_args`, just not exposed yet
  on most pages
- Pause support for batch jobs (cancel is implemented; true pause isn't,
  per ffmpeg's own process model)

## Troubleshooting

- **"FFmpeg not detected"** on Home: open Settings and either click "Detect
  Automatically" after installing FFmpeg, or browse to your `ffmpeg.exe` /
  `ffprobe.exe` manually.
- **Logs**: check the log file path printed in the console on startup (also
  findable via `platformdirs.user_log_dir("FFmpegStudio", "FFmpegStudio")`).
- **Settings not saving**: settings are written to
  `platformdirs.user_config_dir("FFmpegStudio", "FFmpegStudio")/settings.json`;
  make sure that location is writable.
