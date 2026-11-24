"""操作结果对话框：汇总成功 / 失败 / 跳过，并可直接撤销。"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import translate_widget_tree


class ResultDialog(QDialog):
    undoRequested = Signal()

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        summary_lines: Sequence[str],
        details: Sequence[str] = (),
        backup_path: Path | None = None,
        allow_undo: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.setWindowModality(Qt.WindowModal)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(520)
        self._backup_path = backup_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        layout.addWidget(heading)

        for line in summary_lines:
            label = QLabel(line)
            label.setWordWrap(True)
            layout.addWidget(label)

        if details:
            box = QPlainTextEdit()
            box.setReadOnly(True)
            box.setPlainText("\n".join(details))
            box.setMaximumHeight(190)
            layout.addWidget(box)

        if backup_path is not None:
            backup = QLabel(f"备份文件：{backup_path}")
            backup.setObjectName("Hint")
            backup.setWordWrap(True)
            backup.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(backup)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        if backup_path is not None:
            open_button = QPushButton("打开备份目录")
            open_button.clicked.connect(self._open_backup_dir)
            buttons.addWidget(open_button)
        if allow_undo:
            undo_button = QPushButton("撤销本次重命名")
            undo_button.clicked.connect(self._undo)
            buttons.addWidget(undo_button)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        translate_widget_tree(self)

    def _open_backup_dir(self) -> None:
        if self._backup_path is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._backup_path.parent))
            )

    def _undo(self) -> None:
        self.undoRequested.emit()
        self.accept()
