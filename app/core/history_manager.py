"""Persists completed job records so the History page has something to show
across app restarts. Stored as a single JSON array, capped in length so it
doesn't grow forever.
"""
from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.config.settings_manager import config_dir
from app.models.models import HistoryEntry

_MAX_ENTRIES = 500


def _history_file() -> Path:
    return config_dir() / "history.json"


class HistoryManager:
    def __init__(self):
        self._entries: List[HistoryEntry] = self._load()

    def _load(self) -> List[HistoryEntry]:
        path = _history_file()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [HistoryEntry(**item) for item in data]
        except (json.JSONDecodeError, OSError, TypeError):
            return []

    def _save(self) -> None:
        path = _history_file()
        data = [dataclasses.asdict(e) for e in self._entries[-_MAX_ENTRIES:]]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(
        self,
        operation: str,
        input_summary: str,
        output_path: str,
        status: str,
        duration_seconds: Optional[float] = None,
        command: Optional[List[str]] = None,
    ) -> HistoryEntry:
        entry = HistoryEntry(
            id=str(uuid.uuid4())[:8],
            date=datetime.now().isoformat(timespec="seconds"),
            operation=operation,
            input_summary=input_summary,
            output_path=output_path,
            status=status,
            duration_seconds=duration_seconds,
            command=command or [],
        )
        self._entries.append(entry)
        self._save()
        return entry

    def list_entries(self) -> List[HistoryEntry]:
        return list(reversed(self._entries))  # most recent first

    def delete(self, entry_id: str) -> None:
        self._entries = [e for e in self._entries if e.id != entry_id]
        self._save()

    def clear(self) -> None:
        self._entries = []
        self._save()
