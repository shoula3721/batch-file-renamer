"""主窗口：规则面板、文件列表、菜单与状态栏。"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QSettings, QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app import i18n
from app.engine.backup import (
    BackupError,
    BackupStore,
    STATUS_FAILED,
    STATUS_OK,
)
from app.engine.executor import BatchResult, RenameExecutor, RenameItem
from app.engine.metadata import CaptureCache
from app.engine.rules import RuleSet
from app.engine.scheme import Scheme, SchemeError
from app.engine.undo import (
    CONFLICT_SKIP,
    RestoreOutcome,
    latest_restorable,
    recover_incomplete,
    restore_batch,
)
from app.paths import backup_dir
from app.ui import theme
from app.ui.file_list import FileEntry, FileListCard
from app.ui.help_dialog import HelpDialog
from app.ui.operations import TaskWorker
from app.ui.preview_worker import PreviewWorker
from app.ui.progress_dialog import ProgressDialog
from app.ui.restore_dialog import RestoreDialog
from app.ui.result_dialog import ResultDialog
from app.ui.rules_panel import TAB_TITLES, RulesPanel

APP_TITLE = "批量文件改名"


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024 / 1024 / 1024:.2f} GB"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 800)
        self.setMinimumSize(1040, 680)
        self.setAcceptDrops(True)
        self._last_dir = str(Path.home())
        i18n.initialize()
        i18n.install_message_filter(QApplication.instance())
        i18n.install_qt_translator(QApplication.instance())
        self._theme_mode = theme.load_theme_mode()
        theme.apply_theme(QApplication.instance(), self._theme_mode)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(120)
        self._preview_timer.timeout.connect(self._apply_previews)

        self.metadata_cache = CaptureCache()
        self._preview_generation = 0
        self._preview_entries: list[FileEntry] = []
        self._sort_after_preview: str | None = None
        self._preview_pending = False

        self._busy = False
        self._worker: TaskWorker | None = None
        self._progress_dialog: ProgressDialog | None = None
        self._backup_error = ""
        self.backup_store: BackupStore | None = None
        try:
            self.backup_store = BackupStore()
        except BackupError as exc:
            self._backup_error = str(exc)

        self._preview_worker = PreviewWorker(self.metadata_cache, self)
        self._preview_worker.ready.connect(self._on_previews_ready)
        self._preview_worker.progress.connect(self._on_preview_progress)
        self._preview_worker.failed.connect(self._on_preview_failed)
        self._preview_worker.start()

        self._settings_timer = QTimer(self)
        self._settings_timer.setSingleShot(True)
        self._settings_timer.setInterval(1000)
        self._settings_timer.timeout.connect(self._save_scheme_settings)

        self._build_actions()
        self._build_ui()
        self._build_menus()
        self._connect_signals()
        self._load_settings()
        i18n.translate_widget_tree(self)
        self._sync_language_actions()
        self._update_status()
        self.statusBar().showMessage(
            i18n.tr("就绪 · 添加文件后即可看到实时预览")
        )
        self._refresh_edit_actions()
        self._sync_theme_actions()
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(
                self._on_system_color_scheme_changed
            )
        except (AttributeError, TypeError):
            pass
        QTimer.singleShot(0, self._check_startup_recovery)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build_actions(self) -> None:
        self.act_add_files = QAction("添加文件…", self)
        self.act_add_files.setShortcut("Ctrl+O")
        self.act_add_files.triggered.connect(self._add_files)

        self.act_add_folder = QAction("添加文件夹…", self)
        self.act_add_folder.setShortcut("Ctrl+Shift+A")
        self.act_add_folder.triggered.connect(lambda: self._add_folder())

        self.act_import = QAction("导入方案…", self)
        self.act_import.setShortcut("Ctrl+Shift+O")
        self.act_import.triggered.connect(self._import_scheme)

        self.act_export = QAction("导出方案…", self)
        self.act_export.setShortcut("Ctrl+S")
        self.act_export.triggered.connect(self._export_scheme)

        self.act_backups = QAction("备份管理…", self)
        self.act_backups.triggered.connect(
            lambda: self._open_restore_dialog(preselect_latest=False)
        )

        self.act_exit = QAction("退出", self)
        self.act_exit.setShortcut("Ctrl+Q")
        self.act_exit.triggered.connect(self._on_cancel)

        self.act_undo = QAction("撤销上一次重命名", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.act_undo.triggered.connect(self._undo_last)

        self.act_restore = QAction("一键还原…", self)
        self.act_restore.triggered.connect(
            lambda: self._open_restore_dialog(preselect_latest=True)
        )

        self.act_select_all = QAction("全选", self)
        self.act_select_all.setShortcut("Ctrl+A")
        self.act_select_all.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.act_select_all.triggered.connect(self._select_all)

        self.act_remove = QAction("移除所选", self)
        self.act_remove.setShortcut("Delete")
        self.act_remove.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.act_remove.triggered.connect(self._remove_selected)

        self.act_clear = QAction("清空列表", self)
        self.act_clear.triggered.connect(self._clear_list)

        self.act_sort_natural = QAction("按序号排序", self)
        self.act_sort_natural.triggered.connect(
            lambda: self.file_list.sort_by_key("natural", True)
        )
        self.act_sort_name = QAction("按名称排序", self)
        self.act_sort_name.triggered.connect(
            lambda: self.file_list.sort_by_key("name", True)
        )
        self.act_sort_mtime = QAction("按修改时间排序", self)
        self.act_sort_mtime.triggered.connect(
            lambda: self.file_list.sort_by_key("mtime", True)
        )
        self.act_sort_size = QAction("按大小排序", self)
        self.act_sort_size.triggered.connect(
            lambda: self.file_list.sort_by_key("size", True)
        )
        self.act_sort_taken = QAction("按拍摄时间排序", self)
        self.act_sort_taken.triggered.connect(self._sort_by_taken)

        self.act_focus_filter = QAction("筛选扩展名…", self)
        self.act_focus_filter.triggered.connect(self._focus_filter)
        self.act_clear_filter = QAction("清除筛选", self)
        self.act_clear_filter.triggered.connect(self._clear_filter)

        self.act_help = QAction("使用说明", self)
        self.act_help.setShortcut("F1")
        self.act_help.triggered.connect(self._show_help)
        self.act_about = QAction("关于", self)
        self.act_about.triggered.connect(self._show_about)

        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.act_theme_light = QAction("白天", self)
        self.act_theme_dark = QAction("夜间", self)
        self.act_theme_system = QAction("跟随系统", self)
        self._theme_actions = {
            theme.THEME_LIGHT: self.act_theme_light,
            theme.THEME_DARK: self.act_theme_dark,
            theme.THEME_SYSTEM: self.act_theme_system,
        }
        for mode, action in self._theme_actions.items():
            action.setCheckable(True)
            action.setData(mode)
            action.triggered.connect(
                lambda _checked=False, value=mode: self._set_theme(value)
            )
            self.theme_group.addAction(action)

        self.act_reset_defaults = QAction("重置为默认设置", self)
        self.act_reset_defaults.triggered.connect(self._reset_defaults)

        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self._language_actions: dict[str, QAction] = {}
        for code, label in i18n.LANGUAGES.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(code)
            action.triggered.connect(
                lambda _checked=False, value=code: self._switch_language(value)
            )
            self.language_group.addAction(action)
            self._language_actions[code] = action

    def _build_ui(self) -> None:
        root_widget = QWidget()
        root_widget.setObjectName("Root")
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(18, 16, 18, 12)
        root.setSpacing(10)

        root.addLayout(self._build_header())
        root.addWidget(self._build_segmented(), 0, Qt.AlignLeft)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.rules_panel = RulesPanel()
        self.rules_panel.setMinimumWidth(480)
        self.rules_panel.setMaximumWidth(560)
        self.file_list = FileListCard()
        self.file_list.table.addAction(self.act_select_all)
        self.file_list.table.addAction(self.act_remove)
        self.file_list.table.addAction(self.act_undo)
        body.addWidget(self.rules_panel, 0)
        body.addWidget(self.file_list, 1)
        root.addLayout(body, 1)

        root.addWidget(self._build_bottom_bar())
        self.setCentralWidget(root_widget)

        self.status_summary = QLabel("0 个文件")
        self.status_summary.setObjectName("StatusSummary")
        self.statusBar().addPermanentWidget(self.status_summary)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(10)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel(APP_TITLE)
        title.setObjectName("AppTitle")
        subtitle = QLabel("批量重命名 · 预览先行 · 随时可还原")
        subtitle.setObjectName("AppSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        chip = QLabel(f"v{__version__}")
        chip.setObjectName("VersionChip")
        header.addWidget(chip, 0, Qt.AlignTop)
        return header

    def _build_segmented(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Segmented")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_buttons: list[QPushButton] = []
        for index, title in enumerate(TAB_TITLES):
            button = QPushButton(title)
            button.setObjectName("Segment")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            if index == 0:
                button.setChecked(True)
            self.tab_group.addButton(button, index)
            self.tab_buttons.append(button)
            layout.addWidget(button)
        self.tab_group.idClicked.connect(self._switch_tab)
        return frame

    def _build_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("BottomBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        hint = QLabel("所有改名操作执行前都会自动生成 JSON 备份")
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        layout.addStretch(1)

        self.start_button = QPushButton("开始重命名")
        self.start_button.setObjectName("Primary")
        self.start_button.setToolTip("先写入 JSON 备份，再用临时名两阶段改名；失败自动回滚")
        self.start_button.clicked.connect(self._on_start)
        self.cancel_button = QPushButton("取消")
        self.help_button = QPushButton("帮助")
        self.cancel_button.clicked.connect(self._on_cancel)
        self.help_button.clicked.connect(self._show_help)
        layout.addWidget(self.start_button)
        layout.addWidget(self.cancel_button)
        layout.addWidget(self.help_button)
        return bar

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("文件")
        file_menu.addAction(self.act_add_files)
        file_menu.addAction(self.act_add_folder)
        file_menu.addSeparator()
        file_menu.addAction(self.act_import)
        file_menu.addAction(self.act_export)
        self.recent_menu = file_menu.addMenu("最近方案")
        self.recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        file_menu.addAction(self.act_backups)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)

        edit_menu = menu_bar.addMenu("编辑")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_restore)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_select_all)
        edit_menu.addAction(self.act_remove)
        edit_menu.addAction(self.act_clear)

        view_menu = menu_bar.addMenu("视图")
        view_menu.addAction(self.act_sort_natural)
        view_menu.addAction(self.act_sort_name)
        view_menu.addAction(self.act_sort_mtime)
        view_menu.addAction(self.act_sort_taken)
        view_menu.addAction(self.act_sort_size)
        view_menu.addSeparator()
        view_menu.addAction(self.act_focus_filter)
        view_menu.addAction(self.act_clear_filter)

        appearance_menu = menu_bar.addMenu("外观设置")
        appearance_menu.addAction(self.act_theme_light)
        appearance_menu.addAction(self.act_theme_dark)
        appearance_menu.addAction(self.act_theme_system)
        appearance_menu.addSeparator()
        appearance_menu.addAction(self.act_reset_defaults)

        language_menu = menu_bar.addMenu("语言")
        for code in ("zh", "en", "ja"):
            language_menu.addAction(self._language_actions[code])

        help_menu = menu_bar.addMenu("帮助")
        help_menu.addAction(self.act_help)
        help_menu.addAction(self.act_about)

    def _connect_signals(self) -> None:
        self.rules_panel.changed.connect(self._schedule_preview)
        self.rules_panel.changed.connect(self._settings_timer.start)
        self.rules_panel.placeholderRequested.connect(self._insert_placeholder)
        self.rules_panel.metadataRefreshRequested.connect(
            lambda: self._reload_metadata(only_selected=False)
        )
        self.file_list.filesChanged.connect(self._schedule_preview)
        self.file_list.filesChanged.connect(self._settings_timer.start)
        self.file_list.countChanged.connect(self._on_count_changed)
        self.file_list.selectionChanged.connect(self._update_selection_info)
        self.file_list.addRequested.connect(self._add_files)
        self.file_list.filesDropped.connect(self._on_files_dropped)
        self.file_list.addFolderRequested.connect(self._add_folder)
        self.file_list.message.connect(self._show_message)
        self.file_list.metadataRefreshRequested.connect(
            lambda: self._reload_metadata(only_selected=True)
        )
        self.file_list.undoRequested.connect(self._undo_last)
        self.file_list.restoreRequested.connect(
            lambda: self._open_restore_dialog(preselect_latest=True)
        )

    # ------------------------------------------------------------------
    # 预览
    # ------------------------------------------------------------------
    def _schedule_preview(self) -> None:
        self._preview_timer.start()

    def _apply_previews(self) -> None:
        self._start_preview(self.file_list.visible_entries())

    def _start_preview(self, entries: list[FileEntry]) -> None:
        """把预览放到后台线程；拍摄时间读取可能涉及大量文件。"""
        self._preview_generation += 1
        generation = self._preview_generation
        if not entries:
            self._preview_entries = []
            self._preview_pending = False
            self.rules_panel.set_metadata_progress("")
            self.statusBar().clearMessage()
            self._update_status()
            return
        self._preview_entries = entries
        self._preview_pending = True
        self.rules_panel.set_metadata_progress("正在读取元数据…")
        self.statusBar().showMessage("正在读取拍摄时间并生成预览…")
        self._preview_worker.submit(
            generation,
            [entry.path for entry in entries],
            self.rules_panel.ruleset(),
        )

    def _on_previews_ready(self, generation: int, infos: object) -> None:
        if generation != self._preview_generation:
            return
        entries = self._preview_entries
        if not isinstance(infos, list) or len(infos) != len(entries):
            return
        self.file_list.refresh_previews(infos, entries)
        self._preview_pending = False
        self.rules_panel.set_metadata_progress(self._capture_summary(entries))
        self.statusBar().clearMessage()
        self._update_status()
        if self._sort_after_preview is not None:
            key = self._sort_after_preview
            self._sort_after_preview = None
            self.file_list.sort_by_key(key, True)
        self._update_selection_info(len(self.file_list.selected_entries()))

    @staticmethod
    def _capture_summary(entries: list[FileEntry]) -> str:
        if not entries:
            return ""
        exif = sum(1 for entry in entries if entry.taken_source.startswith("EXIF"))
        video = sum(1 for entry in entries if entry.taken_source.startswith("视频"))
        fallback = sum(1 for entry in entries if entry.taken_fallback)
        parts: list[str] = []
        if exif:
            parts.append(i18n.tr("EXIF {count}", count=exif))
        if video:
            parts.append(i18n.tr("视频 {count}", count=video))
        if fallback:
            parts.append(i18n.tr("回退 {count}", count=fallback))
        detail = " · ".join(parts) if parts else i18n.tr("未找到拍摄时间")
        return i18n.tr("已读取 {count} 个文件：{detail}", count=len(entries), detail=detail)

    def _on_preview_progress(self, done: int, total: int) -> None:
        text = f"正在读取元数据 {done}/{total}…"
        self.rules_panel.set_metadata_progress(text)
        self.statusBar().showMessage(text)

    def _on_preview_failed(self, generation: int, message: str) -> None:
        if generation != self._preview_generation:
            return
        self._preview_pending = False
        self.rules_panel.set_metadata_progress("")
        self.statusBar().clearMessage()
        self._show_message(f"预览失败：{message}")

    def _reload_metadata(self, only_selected: bool = False) -> None:
        selected = self.file_list.selected_entries() if only_selected else []
        entries = selected or self.file_list.visible_entries()
        if not entries:
            self._show_message("列表为空，没有可重新读取的文件")
            return
        for entry in entries:
            self.metadata_cache.invalidate(entry.path)
        self._preview_timer.stop()
        self._sort_after_preview = None
        self._start_preview(entries)
        scope = "所选文件" if selected else "全部文件"
        self._show_message(f"已清空{scope}的拍摄时间缓存，正在重新读取…")

    def _sort_by_taken(self) -> None:
        if not self.file_list.visible_entries():
            self._update_status()
            return
        self._preview_timer.stop()
        self._sort_after_preview = "taken"
        self._apply_previews()
        self._show_message("正在读取拍摄时间，读取完成后按拍摄时间排序")

    def wait_for_previews(self, timeout_ms: int = 10000) -> bool:
        """等待后台预览完成，供演示脚本与冒烟测试使用。"""
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < timeout_ms:
            QApplication.processEvents()
            entries = self.file_list.visible_entries()
            settled = (
                not self._preview_pending
                and not self._preview_timer.isActive()
                and all(entry.status != "待预览" for entry in entries)
            )
            if settled:
                return True
            time.sleep(0.01)
        return False

    def wait_for_operation(self, timeout_ms: int = 120000) -> bool:
        """等待当前改名 / 撤销 / 还原任务结束，供演示脚本与集成测试使用。"""
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < timeout_ms:
            QApplication.processEvents()
            if not self._busy:
                return True
            time.sleep(0.01)
        return False

    # ------------------------------------------------------------------
    # 文件与列表操作
    # ------------------------------------------------------------------
    def _add_files(self) -> None:
        paths, _selected = QFileDialog.getOpenFileNames(
            self,
            "添加文件",
            self._last_dir,
            "所有文件 (*.*)",
        )
        if not paths:
            return
        self._last_dir = str(Path(paths[0]).parent)
        self.file_list.add_paths([Path(path) for path in paths])

    def _add_folder(self, include_subfolders: bool | None = None) -> None:
        directory = QFileDialog.getExistingDirectory(self, "添加文件夹", self._last_dir)
        if not directory:
            return
        self._last_dir = directory
        include = (
            self.file_list.include_subfolders()
            if include_subfolders is None
            else bool(include_subfolders)
        )
        self.file_list.add_paths([Path(directory)], recursive=include)

    def _on_files_dropped(self, paths: list[Path]) -> None:
        self.file_list.add_paths(
            paths, recursive=self.file_list.include_subfolders()
        )

    def _select_all(self) -> None:
        self.file_list.table.selectAll()

    def _remove_selected(self) -> None:
        self.file_list.remove_selected()

    def _clear_list(self) -> None:
        self.file_list.clear_all()

    def _focus_filter(self) -> None:
        self.file_list.focus_filter()

    def _clear_filter(self) -> None:
        self.file_list.clear_filter()

    # ------------------------------------------------------------------
    # 配置记忆与方案
    # ------------------------------------------------------------------
    def _load_settings(self) -> None:
        settings = QSettings()
        geometry = settings.value("ui/geometry")
        if geometry is not None:
            try:
                self.restoreGeometry(geometry)
            except (TypeError, ValueError):
                pass
        window_state = settings.value("ui/windowState")
        if window_state is not None:
            try:
                self.restoreState(window_state)
            except (TypeError, ValueError):
                pass
        last_dir = settings.value("ui/lastDir", "", type=str)
        if last_dir:
            self._last_dir = last_dir
        self.file_list.set_include_subfolders(
            settings.value("ui/includeSubfolders", True, type=bool)
        )

        try:
            tab_index = int(settings.value("ui/tab", 0))
        except (TypeError, ValueError):
            tab_index = 0
        if 0 <= tab_index < len(self.tab_buttons):
            self.tab_buttons[tab_index].setChecked(True)
            self.rules_panel.set_page(tab_index)

        raw_rules = settings.value("scheme/rules", "", type=str)
        if raw_rules:
            try:
                rules = RuleSet.from_dict(json.loads(raw_rules))
            except (ValueError, TypeError, json.JSONDecodeError):
                rules = None
            if rules is not None:
                self.rules_panel.set_ruleset(rules)

        extensions = settings.value("scheme/filter", [])
        if isinstance(extensions, str):
            extensions = [extensions]
        if isinstance(extensions, list) and extensions:
            self.file_list.set_filter_extensions([str(item) for item in extensions])

        sort_key = settings.value("scheme/sortKey", "natural", type=str) or "natural"
        ascending = settings.value("scheme/sortAscending", True, type=bool)
        self.file_list.set_sort_state(sort_key, ascending)

    def _save_scheme_settings(self) -> None:
        key, ascending = self.file_list.sort_state()
        settings = QSettings()
        settings.setValue(
            "scheme/rules",
            json.dumps(self.rules_panel.ruleset().to_dict(), ensure_ascii=False),
        )
        settings.setValue("scheme/filter", self.file_list.filter_extensions())
        settings.setValue("scheme/sortKey", key)
        settings.setValue("scheme/sortAscending", ascending)
        settings.sync()

    def _save_settings(self) -> None:
        self._save_scheme_settings()
        settings = QSettings()
        settings.setValue("ui/geometry", self.saveGeometry())
        settings.setValue("ui/windowState", self.saveState())
        settings.setValue("ui/tab", self.rules_panel.current_page())
        settings.setValue("ui/lastDir", self._last_dir)
        settings.setValue(
            "ui/includeSubfolders", self.file_list.include_subfolders()
        )
        settings.sync()

    # ------------------------------------------------------------------
    # 外观与重置
    # ------------------------------------------------------------------
    def _set_theme(self, mode: str) -> None:
        self._theme_mode = mode
        theme.save_theme_mode(mode)
        theme.apply_theme(QApplication.instance(), mode)
        self._sync_theme_actions()
        labels = {
            theme.THEME_LIGHT: "已切换为白天模式",
            theme.THEME_DARK: "已切换为夜间模式",
            theme.THEME_SYSTEM: "外观已跟随系统",
        }
        self._show_message(labels.get(mode, "外观已更新"))

    def _sync_theme_actions(self) -> None:
        action = self._theme_actions.get(self._theme_mode)
        if action is not None:
            action.setChecked(True)

    def _on_system_color_scheme_changed(self, *_args) -> None:
        if self._theme_mode == theme.THEME_SYSTEM:
            theme.apply_theme(QApplication.instance(), theme.THEME_SYSTEM)
            self._sync_theme_actions()

    # ------------------------------------------------------------------
    # 多语言
    # ------------------------------------------------------------------
    def _switch_language(self, code: str) -> None:
        if code not in i18n.LANGUAGES:
            return
        i18n.set_language(code)
        i18n.install_qt_translator(QApplication.instance())
        i18n.translate_widget_tree(self)
        self.file_list.retranslate_language()
        self.rules_panel.retranslate_language()
        self._sync_language_actions()
        self._update_status()
        self._update_selection_info(len(self.file_list.selected_entries()))
        self.menuBar().update()
        self._show_message(
            i18n.tr("语言已切换为 {language}", language=i18n.LANGUAGES[code])
        )

    def _sync_language_actions(self) -> None:
        action = self._language_actions.get(i18n.current_language())
        if action is not None:
            action.setChecked(True)

    def _reset_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            "重置为默认设置",
            "将恢复默认的规则、外观、语言、筛选、排序与窗口布局。\n"
            "列表中的文件和备份 JSON 不会被删除。\n\n继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        QSettings().clear()
        QSettings().sync()
        self._theme_mode = theme.THEME_SYSTEM
        theme.save_theme_mode(theme.THEME_SYSTEM)
        theme.apply_theme(QApplication.instance(), theme.THEME_SYSTEM)
        self._sync_theme_actions()
        self.rules_panel.set_ruleset(RuleSet())
        self.file_list.clear_filter()
        self.file_list.set_sort_state("natural", True)
        self.file_list.set_include_subfolders(True)
        self.tab_buttons[0].setChecked(True)
        self.rules_panel.set_page(0)
        self._last_dir = str(Path.home())
        self.resize(1280, 800)
        self.recent_menu.clear()
        self._settings_timer.stop()
        i18n.set_language("zh")
        i18n.install_qt_translator(QApplication.instance())
        i18n.translate_widget_tree(self)
        self.file_list.retranslate_language()
        self.rules_panel.retranslate_language()
        self._sync_language_actions()
        self._update_status()
        self._update_selection_info(len(self.file_list.selected_entries()))
        self._schedule_preview()
        self._show_message("已恢复默认设置")

    # ------------------------------------------------------------------
    def save_scheme(self, path: Path) -> None:
        sort_key, ascending = self.file_list.sort_state()
        Scheme(
            rules=self.rules_panel.ruleset(),
            filter_extensions=self.file_list.filter_extensions(),
            sort_key=sort_key,
            sort_ascending=ascending,
        ).save(path)

    def _apply_scheme(self, scheme: Scheme) -> None:
        self.rules_panel.set_ruleset(scheme.rules)
        self.file_list.set_filter_extensions(scheme.filter_extensions)
        self.file_list.set_sort_state(scheme.sort_key, scheme.sort_ascending)
        self._schedule_preview()

    def _import_scheme(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "导入方案",
            self._last_dir,
            "重命名方案 (*.bfr.json);;JSON 文件 (*.json);;所有文件 (*.*)",
        )
        if not path:
            return
        try:
            scheme = Scheme.load(path)
        except (OSError, SchemeError) as exc:
            QMessageBox.warning(self, "导入方案", f"无法导入方案：\n{exc}")
            return
        self._apply_scheme(scheme)
        self._remember_scheme(Path(path))
        self._last_dir = str(Path(path).parent)
        self._settings_timer.start()
        self._show_message(f"已导入方案：{Path(path).name}")

    def _export_scheme(self) -> None:
        default = str(Path(self._last_dir) / "重命名方案.bfr.json")
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "导出方案",
            default,
            "重命名方案 (*.bfr.json);;JSON 文件 (*.json)",
        )
        if not path:
            return
        target = Path(path)
        lower = str(target).lower()
        if lower.endswith(".json") and not lower.endswith(".bfr.json"):
            target = Path(str(target)[: -len(".json")] + ".bfr.json")
        elif not lower.endswith(".bfr.json"):
            target = Path(str(target) + ".bfr.json")
        try:
            self.save_scheme(target)
        except OSError as exc:
            QMessageBox.warning(self, "导出方案", f"无法写入方案：\n{exc}")
            return
        self._last_dir = str(target.parent)
        self._remember_scheme(target)
        self._settings_timer.start()
        self._show_message(f"已导出方案：{target.name}")

    def _recent_paths(self) -> list[str]:
        value = QSettings().value("scheme/recent", [])
        if isinstance(value, str):
            return [value] if value else []
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item]

    def _remember_scheme(self, path: Path) -> None:
        target = os.path.normcase(os.path.abspath(str(path)))
        paths = [
            item
            for item in self._recent_paths()
            if os.path.normcase(os.path.abspath(item)) != target
        ]
        paths.insert(0, str(path))
        settings = QSettings()
        settings.setValue("scheme/recent", paths[:8])
        settings.sync()

    def _forget_scheme(self, path: Path) -> None:
        target = os.path.normcase(os.path.abspath(str(path)))
        paths = [
            item
            for item in self._recent_paths()
            if os.path.normcase(os.path.abspath(item)) != target
        ]
        settings = QSettings()
        settings.setValue("scheme/recent", paths)
        settings.sync()

    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.clear()
        paths = self._recent_paths()
        if not paths:
            empty = self.recent_menu.addAction("（暂无）")
            empty.setEnabled(False)
            return
        for path in paths:
            action = QAction(Path(path).name, self)
            action.setToolTip(path)
            action.triggered.connect(
                lambda _checked=False, item=path: self._load_recent_scheme(item)
            )
            self.recent_menu.addAction(action)
        self.recent_menu.addSeparator()
        clear_action = QAction("清除最近记录", self)
        clear_action.triggered.connect(self._clear_recent)
        self.recent_menu.addAction(clear_action)

    def _load_recent_scheme(self, path: str) -> None:
        try:
            scheme = Scheme.load(path)
        except FileNotFoundError:
            QMessageBox.warning(
                self, "最近方案", f"方案文件已不存在：\n{path}"
            )
            self._forget_scheme(Path(path))
            return
        except (OSError, SchemeError) as exc:
            QMessageBox.warning(self, "最近方案", f"无法读取方案：\n{exc}")
            return
        self._apply_scheme(scheme)
        self._remember_scheme(Path(path))
        self._last_dir = str(Path(path).parent)
        self._show_message(f"已载入方案：{Path(path).name}")

    def _clear_recent(self) -> None:
        settings = QSettings()
        settings.setValue("scheme/recent", [])
        settings.sync()
        self._rebuild_recent_menu()

    # ------------------------------------------------------------------
    # 标签页 / 状态
    # ------------------------------------------------------------------
    def _switch_tab(self, index: int) -> None:
        self.rules_panel.set_page(index)

    def _insert_placeholder(self, token: str) -> None:
        self.rules_panel.insert_placeholder(token)
        self.tab_buttons[0].setChecked(True)
        self._schedule_preview()

    def _on_count_changed(self) -> None:
        self._update_status()

    def _update_status(self) -> None:
        total = self.file_list.total_count()
        visible = self.file_list.visible_count()
        entries = self.file_list.visible_entries()
        ready = sum(1 for entry in entries if entry.status in ("就绪", "冲突已处理"))
        conflict = sum(1 for entry in entries if entry.status == "冲突已处理")
        error = sum(1 for entry in entries if entry.status == "错误")
        unchanged = sum(1 for entry in entries if entry.status == "未更改")
        filter_text = i18n.tr("全部") if visible == total else f"{visible}/{total}"
        self.status_summary.setText(
            i18n.tr(
                "{total} 个文件 · 筛选 {filter} · 预计成功 {ready} · "
                "冲突 {conflict} · 错误 {error} · 未更改 {unchanged}",
                total=total,
                filter=filter_text,
                ready=ready,
                conflict=conflict,
                error=error,
                unchanged=unchanged,
            )
        )
        self.start_button.setEnabled(visible > 0 and not self._busy)

    def _update_selection_info(self, _count: int) -> None:
        entries = self.file_list.selected_entries()
        if not entries:
            self.rules_panel.set_selection_info(i18n.tr("未选择文件"))
            return
        if len(entries) > 1:
            self.rules_panel.set_selection_info(
                i18n.tr("已选择 {count} 个文件", count=len(entries))
            )
            return
        entry = entries[0]
        modified = (
            datetime.fromtimestamp(entry.mtime).strftime("%Y-%m-%d %H:%M:%S")
            if entry.mtime
            else i18n.tr("未知")
        )
        if entry.status == "待预览":
            taken_line = i18n.tr("拍摄时间：读取中…")
        elif entry.taken_at is not None:
            moment = datetime.fromtimestamp(entry.taken_at).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            taken_line = i18n.tr(
                "拍摄时间：{time}（{source}）",
                time=moment,
                source=i18n.tr(entry.taken_source or i18n.tr("未知")),
            )
            if entry.taken_raw:
                taken_line += "\n" + i18n.tr(
                    "元数据原文：{raw}", raw=entry.taken_raw
                )
        else:
            taken_line = i18n.tr("拍摄时间：未检测到（命名时回退文件修改时间）")
        tag_lines: list[str] = []
        tags = entry.media_tags
        for label, key in (
            ("标题", "title"),
            ("艺术家 / 导演", "artist"),
            ("专辑 / 系列", "album"),
        ):
            value = tags.get(key)
            if value:
                tag_lines.append(f"{i18n.tr(label)}：{value}")
        meta_parts: list[str] = []
        if tags.get("genre"):
            meta_parts.append(
                f"{i18n.tr('风格')}：{tags['genre']}"
            )
        if tags.get("year"):
            meta_parts.append(f"{i18n.tr('年份')}：{tags['year']}")
        if meta_parts:
            tag_lines.append(" · ".join(meta_parts))
        camera_parts: list[str] = []
        for label, key in (
            ("相机", "camera"),
            ("镜头", "lens"),
            ("ISO", "iso"),
            ("光圈", "aperture"),
        ):
            value = tags.get(key)
            if value:
                camera_parts.append(f"{i18n.tr(label)} {value}")
        if camera_parts:
            tag_lines.append(" · ".join(camera_parts))
        extra = ("\n" + "\n".join(tag_lines)) if tag_lines else ""
        self.rules_panel.set_selection_info(
            i18n.tr("文件：{name}", name=entry.path.name)
            + "\n"
            + i18n.tr(
                "大小：{size} · 修改时间：{modified}",
                size=_format_size(entry.size),
                modified=modified,
            )
            + "\n"
            + taken_line
            + extra
        )

    def _show_message(self, text: str) -> None:
        self.statusBar().showMessage(i18n.tr(text), 5000)

    # ------------------------------------------------------------------
    # 底部 / 菜单动作
    # ------------------------------------------------------------------
    def _on_start(self) -> None:
        if self._busy:
            return
        if not self._ensure_store():
            return
        entries = self.file_list.visible_entries()
        if not entries:
            self._show_message("请先添加要重命名的文件")
            return
        if any(entry.status == "待预览" for entry in entries):
            self._schedule_preview()
            self._show_message("预览尚未完成，请稍候再点击“开始重命名”")
            return

        items: list[RenameItem] = []
        for entry in entries:
            if entry.status == "错误" or not entry.preview:
                continue
            if entry.status == "未更改" or entry.preview == entry.path.name:
                continue
            items.append(
                RenameItem(source=entry.path, target=entry.path.parent / entry.preview)
            )
        if not items:
            self._show_message("没有需要重命名的文件（全部未更改或存在错误）")
            return
        self._start_rename(items)

    # ------------------------------------------------------------------
    # 执行闭环：重命名 / 撤销 / 还原 / 恢复
    # ------------------------------------------------------------------
    def _start_rename(self, items: list[RenameItem]) -> None:
        rules = self.rules_panel.ruleset()
        store = self.backup_store
        assert store is not None

        def task(progress, should_cancel):
            executor = RenameExecutor(
                store, progress=progress, should_cancel=should_cancel
            )
            return executor.execute(items, rules)

        self._run_operation(
            "正在重命名",
            f"共 {len(items)} 个文件，按“写入备份 → 临时名 → 目标名”执行。",
            task,
            self._on_rename_done,
        )

    def _on_rename_done(self, result: BatchResult) -> None:
        self._apply_operation_items(result.items, "成功")
        self._update_status()
        self._show_batch_result(
            result, "重命名完成", allow_undo=result.success > 0
        )

    def _undo_last(self) -> None:
        if self._busy or not self._ensure_store():
            return
        try:
            record = latest_restorable(self.backup_store)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "撤销", f"读取备份失败：{exc}")
            return
        if record is None:
            QMessageBox.information(
                self, "撤销上一次重命名", "没有可撤销的重命名记录。"
            )
            return
        ok_items = sum(1 for item in record.items if item.status == STATUS_OK)
        if ok_items == 0:
            QMessageBox.information(
                self, "撤销上一次重命名", "上一次重命名没有成功项，无需撤销。"
            )
            return
        answer = QMessageBox.question(
            self,
            "撤销上一次重命名",
            f"批次：{record.created_at[:19].replace('T', ' ')}\n"
            f"将把 {ok_items} 个文件还原到原名称。\n"
            "原位置被占用时会跳过，不会覆盖。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            self._undo_batch(record.batch_id, confirm=False)

    def _undo_batch(self, batch_id: str, confirm: bool = True) -> None:
        if self._busy or not self._ensure_store():
            return
        store = self.backup_store
        assert store is not None
        try:
            record = store.find(batch_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "撤销", f"读取备份失败：{exc}")
            return
        if record is None:
            QMessageBox.warning(self, "撤销", f"找不到备份记录：{batch_id}")
            return
        ok_items = sum(1 for item in record.items if item.status == STATUS_OK)
        if ok_items == 0:
            QMessageBox.information(self, "撤销", "该批次没有成功改名的文件。")
            return
        if confirm:
            answer = QMessageBox.question(
                self,
                "撤销重命名",
                f"将把批次 {batch_id} 的 {ok_items} 个文件还原到原名称。\n"
                "原位置被占用时会跳过，不会覆盖。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return

        def task(progress, should_cancel):
            executor = RenameExecutor(
                store, progress=progress, should_cancel=should_cancel
            )
            return restore_batch(
                store, batch_id, conflict=CONFLICT_SKIP, executor=executor
            )

        self._run_operation(
            "正在撤销",
            f"正在把批次 {batch_id} 的 {ok_items} 个文件还原到原名称。",
            task,
            self._on_undo_done,
        )

    def _on_undo_done(self, outcome: RestoreOutcome) -> None:
        self._apply_operation_items(outcome.result.items, "已还原")
        self._update_status()
        self._show_restore_result(outcome, "撤销完成")

    def _open_restore_dialog(self, preselect_latest: bool = True) -> None:
        if self._busy or not self._ensure_store():
            return
        dialog = RestoreDialog(
            self.backup_store, self, preselect_latest=preselect_latest
        )
        if dialog.exec() == QDialog.Accepted and dialog.batch_id:
            self._restore_batch(dialog.batch_id, dialog.conflict)

    def _restore_batch(
        self, batch_id: str, conflict: str, confirm: bool = False
    ) -> None:
        if self._busy or not self._ensure_store():
            return
        store = self.backup_store
        assert store is not None
        try:
            record = store.find(batch_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "一键还原", f"读取备份失败：{exc}")
            return
        if record is None:
            QMessageBox.warning(self, "一键还原", f"找不到备份记录：{batch_id}")
            return
        ok_items = sum(1 for item in record.items if item.status == STATUS_OK)
        if ok_items == 0:
            QMessageBox.information(self, "一键还原", "该批次没有可还原的文件。")
            return
        if confirm:
            policy = (
                "跳过被占用的原位置"
                if conflict == CONFLICT_SKIP
                else "原位置被占用时自动加序号"
            )
            answer = QMessageBox.question(
                self,
                "确认还原",
                f"将还原批次 {batch_id} 的 {ok_items} 个文件；{policy}。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return

        def task(progress, should_cancel):
            executor = RenameExecutor(
                store, progress=progress, should_cancel=should_cancel
            )
            return restore_batch(
                store, batch_id, conflict=conflict, executor=executor
            )

        self._run_operation(
            "正在还原",
            f"正在还原批次 {batch_id} 的 {ok_items} 个文件。",
            task,
            self._on_restore_done,
        )

    def _on_restore_done(self, outcome: RestoreOutcome) -> None:
        self._apply_operation_items(outcome.result.items, "已还原")
        self._update_status()
        self._show_restore_result(outcome, "还原完成")

    # ------------------------------------------------------------------
    # 后台任务与结果展示
    # ------------------------------------------------------------------
    def _run_operation(self, title, message, task, on_done) -> None:
        if self._busy:
            return
        self._set_busy(True)
        dialog = ProgressDialog(self, title, message)
        worker = TaskWorker(task, self)
        self._progress_dialog = dialog
        self._worker = worker
        dialog.cancelRequested.connect(worker.cancel)
        worker.progress.connect(dialog.update_progress)
        worker.completed.connect(
            lambda result: self._operation_done(result, on_done)
        )
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(worker.deleteLater)
        dialog.show()
        worker.start()

    def _operation_done(self, result, on_done) -> None:
        self._finish_operation()
        on_done(result)

    def _operation_failed(self, message: str) -> None:
        self._finish_operation()
        QMessageBox.critical(
            self,
            "操作失败",
            f"执行过程中出现错误：\n{message}\n\n"
            "如果已有文件被改动，请重新启动程序，启动时会提示恢复未完成的批次；"
            "也可以在“编辑 → 一键还原”中查看备份记录。",
        )

    def _finish_operation(self) -> None:
        dialog = self._progress_dialog
        self._progress_dialog = None
        if dialog is not None:
            dialog.finish()
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.rules_panel.setEnabled(not busy)
        self.file_list.setEnabled(not busy)
        for action in (
            self.act_add_files,
            self.act_add_folder,
            self.act_import,
            self.act_export,
            self.act_clear,
            self.act_remove,
        ):
            action.setEnabled(not busy)
        self._refresh_edit_actions()
        self._update_status()

    def _refresh_edit_actions(self) -> None:
        available = (not self._busy) and self.backup_store is not None
        self.act_undo.setEnabled(available and self._has_undo())
        self.act_restore.setEnabled(available)
        self.act_backups.setEnabled(available)

    def _has_undo(self) -> bool:
        if self.backup_store is None:
            return False
        try:
            return latest_restorable(self.backup_store) is not None
        except Exception:  # noqa: BLE001
            return False

    def _ensure_store(self) -> bool:
        if self.backup_store is not None:
            return True
        try:
            self.backup_store = BackupStore()
        except BackupError as exc:
            QMessageBox.critical(
                self,
                "备份目录不可用",
                f"无法读取或创建备份目录：{exc}\n\n"
                "为避免改名后无法还原，已禁用执行操作。",
            )
            return False
        self._backup_error = ""
        return True

    def _apply_operation_items(self, items, success_text: str) -> None:
        succeeded: dict[str, Path] = {}
        failed: dict[str, str] = {}
        skipped: dict[str, str] = {}
        for item in items:
            key = os.path.normcase(os.path.abspath(str(item.source)))
            if item.status == STATUS_OK:
                succeeded[key] = item.target
            elif item.status == STATUS_FAILED:
                failed[key] = item.error or "执行失败"
            else:
                skipped[key] = item.error or ""
        self.file_list.apply_operation_result(
            succeeded, failed, skipped, success_text
        )

    def _show_batch_result(
        self, result: BatchResult, title: str, allow_undo: bool = False
    ) -> None:
        lines = [
            i18n.tr(
                "成功 {success} 个 · 失败 {failed} 个 · 跳过 {skipped} 个",
                success=result.success,
                failed=result.failed,
                skipped=result.skipped,
            )
        ]
        if result.note:
            lines.append(i18n.tr(result.note))
        details = [
            f"{item.source.name} → {item.target.name}\n    {item.error}"
            for item in result.errors[:20]
        ]
        if len(result.errors) > 20:
            details.append(
                i18n.tr(
                    "…还有 {count} 条失败记录", count=len(result.errors) - 20
                )
            )
        dialog = ResultDialog(
            self, i18n.tr(title), lines, details, result.backup_path, allow_undo
        )
        if allow_undo:
            dialog.undoRequested.connect(
                lambda batch_id=result.batch_id: self._undo_batch(
                    batch_id, confirm=False
                )
            )
        dialog.open()

    def _show_restore_result(self, outcome: RestoreOutcome, title: str) -> None:
        result = outcome.result
        lines = [
            i18n.tr(
                "成功 {success} 个 · 失败 {failed} 个 · 跳过 {skipped} 个",
                success=result.success,
                failed=result.failed,
                skipped=result.skipped,
            )
        ]
        if outcome.plan.skipped:
            lines.append(
                i18n.tr(
                    "原位置被占用而跳过 {count} 个",
                    count=len(outcome.plan.skipped),
                )
            )
        if outcome.plan.missing:
            lines.append(
                i18n.tr(
                    "文件已不存在 {count} 个", count=len(outcome.plan.missing)
                )
            )
        if not outcome.fully_restored:
            lines.append(
                i18n.tr("该批次没有完全还原，可稍后重试剩余文件。")
            )
        details = [
            f"{item.source.name} → {item.target.name}\n    {item.error}"
            for item in result.errors[:20]
        ]
        for new_path, reason in outcome.plan.skipped[:10]:
            details.append(f"{Path(new_path).name}：{reason}")
        for missing in outcome.plan.missing[:10]:
            details.append(f"{Path(missing).name}：{i18n.tr('文件已不存在')}")
        dialog = ResultDialog(
            self, i18n.tr(title), lines, details, result.backup_path, False
        )
        dialog.open()

    def _check_startup_recovery(self) -> None:
        if self.backup_store is None:
            return
        try:
            records = self.backup_store.unfinished()
        except Exception:  # noqa: BLE001
            return
        if not records:
            return
        lines = [
            f"{record.created_at[:19].replace('T', ' ')} · "
            f"{len(record.items)} 个文件 · {record.state}"
            for record in records[:5]
        ]
        text = (
            "上次重命名没有正常结束，可以把已改名或暂存的文件还原到原路径：\n\n"
            + "\n".join(lines)
            + "\n\n是否立即还原？"
        )
        answer = QMessageBox.question(
            self,
            "发现未完成的重命名",
            text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            self._show_message(
                "已保留未完成批次，可在“编辑 → 一键还原”查看备份。"
            )
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            outcomes = recover_incomplete(self.backup_store)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "恢复失败", f"恢复过程中出错：{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        restored = sum(outcome.restored for outcome in outcomes)
        problems = [
            message for outcome in outcomes for message in outcome.errors
        ]
        self._refresh_edit_actions()
        detail = ""
        if problems:
            detail = "\n\n未解决的问题：\n" + "\n".join(problems[:10])
        QMessageBox.information(
            self,
            "恢复完成",
            f"已还原 {restored} 个文件。{detail}",
        )

    def _on_cancel(self) -> None:
        if self._busy:
            self._show_message("正在执行改名，请等待完成或点击进度对话框的“取消”。")
            return
        if self.file_list.total_count() == 0:
            self.close()
            return
        answer = QMessageBox.question(
            self,
            "确认退出",
            "列表里还有未处理的文件，确定要退出吗？\n"
            "列表本身不会被保存，磁盘上的文件不会受影响。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.close()

    def _show_help(self) -> None:
        dialog = HelpDialog(self)
        dialog.exec()

    def _show_about(self) -> None:
        import platform

        from PySide6 import __version__ as pyside_version

        try:
            backup_path = str(backup_dir())
        except OSError:
            backup_path = f"不可用（{self._backup_error or '无写入权限'}）"
        QMessageBox.about(
            self,
            "关于 批量文件改名",
            f"<b>{APP_TITLE}</b> v{__version__}<br><br>"
            "批量重命名工具，预览先行，改名前后均有备份。<br>"
            f"Python {platform.python_version()} · PySide6 {pyside_version}<br><br>"
            f"备份目录：<br>{backup_path}<br><br>"
            "快捷键：Ctrl+O 添加 · Ctrl+Z 撤销 · Ctrl+S 导出方案 · F1 帮助",
        )

    # ------------------------------------------------------------------
    # 窗口拖放
    # ------------------------------------------------------------------
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
            self.file_list.add_paths(
                paths, recursive=self.file_list.include_subfolders()
            )
            event.acceptProposedAction()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._busy:
            self._show_message("正在执行改名，请等待完成或取消后再退出。")
            event.ignore()
            return
        self._settings_timer.stop()
        self._save_settings()
        self._preview_timer.stop()
        self._preview_worker.stop()
        super().closeEvent(event)
