"""Loads built-in presets shipped with the app and user presets saved to the
config directory. Presets are plain JSON so they're easy to hand-edit,
export, or share.
"""
from __future__ import annotations

import json
import dataclasses
import uuid
from pathlib import Path
from typing import List, Optional

from app.config.settings_manager import config_dir
from app.models.models import Preset


def _builtin_presets_dir() -> Path:
    # __file__-relative resolution works identically in dev and in the
    # frozen .exe as long as build/build.py bundles presets/ at a matching
    # relative destination (see its data_dirs list) — no sys.frozen branch
    # needed. (A sys.executable-relative scheme was used here previously,
    # but that resolves to a different location than where PyInstaller
    # actually places --add-data content, which was silently never bundled
    # at all until this fix.)
    return Path(__file__).resolve().parents[2] / "presets"


def _user_presets_dir() -> Path:
    path = config_dir() / "presets"
    path.mkdir(parents=True, exist_ok=True)
    return path


class PresetManager:
    def __init__(self):
        self._presets: dict[str, Preset] = {}
        self.reload()

    def reload(self) -> None:
        self._presets = {}
        for path in _builtin_presets_dir().glob("*.json"):
            preset = self._load_file(path, built_in=True)
            if preset:
                self._presets[preset.id] = preset
        for path in _user_presets_dir().glob("*.json"):
            preset = self._load_file(path, built_in=False)
            if preset:
                self._presets[preset.id] = preset

    @staticmethod
    def _load_file(path: Path, built_in: bool) -> Optional[Preset]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["built_in"] = built_in
            data.setdefault("id", path.stem)
            return Preset(**data)
        except (json.JSONDecodeError, OSError, TypeError):
            return None

    def list_presets(self, operation: Optional[str] = None) -> List[Preset]:
        presets = list(self._presets.values())
        if operation:
            presets = [p for p in presets if p.operation == operation]
        return sorted(presets, key=lambda p: (not p.built_in, p.name.lower()))

    def get(self, preset_id: str) -> Optional[Preset]:
        return self._presets.get(preset_id)

    def save(self, preset: Preset) -> None:
        if preset.built_in:
            raise ValueError("Built-in presets cannot be modified.")
        path = _user_presets_dir() / f"{preset.id}.json"
        path.write_text(json.dumps(dataclasses.asdict(preset), indent=2), encoding="utf-8")
        self._presets[preset.id] = preset

    def create(self, name: str, operation: str, params: dict, description: str = "") -> Preset:
        preset = Preset(id=str(uuid.uuid4())[:8], name=name, operation=operation, description=description, params=params)
        self.save(preset)
        return preset

    def duplicate(self, preset_id: str, new_name: str) -> Optional[Preset]:
        original = self.get(preset_id)
        if not original:
            return None
        return self.create(new_name, original.operation, dict(original.params), original.description)

    def delete(self, preset_id: str) -> bool:
        preset = self.get(preset_id)
        if not preset or preset.built_in:
            return False
        path = _user_presets_dir() / f"{preset_id}.json"
        if path.exists():
            path.unlink()
        del self._presets[preset_id]
        return True

    def export_to(self, preset_id: str, target_path: Path) -> bool:
        preset = self.get(preset_id)
        if not preset:
            return False
        data = dataclasses.asdict(preset)
        data.pop("built_in", None)
        target_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True

    def import_from(self, source_path: Path) -> Preset:
        data = json.loads(source_path.read_text(encoding="utf-8"))
        data["id"] = str(uuid.uuid4())[:8]
        data["built_in"] = False
        preset = Preset(**data)
        self.save(preset)
        return preset
