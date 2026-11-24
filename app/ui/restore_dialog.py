"""备份列表与一键还原对话框。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.engine.backup import (
    KIND_RENAME,
    KIND_RESTORE,
    KIND_UNDO,
    STATE_COMPLETED,
    STATE_COMPLETED_WITH_ERRORS,
    STATE_INCOMPLETE,
    STATE_PREPARING,
    STATE_RENAMING,
    STATE_ROLLED_BACK,
    BackupRecord,
    BackupStore,
    STATUS_FAILED,
    STATUS_OK,
)
from app.engine.undo import CONFLICT_RENAME, CONFLICT_SKIP, build_reverse_plan
from app.i18n import tr, translate_widget_tree
from app.ui.widgets import HintLabel, MutedLabel

KIND_LABELS = {
    KIND_RENAME: "重命名",
    KIND_UNDO: "撤销",
    KIND_RESTORE: "还原",
}
STATE_LABELS = {
    STATE_PREPARING: "准备中",
    STATE_RENAMING: "执行中",
    STATE_COMPLETED: "完成",
    STATE_COMPLETED_WITH_ERRORS: "部分失败",
    STATE_INCOMPLETE: "未完成",
    STATE_ROLLED_BACK: "已还原",
}
COLUMNS = ("时间", "类型", "状态", "文件数", "成功", "失败", "说明")


class RestoreDialog(QDialog):
    """列出全部备份批次，选择一批还原；也作为“备份管理”入口。"""

    def __init__(
        self,
        store: BackupStore,
        parent: QWidget | None = None,
        preselect_latest: bool = True,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self.setWindowTitle("备份与还原")
        self.setMinimumSize(760, 480)
        self.batch_id: str | None = None
        self.conflict = CONFLICT_SKIP
        self._records: list[BackupRecord] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        heading = QLabel("备份与还原")
        heading.setObjectName("DialogTitle")
        layout.addWidget(heading)
        layout.addWidget(
            HintLabel(
                "每次改名都会先写入 JSON 备份。选择一批已完成的记录即可把文件还原到原名称；"
                "原位置被占用时默认跳过，不会覆盖。"
            )
        )

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        options = QHBoxLayout()
        options.setSpacing(8)
        options.addWidget(MutedLabel("原位置被占用时"))
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem("跳过，不覆盖（推荐）", CONFLICT_SKIP)
        self.conflict_combo.addItem("自动加序号 (1)、(2)…", CONFLICT_RENAME)
        self.conflict_combo.currentIndexChanged.connect(self._update_preview)
        options.addWidget(self.conflict_combo)
        options.addStretch(1)
        layout.addLayout(options)

        self.preview = QLabel("请选择要还原的批次")
        self.preview.setObjectName("Hint")
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)

        self.error_label = QLabel("")
        self.error_label.setObjectName("DangerText")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.refresh_button = QPushButton("刷新列表")
        self.refresh_button.clicked.connect(self.reload)
        self.open_button = QPushButton("打开备份目录")
        self.open_button.clicked.connect(self._open_backup_dir)
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.open_button)
        buttons.addStretch(1)
        self.restore_button = QPushButton("还原所选")
        self.restore_button.setObjectName("Primary")
        self.restore_button.setEnabled(False)
        self.restore_button.clicked.connect(self._accept_restore)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.reject)
        buttons.addWidget(self.restore_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.table.itemSelectionChanged.connect(self._update_preview)
        self.table.doubleClicked.connect(self._on_double_click)
        self.reload(preselect_latest=preselect_latest)
        translate_widget_tree(self)

    # ------------------------------------------------------------------
    def reload(self, preselect_latest: bool = True) -> None:
        try:
            self._records = self._store.list_records()
        except Exception as exc:  # noqa: BLE001
            self._records = []
            self.error_label.setText(f"读取备份失败：{exc}")
        self.table.setRowCount(0)
        restorable_row = -1
        for index, record in enumerate(self._records):
            counts = record.counts
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = (
                record.created_at[:19].replace("T", " "),
                tr(KIND_LABELS.get(record.kind, record.kind)),
                tr(STATE_LABELS.get(record.state, record.state)),
                str(len(record.items)),
                str(counts.get(STATUS_OK, 0)),
                str(counts.get(STATUS_FAILED, 0)),
                tr(record.note),
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if column in (3, 4, 5):
                    item.setTextAlignment(int(Qt.AlignCenter))
                if column == 6:
                    item.setToolTip(record.note)
                self.table.setItem(row, column, item)
            if self._is_restorable(record) and restorable_row < 0:
                restorable_row = row
        if self._store.errors:
            self.error_label.setText("；".join(self._store.errors))
        elif not self._records:
            self.error_label.setText("备份目录里还没有记录")
        else:
            self.error_label.setText("")

        if restorable_row >= 0:
            self.table.selectRow(restorable_row)
        else:
            self._update_preview()

    def selected_record(self) -> BackupRecord | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        index = rows[0].row()
        if 0 <= index < len(self._records):
            return self._records[index]
        return None

    @property
    def conflict_policy(self) -> str:
        return self.conflict_combo.currentData() or CONFLICT_SKIP

    # ------------------------------------------------------------------
    def _is_restorable(self, record: BackupRecord) -> bool:
        return (
            record.kind == KIND_RENAME
            and record.state in (STATE_COMPLETED, STATE_COMPLETED_WITH_ERRORS)
            and any(item.status == STATUS_OK for item in record.items)
        )

    def _update_preview(self) -> None:
        record = self.selected_record()
        if record is None:
            self.preview.setText(tr("请选择要还原的批次"))
            self.restore_button.setEnabled(False)
            return
        if not self._is_restorable(record):
            self.preview.setText(
                tr("该批次不可还原：只有“完成 / 部分失败”的重命名批次支持一键还原。")
            )
            self.restore_button.setEnabled(False)
            return
        try:
            plan = build_reverse_plan(record, conflict=self.conflict_policy)
        except ValueError as exc:
            self.preview.setText(str(exc))
            self.restore_button.setEnabled(False)
            return
        parts = [tr("将还原 {count} 个文件", count=len(plan.items))]
        if plan.skipped:
            parts.append(
                tr("跳过 {count} 个（原位置被占用）", count=len(plan.skipped))
            )
        if plan.missing:
            parts.append(tr("缺失 {count} 个", count=len(plan.missing)))
        self.preview.setText(" · ".join(parts))
        self.restore_button.setEnabled(bool(plan.items))

    def _accept_restore(self) -> None:
        record = self.selected_record()
        if record is None or not self._is_restorable(record):
            return
        self.batch_id = record.batch_id
        self.conflict = self.conflict_policy
        self.accept()

    def _on_double_click(self, _index) -> None:
        if self.restore_button.isEnabled():
            self._accept_restore()

    def _open_backup_dir(self) -> None:
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(Path(self._store.root)))
        )
