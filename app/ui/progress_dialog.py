"""执行进度对话框：显示进度、允许取消。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr, translate_widget_tree
from app.ui.widgets import MutedLabel


class ProgressDialog(QDialog):
    cancelRequested = Signal()

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(430)
        self._finished = False
        self._cancel_sent = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        layout.addWidget(heading)
        layout.addWidget(MutedLabel(message))

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)  # 未知总数时显示忙碌动画
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        layout.addWidget(self.bar)

        self.status = QLabel("准备中…")
        self.status.setObjectName("Hint")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self._request_cancel)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        translate_widget_tree(self)

    # ------------------------------------------------------------------
    def set_total(self, total: int) -> None:
        if total > 0:
            self.bar.setRange(0, total)
            self.bar.setValue(0)

    def update_progress(self, done: int, total: int, message: str) -> None:
        self.set_total(total)
        self.bar.setValue(min(done, max(0, total)))
        text = tr(message) if message else tr("正在处理")
        if total > 0:
            text = f"{text}（{done}/{total}）"
        self.status.setText(text)

    def finish(self) -> None:
        self._finished = True
        self.accept()

    # ------------------------------------------------------------------
    def _request_cancel(self) -> None:
        if self._cancel_sent:
            return
        self._cancel_sent = True
        self.cancel_button.setEnabled(False)
        self.status.setText(
            tr("正在取消：已处理的文件会保留，可在结果中撤销…")
        )
        self.cancelRequested.emit()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        if self._finished:
            super().closeEvent(event)
            return
        self._request_cancel()
        event.ignore()
