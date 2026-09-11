"""A labeled 'drop files here / Browse…' row, reused across pages.

Supports single file, multiple files, or folder selection depending on how
it's constructed. Emits paths_selected(list[Path]) either way so callers
don't need separate handling for drag-drop vs the file dialog.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QFileDialog

from app.i18n.translator import t


class FileDropField(QWidget):
    paths_selected = Signal(list)  # list[Path]

    def __init__(
        self,
        placeholder: str = None,
        mode: str = "files",  # "file" | "files" | "folder"
        name_filter: str = "All files (*)",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._name_filter = name_filter
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(placeholder or t("common.drop_files_here"))
        self._label.setObjectName("mutedLabel")
        layout.addWidget(self._label, stretch=1)

        browse_label = {
            "file": t("common.select_file"),
            "files": t("common.select_files"),
            "folder": t("common.select_folder"),
        }[mode]
        self._browse_button = QPushButton(browse_label)
        self._browse_button.clicked.connect(self._browse)
        layout.addWidget(self._browse_button)

    def set_label(self, text: str) -> None:
        self._label.setText(text)

    def _browse(self) -> None:
        if self._mode == "file":
            path, _ = QFileDialog.getOpenFileName(self, "Select file", filter=self._name_filter)
            paths = [Path(path)] if path else []
        elif self._mode == "files":
            paths_str, _ = QFileDialog.getOpenFileNames(self, "Select files", filter=self._name_filter)
            paths = [Path(p) for p in paths_str]
        else:  # folder
            folder = QFileDialog.getExistingDirectory(self, "Select folder")
            paths = [Path(folder)] if folder else []

        if paths:
            self._emit_paths(paths)

    def _emit_paths(self, paths: List[Path]) -> None:
        if self._mode == "file":
            self._label.setText(paths[0].name)
        elif self._mode == "folder":
            self._label.setText(str(paths[0]))
        else:
            self._label.setText(f"{len(paths)} file(s) selected" if len(paths) != 1 else paths[0].name)
        self.paths_selected.emit(paths)

    # --- drag and drop ---
    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt override)
        urls = event.mimeData().urls()
        paths = [Path(url.toLocalFile()) for url in urls if url.toLocalFile()]
        if not paths:
            return
        if self._mode == "file":
            paths = paths[:1]
        elif self._mode == "folder":
            paths = [p for p in paths if p.is_dir()][:1] or paths[:1]
        self._emit_paths(paths)
