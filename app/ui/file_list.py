"""文件列表：数据模型、扩展名筛选、排序、拖放与列表操作。"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QItemSelectionModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QUrl

from app.engine.scheme import SORT_KEYS
from app.i18n import add_combo_item, tr
from app.ui.preview import PreviewInfo
from app.ui.widgets import Card, MutedLabel

COLUMNS = ("原文件名", "拍摄时间", "预览", "结果", "状态")
COL_NAME, COL_TAKEN, COL_PREVIEW, COL_RESULT, COL_STATUS = range(5)
COLUMN_SORT_KEYS = ("natural", "taken", "preview", "result", "status")
MAX_ADD_FILES = 10000


@dataclass
class FileEntry:
    path: Path
    preview: str = ""
    result: str = "—"
    status: str = "待预览"
    error: str = ""
    size: int = 0
    mtime: float = 0.0
    conflict_resolved: bool = False
    taken_at: float | None = None
    taken_source: str = ""
    taken_raw: str = ""
    taken_fallback: bool = False
    media_tags: dict[str, str] = field(default_factory=dict)

    @property
    def extension(self) -> str:
        return self.path.suffix.lower().lstrip(".")

    @property
    def display_extension(self) -> str:
        return f".{self.extension}" if self.extension else "(无扩展名)"

    @property
    def taken_display(self) -> str:
        if self.taken_at is None:
            return "—"
        text = datetime.fromtimestamp(self.taken_at).strftime("%Y-%m-%d %H:%M")
        return f"ⓘ {text}" if self.taken_fallback else text

    @property
    def taken_tooltip(self) -> str:
        lines: list[str] = []
        if self.taken_at is None:
            lines.append(
                tr("未检测到拍摄时间，命名时将回退到文件修改时间")
            )
        else:
            moment = datetime.fromtimestamp(self.taken_at).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            lines.append(tr("拍摄时间：{time}", time=moment))
            lines.append(
                tr("来源：{source}", source=tr(self.taken_source or "未知"))
            )
            if self.taken_raw:
                lines.append(tr("元数据原文：{raw}", raw=self.taken_raw))
            if self.taken_fallback:
                lines.append(tr("未找到媒体时间，已回退到文件修改时间"))
        labels = (
            ("标题", "title"),
            ("艺术家 / 导演", "artist"),
            ("专辑 / 系列", "album"),
            ("风格", "genre"),
            ("年份", "year"),
            ("相机", "camera"),
            ("镜头", "lens"),
            ("ISO", "iso"),
            ("光圈", "aperture"),
        )
        for label, key in labels:
            value = self.media_tags.get(key)
            if value:
                lines.append(f"{tr(label)}：{value}")
        return "\n".join(lines)


def _natural_key(text: str) -> list[object]:
    parts = re.split(r"(\d+)", text.casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def _entry_from_path(path: Path) -> FileEntry:
    try:
        stat = path.stat()
        size = stat.st_size
        mtime = stat.st_mtime
    except OSError:
        size = 0
        mtime = 0.0
    return FileEntry(path=path, size=size, mtime=mtime)


class FileTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entries: list[FileEntry] = []

    # ---------- Qt 模型接口 ----------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return tr(COLUMNS[section])
        if role == Qt.TextAlignmentRole and orientation == Qt.Horizontal:
            centered = section in (COL_TAKEN, COL_RESULT, COL_STATUS)
            return int(Qt.AlignCenter if centered else Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.entries):
            return None
        entry = self.entries[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == COL_NAME:
                return entry.path.name
            if column == COL_TAKEN:
                return entry.taken_display
            if column == COL_PREVIEW:
                return entry.preview or "—"
            if column == COL_RESULT:
                return tr(entry.result)
            return tr(entry.status)

        if role == Qt.ToolTipRole:
            if column == COL_NAME:
                return f"{entry.path}\n{entry.taken_tooltip}"
            if column == COL_TAKEN:
                return entry.taken_tooltip
            if column == COL_PREVIEW:
                return entry.error or entry.preview or "尚未生成预览"
            if column == COL_RESULT:
                if entry.result == "失败" and entry.error:
                    return entry.error
                return entry.result
            return entry.error or entry.status

        if role == Qt.ForegroundRole:
            if column in (COL_RESULT, COL_STATUS):
                if entry.status == "错误" or entry.result == "失败":
                    return QColor("#DC2626")
                if entry.status == "未更改":
                    return QColor("#6B7280")
                if entry.status == "冲突已处理":
                    return QColor("#B45309")
                if entry.result in ("成功", "已还原", "已撤销"):
                    return QColor("#047857")
                return QColor("#6B7280")
            if column == COL_TAKEN:
                return QColor("#9CA3AF") if entry.taken_fallback else None
            if column == COL_PREVIEW and entry.error:
                return QColor("#DC2626")
            if column == COL_PREVIEW and entry.status == "未更改":
                return QColor("#6B7280")
            return None

        if role == Qt.TextAlignmentRole:
            if column in (COL_TAKEN, COL_RESULT, COL_STATUS):
                return int(Qt.AlignCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        if role == Qt.UserRole:
            return entry
        return None

    # ---------- 数据操作 ----------
    def add_paths(self, paths: Iterable[Path]) -> tuple[int, int]:
        existing = {os.path.normcase(str(entry.path)) for entry in self.entries}
        new_entries: list[FileEntry] = []
        skipped = 0
        for path in paths:
            if len(self.entries) + len(new_entries) >= MAX_ADD_FILES:
                skipped += 1
                continue
            key = os.path.normcase(str(path))
            if key in existing or not path.is_file():
                skipped += 1
                continue
            existing.add(key)
            new_entries.append(_entry_from_path(path))
        if new_entries:
            start = len(self.entries)
            self.beginInsertRows(QModelIndex(), start, start + len(new_entries) - 1)
            self.entries.extend(new_entries)
            self.endInsertRows()
        return len(new_entries), skipped

    def remove_rows(self, rows: Sequence[int]) -> int:
        targets = sorted({row for row in rows if 0 <= row < len(self.entries)}, reverse=True)
        if not targets:
            return 0
        for row in targets:
            self.beginRemoveRows(QModelIndex(), row, row)
            del self.entries[row]
            self.endRemoveRows()
        return len(targets)

    def clear(self) -> None:
        if not self.entries:
            return
        self.beginResetModel()
        self.entries.clear()
        self.endResetModel()

    def move_rows(self, rows: Sequence[int], delta: int) -> list[int]:
        selected = {row for row in rows if 0 <= row < len(self.entries)}
        if not selected or delta == 0:
            return sorted(selected)

        self.beginResetModel()
        if delta < 0:
            for _ in range(-delta):
                for row in range(1, len(self.entries)):
                    if row in selected and row - 1 not in selected:
                        self.entries[row - 1], self.entries[row] = (
                            self.entries[row],
                            self.entries[row - 1],
                        )
                        selected.remove(row)
                        selected.add(row - 1)
        else:
            for _ in range(delta):
                for row in range(len(self.entries) - 2, -1, -1):
                    if row in selected and row + 1 not in selected:
                        self.entries[row], self.entries[row + 1] = (
                            self.entries[row + 1],
                            self.entries[row],
                        )
                        selected.remove(row)
                        selected.add(row + 1)
        self.endResetModel()
        return sorted(selected)

    def sort_by(self, column: int, ascending: bool = True) -> None:
        if not self.entries:
            return

        def key(entry: FileEntry):
            if column == COL_NAME:
                return _natural_key(entry.path.name)
            if column == COL_TAKEN:
                return entry.taken_at if entry.taken_at is not None else entry.mtime
            if column == COL_PREVIEW:
                return entry.preview.casefold()
            if column == COL_RESULT:
                return entry.result.casefold()
            if column == COL_STATUS:
                return entry.status.casefold()
            return _natural_key(entry.path.name)

        self.beginResetModel()
        self.entries.sort(key=key, reverse=not ascending)
        self.endResetModel()

    def sort_by_key(self, key: str, ascending: bool = True) -> None:
        if not self.entries:
            return

        def sort_key(entry: FileEntry):
            if key == "name":
                return entry.path.name.casefold()
            if key == "mtime":
                return entry.mtime
            if key == "taken":
                return entry.taken_at if entry.taken_at is not None else entry.mtime
            if key == "size":
                return entry.size
            if key == "ext":
                return (entry.extension, _natural_key(entry.path.name))
            if key == "preview":
                return entry.preview.casefold()
            if key == "result":
                return entry.result.casefold()
            if key == "status":
                return entry.status.casefold()
            return _natural_key(entry.path.name)

        self.beginResetModel()
        self.entries.sort(key=sort_key, reverse=not ascending)
        self.endResetModel()

    def set_previews(
        self,
        infos: Sequence[PreviewInfo],
        entries: Sequence[FileEntry] | None = None,
    ) -> None:
        targets = list(entries) if entries is not None else self.entries
        if not targets:
            return
        for entry, info in zip(targets, infos):
            entry.preview = info.target_name
            entry.status = info.status
            entry.error = info.error
            entry.conflict_resolved = info.conflict_resolved
            entry.taken_at = info.taken_at
            entry.taken_source = info.taken_source
            entry.taken_raw = info.taken_raw
            entry.taken_fallback = info.taken_fallback
            entry.media_tags = dict(info.media_tags)
        if self.entries:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self.entries) - 1, len(COLUMNS) - 1),
                [Qt.DisplayRole, Qt.ToolTipRole, Qt.ForegroundRole],
            )

    def set_result(self, row: int, result: str) -> None:
        if 0 <= row < len(self.entries):
            self.entries[row].result = result
            self.dataChanged.emit(self.index(row, COL_RESULT), self.index(row, COL_RESULT))

    def update_after_operation(
        self,
        succeeded: Mapping[str, Path],
        failed: Mapping[str, str] | None = None,
        skipped: Mapping[str, str] | None = None,
        success_text: str = "成功",
    ) -> int:
        """改名/还原后更新行：成功项换成新路径，失败/跳过项写结果列。"""
        failed = failed or {}
        skipped = skipped or {}
        changed = 0
        for entry in self.entries:
            key = os.path.normcase(os.path.abspath(str(entry.path)))
            if key in succeeded:
                entry.path = succeeded[key]
                try:
                    stat = entry.path.stat()
                except OSError:
                    pass
                else:
                    entry.size = stat.st_size
                    entry.mtime = stat.st_mtime
                entry.result = success_text
                entry.error = ""
                entry.preview = ""
                entry.status = "待预览"
                entry.conflict_resolved = False
                entry.taken_at = None
                entry.taken_source = ""
                entry.taken_raw = ""
                entry.taken_fallback = False
                entry.media_tags = {}
                changed += 1
            elif key in failed:
                entry.result = "失败"
                entry.error = failed[key]
                changed += 1
            elif key in skipped:
                entry.result = "跳过"
                entry.error = skipped[key]
                changed += 1
        if changed:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self.entries) - 1, len(COLUMNS) - 1),
                [Qt.DisplayRole, Qt.ToolTipRole, Qt.ForegroundRole],
            )
        return changed

    def entry_at(self, row: int) -> FileEntry | None:
        if 0 <= row < len(self.entries):
            return self.entries[row]
        return None


class FileFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._extensions: set[str] | None = None

    def set_extensions(self, extensions: set[str] | None) -> None:
        self._extensions = extensions
        self.invalidateFilter()

    @property
    def extensions(self) -> set[str] | None:
        return None if self._extensions is None else set(self._extensions)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._extensions is None:
            return True
        model = self.sourceModel()
        if not isinstance(model, FileTableModel):
            return True
        entry = model.entry_at(source_row)
        if entry is None:
            return True
        return entry.extension in self._extensions


class FileListCard(Card):
    filesDropped = Signal(list)
    addRequested = Signal()
    addFolderRequested = Signal(bool)
    countChanged = Signal()
    filesChanged = Signal()
    selectionChanged = Signal(int)
    message = Signal(str)
    undoRequested = Signal()
    restoreRequested = Signal()
    metadataRefreshRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._sort_column = -1
        self._sort_ascending = True
        self._sort_key: str | None = None
        self._build_ui()
        self.refresh_view()

    # ---------- 构建 ----------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("文件列表")
        title.setObjectName("SectionTitle")
        self.count_label = MutedLabel("0 个文件")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.count_label)
        layout.addLayout(header)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_label = MutedLabel("筛选")
        self.filter_combo = QComboBox()
        self.filter_combo.setMinimumWidth(126)
        self.filter_combo.addItem("全部扩展名", None)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("或输入 mp4;mkv")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMaximumWidth(180)
        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.filter_combo)
        filter_row.addWidget(self.filter_edit)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self.stack = QStackedWidget()
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_layout.setSpacing(6)
        empty_layout.addStretch(1)
        self.empty_title = QLabel("还没有添加文件")
        self.empty_title.setObjectName("EmptyTitle")
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_hint = QLabel(
            "点击“添加”选择文件，或直接把文件/文件夹拖到窗口里。\n"
            "所有改动都只显示在“预览”列，确认后才会写入磁盘。"
        )
        self.empty_hint.setObjectName("EmptyHint")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setWordWrap(True)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_hint)
        empty_layout.addStretch(1)
        self.stack.addWidget(empty_page)

        self.model = FileTableModel(self)
        self.proxy = FileFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        header_view = self.table.horizontalHeader()
        header_view.setSectionsClickable(True)
        header_view.setHighlightSections(False)
        header_view.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        header_view.setSectionResizeMode(COL_TAKEN, QHeaderView.Fixed)
        header_view.setSectionResizeMode(COL_PREVIEW, QHeaderView.Stretch)
        header_view.setSectionResizeMode(COL_RESULT, QHeaderView.Fixed)
        header_view.setSectionResizeMode(COL_STATUS, QHeaderView.Fixed)
        self.table.setColumnWidth(COL_TAKEN, 152)
        self.table.setColumnWidth(COL_RESULT, 66)
        self.table.setColumnWidth(COL_STATUS, 96)
        header_view.sectionClicked.connect(self._on_header_clicked)
        self.stack.addWidget(self.table)
        layout.addWidget(self.stack, 1)

        order_row = QHBoxLayout()
        order_row.setSpacing(6)
        order_row.addStretch(1)
        self.top_button = self._make_order_button("⇈", "置顶", lambda: self._move(-999))
        self.up_button = self._make_order_button("↑", "上移", lambda: self._move(-1))
        self.down_button = self._make_order_button("↓", "下移", lambda: self._move(1))
        self.bottom_button = self._make_order_button("⇊", "置底", lambda: self._move(999))
        for button in (self.top_button, self.up_button, self.down_button, self.bottom_button):
            order_row.addWidget(button)
        layout.addLayout(order_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addStretch(1)
        self.add_button = QPushButton("添加")
        self.add_folder_button = QPushButton("添加文件夹")
        self.include_subfolders_check = QCheckBox("含子文件夹")
        self.include_subfolders_check.setChecked(True)
        self.include_subfolders_check.setToolTip(
            "添加文件夹时一并扫描子文件夹中的文件"
        )
        self.remove_button = QPushButton("移除")
        self.clear_button = QPushButton("全部移除")
        self.add_button.clicked.connect(lambda: self.addRequested.emit())
        self.add_folder_button.clicked.connect(
            lambda: self.addFolderRequested.emit(
                self.include_subfolders_check.isChecked()
            )
        )
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_all)
        action_row.addWidget(self.add_button)
        action_row.addWidget(self.add_folder_button)
        action_row.addWidget(self.include_subfolders_check)
        action_row.addWidget(self.remove_button)
        action_row.addWidget(self.clear_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.filter_combo.currentIndexChanged.connect(self._on_combo_filter)
        self.filter_edit.textChanged.connect(self._on_text_filter)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _make_order_button(self, text: str, tip: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("IconButton")
        button.setToolTip(tip)
        button.setEnabled(False)
        button.clicked.connect(callback)
        return button

    # ---------- 公共接口 ----------
    def add_paths(
        self, paths: Sequence[Path], recursive: bool = True
    ) -> tuple[int, int]:
        files, folders = self._expand_paths(paths, recursive=recursive)
        added, skipped = self.model.add_paths(files)
        if added and self._sort_key is not None:
            self.model.sort_by_key(self._sort_key, self._sort_ascending)
        self._update_filter_options()
        self.refresh_view()
        if added:
            if folders:
                self.message.emit(
                    tr(
                        "已添加 {added} 个文件（来自 {folders} 个文件夹）",
                        added=added,
                        folders=folders,
                    )
                )
            else:
                self.message.emit(
                    tr("已添加 {added} 个文件", added=added)
                )
            self.filesChanged.emit()
        elif skipped:
            self.message.emit(tr("没有添加新文件：文件已在列表中或不是有效文件"))
        return added, skipped

    def include_subfolders(self) -> bool:
        return self.include_subfolders_check.isChecked()

    def set_include_subfolders(self, include: bool) -> None:
        self.include_subfolders_check.setChecked(bool(include))

    def remove_selected(self) -> None:
        rows = self.selected_source_rows()
        if not rows:
            return
        removed = self.model.remove_rows(rows)
        self._update_filter_options()
        self.refresh_view()
        if removed:
            self.message.emit(
                tr("已移除 {removed} 个文件", removed=removed)
            )
            self.filesChanged.emit()

    def clear_all(self, confirm: bool = True) -> None:
        if not self.model.entries:
            return
        if confirm:
            answer = QMessageBox.question(
                self,
                tr("全部移除"),
                tr(
                    "确定要从列表中移除全部 {count} 个文件吗？\n"
                    "这不会删除磁盘上的文件。",
                    count=len(self.model.entries),
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.model.clear()
        self._update_filter_options()
        self.refresh_view()
        self.message.emit(tr("已清空文件列表"))
        self.filesChanged.emit()

    def refresh_previews(
        self,
        infos: Sequence[PreviewInfo],
        entries: Sequence[FileEntry] | None = None,
    ) -> None:
        self.model.set_previews(infos, entries)
        self.refresh_view()

    def apply_operation_result(
        self,
        succeeded: Mapping[str, Path],
        failed: Mapping[str, str] | None = None,
        skipped: Mapping[str, str] | None = None,
        success_text: str = "成功",
    ) -> int:
        """把改名/还原结果写回列表，并触发一次新的预览。"""
        changed = self.model.update_after_operation(
            succeeded, failed, skipped, success_text
        )
        self._update_filter_options()
        self.refresh_view()
        if changed:
            self.filesChanged.emit()
        return changed

    def entries(self) -> list[FileEntry]:
        return list(self.model.entries)

    def visible_entries(self) -> list[FileEntry]:
        result: list[FileEntry] = []
        for row in range(self.proxy.rowCount()):
            source = self.proxy.mapToSource(self.proxy.index(row, 0))
            entry = self.model.entry_at(source.row())
            if entry is not None:
                result.append(entry)
        return result

    def total_count(self) -> int:
        return len(self.model.entries)

    def visible_count(self) -> int:
        return self.proxy.rowCount()

    def sort_by_key(self, key: str, ascending: bool = True) -> None:
        self._sort_key = key
        self._sort_ascending = ascending
        self.model.sort_by_key(key, ascending)
        self._sort_column = -1
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.refresh_view()
        self.filesChanged.emit()
        self.message.emit(tr("排序已更新，编号将按当前顺序生成"))

    def set_sort_state(self, key: str, ascending: bool = True) -> None:
        """恢复方案或配置里的排序，不弹出提示。"""
        if key not in SORT_KEYS:
            key = "natural"
        self._sort_key = key
        self._sort_ascending = ascending
        if self.model.entries:
            self.model.sort_by_key(key, ascending)
        self._sort_column = -1
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.refresh_view()
        self.filesChanged.emit()

    def sort_state(self) -> tuple[str, bool]:
        return (self._sort_key or "natural", self._sort_ascending)

    def filter_extensions(self) -> list[str]:
        extensions = self.proxy.extensions
        return sorted(extensions) if extensions else []

    def set_filter_extensions(self, extensions: Sequence[str]) -> None:
        cleaned = sorted({item.strip().lower().lstrip(".") for item in extensions if item})
        if not cleaned:
            self.clear_filter()
            return
        text = ";".join(cleaned)
        if self.filter_edit.text() == text:
            return
        self.filter_edit.setText(text)

    def clear_filter(self) -> None:
        self.filter_edit.blockSignals(True)
        self.filter_edit.clear()
        self.filter_edit.blockSignals(False)
        self.filter_combo.blockSignals(True)
        self.filter_combo.setCurrentIndex(0)
        self.filter_combo.blockSignals(False)
        self.proxy.set_extensions(None)
        self.refresh_view()
        self.filesChanged.emit()

    def focus_filter(self) -> None:
        self.filter_edit.setFocus()
        self.filter_edit.selectAll()

    def selected_source_rows(self) -> list[int]:
        selection = self.table.selectionModel()
        if selection is None:
            return []
        rows = {
            self.proxy.mapToSource(index).row()
            for index in selection.selectedRows()
        }
        return sorted(row for row in rows if row >= 0)

    def selected_entries(self) -> list[FileEntry]:
        return [
            entry
            for row in self.selected_source_rows()
            if (entry := self.model.entry_at(row)) is not None
        ]

    def refresh_view(self) -> None:
        total = self.total_count()
        visible = self.visible_count()
        if total == 0:
            self.empty_title.setText(tr("还没有添加文件"))
            self.empty_hint.setText(
                tr(
                    "点击“添加”选择文件，或直接把文件/文件夹拖到窗口里。\n"
                    "所有改动都只显示在“预览”列，确认后才会写入磁盘。"
                )
            )
        elif visible == 0:
            self.empty_title.setText(tr("没有匹配的文件"))
            self.empty_hint.setText(
                tr("当前筛选条件没有结果，调整扩展名或选择“全部扩展名”。")
            )
        else:
            self.empty_title.setText(tr("还没有添加文件"))
        self.stack.setCurrentIndex(1 if visible else 0)
        if total == 0:
            self.count_label.setText(tr("{count} 个文件", count=0))
        elif visible == total:
            self.count_label.setText(tr("{count} 个文件", count=total))
        else:
            self.count_label.setText(
                tr("筛选 {visible} / {total} 个文件", visible=visible, total=total)
            )

        has_selection = bool(self.selected_source_rows())
        self.remove_button.setEnabled(has_selection)
        for button in (self.top_button, self.up_button, self.down_button, self.bottom_button):
            button.setEnabled(has_selection)
        self.clear_button.setEnabled(total > 0)
        self.selectionChanged.emit(len(self.selected_entries()))
        self.countChanged.emit()

    def retranslate_language(self) -> None:
        self.model.headerDataChanged.emit(
            Qt.Horizontal, 0, len(COLUMNS) - 1
        )
        self._update_filter_options()
        self.refresh_view()

    # ---------- 筛选 ----------
    def _update_filter_options(self) -> None:
        current = self.filter_combo.currentData()
        extensions = sorted(
            {entry.extension for entry in self.model.entries},
            key=lambda item: (item == "", item),
        )
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        add_combo_item(self.filter_combo, "全部扩展名", None)
        for extension in extensions:
            label = f".{extension}" if extension else "(无扩展名)"
            add_combo_item(self.filter_combo, label, extension)
        index = self.filter_combo.findData(current)
        self.filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.filter_combo.blockSignals(False)

    def _on_combo_filter(self) -> None:
        if self.filter_edit.text():
            self.filter_edit.blockSignals(True)
            self.filter_edit.clear()
            self.filter_edit.blockSignals(False)
        data = self.filter_combo.currentData()
        self.proxy.set_extensions(None if data is None else {data})
        self.refresh_view()
        self.filesChanged.emit()

    def _on_text_filter(self, text: str) -> None:
        if text.strip():
            self.filter_combo.blockSignals(True)
            self.filter_combo.setCurrentIndex(0)
            self.filter_combo.blockSignals(False)
        parts = [
            part.strip().lower().lstrip(".")
            for part in re.split(r"[;,，；\s]+", text)
            if part.strip()
        ]
        if parts:
            self.proxy.set_extensions(set(parts))
        else:
            data = self.filter_combo.currentData()
            self.proxy.set_extensions(None if data is None else {data})
        self.refresh_view()
        self.filesChanged.emit()

    # ---------- 排序 / 移动 ----------
    def _on_header_clicked(self, column: int) -> None:
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True
        if 0 <= column < len(COLUMN_SORT_KEYS):
            self._sort_key = COLUMN_SORT_KEYS[column]
        self.model.sort_by_key(self._sort_key or "natural", self._sort_ascending)
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(
            column,
            Qt.AscendingOrder if self._sort_ascending else Qt.DescendingOrder,
        )
        self.refresh_view()
        self.filesChanged.emit()
        self.message.emit(tr("排序已更新，编号将按当前顺序生成"))

    def _move(self, delta: int) -> None:
        rows = self.selected_source_rows()
        if not rows:
            return
        new_rows = self.model.move_rows(rows, delta)
        self._sort_column = -1
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.refresh_view()
        self._select_source_rows(new_rows)
        self.filesChanged.emit()
        self.message.emit(tr("顺序已更新，编号将按当前顺序生成"))

    def _select_source_rows(self, rows: Sequence[int]) -> None:
        selection = self.table.selectionModel()
        if selection is None:
            return
        selection.clearSelection()
        for row in rows:
            source_index = self.model.index(row, 0)
            proxy_index = self.proxy.mapFromSource(source_index)
            if proxy_index.isValid():
                selection.select(
                    proxy_index,
                    QItemSelectionModel.Select | QItemSelectionModel.Rows,
                )

    # ---------- 拖放 ----------
    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()

    # ---------- 上下文菜单 ----------
    def _show_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid() and not self.table.selectionModel().isSelected(index):
            self.table.selectRow(index.row())
        menu = QMenu(self)
        remove_action = QAction(tr("移除所选"), menu)
        remove_action.setEnabled(bool(self.selected_source_rows()))
        remove_action.triggered.connect(self.remove_selected)
        menu.addAction(remove_action)
        menu.addSeparator()
        reveal_action = QAction(tr("在资源管理器中显示"), menu)
        entries = self.selected_entries()
        reveal_action.setEnabled(bool(entries))
        if entries:
            reveal_action.triggered.connect(
                lambda: QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(entries[0].path.parent))
                )
            )
        menu.addAction(reveal_action)
        refresh_action = QAction(tr("重新读取拍摄时间"), menu)
        refresh_action.setEnabled(bool(entries))
        refresh_action.triggered.connect(lambda: self.metadataRefreshRequested.emit())
        menu.addAction(refresh_action)
        menu.addSeparator()
        undo_action = QAction(tr("撤销上一次重命名"), menu)
        undo_action.triggered.connect(lambda: self.undoRequested.emit())
        restore_action = QAction(tr("一键还原…"), menu)
        restore_action.triggered.connect(lambda: self.restoreRequested.emit())
        menu.addAction(undo_action)
        menu.addAction(restore_action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    # ---------- 内部 ----------
    def _expand_paths(
        self, paths: Sequence[Path], recursive: bool = True
    ) -> tuple[list[Path], int]:
        files: list[Path] = []
        folders = 0
        for path in paths:
            if path.is_dir():
                folders += 1
                if recursive:
                    roots = (Path(root) for root, _dirs, _names in os.walk(path))
                    for root in roots:
                        try:
                            names = [item.name for item in root.iterdir()]
                        except OSError:
                            continue
                        for name in names:
                            candidate = root / name
                            if candidate.is_file():
                                files.append(candidate)
                            if len(files) >= MAX_ADD_FILES:
                                break
                        if len(files) >= MAX_ADD_FILES:
                            break
                else:
                    try:
                        entries = list(path.iterdir())
                    except OSError:
                        entries = []
                    for candidate in entries:
                        if candidate.is_file():
                            files.append(candidate)
                        if len(files) >= MAX_ADD_FILES:
                            break
            elif path.is_file():
                files.append(path)
            if len(files) >= MAX_ADD_FILES:
                break
        if len(files) >= MAX_ADD_FILES:
            self.message.emit(tr("一次最多添加 {max} 个文件，超出部分已忽略", max=MAX_ADD_FILES))
        return files, folders

    def _on_selection_changed(self, *_args) -> None:
        has_selection = bool(self.selected_source_rows())
        self.remove_button.setEnabled(has_selection)
        for button in (self.top_button, self.up_button, self.down_button, self.bottom_button):
            button.setEnabled(has_selection)
        self.selectionChanged.emit(len(self.selected_entries()))
