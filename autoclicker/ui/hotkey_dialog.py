from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QKeySequenceEdit,
    QLabel,
    QVBoxLayout,
)


def keysequence_to_hotkey_text(sequence: str) -> str:
    normalized = sequence.strip()
    if not normalized:
        return ""
    return normalized.replace("Ctrl", "Control")


class HotkeyDialog(QDialog):
    def __init__(self, start_hotkey: str, stop_hotkey: str, parent: Optional[QDialog] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Customize Hotkeys")
        self.setModal(True)
        self.setFixedSize(360, 200)

        layout = QVBoxLayout(self)
        info = QLabel("Click a field, then press the new key combo.")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.start_edit = QKeySequenceEdit()
        self.start_edit.setKeySequence(start_hotkey)
        form.addRow("Start/Stop toggle:", self.start_edit)

        self.stop_edit = QKeySequenceEdit()
        self.stop_edit.setKeySequence(stop_hotkey)
        form.addRow("Emergency stop:", self.stop_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_hotkeys(self) -> tuple[str, str]:
        start = self.start_edit.keySequence().toString()
        stop = self.stop_edit.keySequence().toString()

        start = keysequence_to_hotkey_text(start)
        stop = keysequence_to_hotkey_text(stop)

        if not start:
            start = "F6"
        if not stop:
            stop = "F7"
        return start, stop
