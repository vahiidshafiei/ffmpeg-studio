"""Overwrite confirmation, respecting the user's global overwrite_policy.

Returns one of: "replace", "rename", "cancel".
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

from app.i18n.translator import t


def resolve_output_path(parent: QWidget, output_path: Path, overwrite_policy: str) -> Path | None:
    """Return the path to actually write to, or None if the user cancelled.

    overwrite_policy: "Always overwrite" | "Never overwrite" | "Ask every time"
    """
    if not output_path.exists():
        return output_path

    if overwrite_policy == "Always overwrite":
        return output_path
    if overwrite_policy == "Never overwrite":
        return _next_available_name(output_path)

    box = QMessageBox(parent)
    box.setWindowTitle(t("overwrite.title"))
    box.setText(t("overwrite.message", name=output_path.name))
    replace_btn = box.addButton(t("overwrite.replace"), QMessageBox.ButtonRole.YesRole)
    rename_btn = box.addButton(t("overwrite.rename"), QMessageBox.ButtonRole.NoRole)
    box.addButton(t("overwrite.cancel"), QMessageBox.ButtonRole.RejectRole)
    box.exec()

    clicked = box.clickedButton()
    if clicked is replace_btn:
        return output_path
    if clicked is rename_btn:
        return _next_available_name(output_path)
    return None


def _next_available_name(path: Path) -> Path:
    counter = 1
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        counter += 1
    return candidate
