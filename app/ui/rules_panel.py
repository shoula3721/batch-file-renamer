"""四个规则标签页：整体 / 替换 / 添加删除 / 元数据。"""
from __future__ import annotations

import re
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.engine.rules import (
    CASE_OPTIONS,
    LETTER_CASE_OPTIONS,
    AddRemoveRule,
    MetadataRule,
    OverallRule,
    ReplaceRule,
    RuleSet,
)
from app.i18n import tr
from app.ui.widgets import Card, Divider, HintLabel, MutedLabel, SectionTitle

TAB_TITLES = ("整体", "替换", "添加删除", "元数据")

TAB_HINTS = {
    "整体": "命名规则、编号、扩展名与大小写。规则为空时保留原文件名。",
    "替换": "先做普通文本或正则替换，再套用命名规则。",
    "添加删除": "在文件名前后添加内容，或按位置插入、删除字符。",
    "元数据": "把拍摄日期、文件时间或文件属性插入命名规则。",
}

PLACEHOLDERS = (
    ("{date}", "日期：2026-11-21（格式见上方设置）"),
    ("{time}", "时间：214000"),
    ("{datetime}", "日期时间：2026-11-21_214000"),
    ("{year}", "年份"),
    ("{month}", "月份"),
    ("{day}", "日"),
    ("{hour}", "小时"),
    ("{min}", "分钟"),
    ("{sec}", "秒"),
    ("{name}", "原文件名（不含扩展名）"),
    ("{ext}", "扩展名"),
    ("{size}", "文件大小"),
    ("{mtime}", "文件修改时间"),
    ("{ctime}", "文件创建时间"),
    ("{n}", "编号（同 #）"),
    ("{exif}", "拍摄时间原文（EXIF / 视频）"),
    ("{title}", "标题 / 曲名"),
    ("{artist}", "艺术家 / 导演"),
    ("{album}", "专辑 / 系列"),
    ("{genre}", "风格 / 分类"),
    ("{tag_year}", "发布年份"),
    ("{camera}", "相机型号"),
    ("{lens}", "镜头"),
    ("{iso}", "ISO 感光度"),
    ("{aperture}", "光圈，如 f/2.8"),
)

DATE_SOURCES = (
    ("exif", "拍摄时间（EXIF / 视频）"),
    ("mtime", "文件修改时间"),
    ("ctime", "文件创建时间"),
)

DATE_FORMATS = (
    ("date", "2026-11-21"),
    ("compact", "20261121"),
    ("datetime", "2026-11-21_214000"),
    ("custom", "自定义"),
)

TIMEZONES = (
    ("original", "按 EXIF 原始时间"),
    ("local", "转换为本地时间"),
)


class RulePage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("PageContent")
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(0, 0, 12, 0)
        self.layout.setSpacing(12)
        self.setWidget(self.content)


class RulesPanel(Card):
    changed = Signal()
    placeholderRequested = Signal(str)
    metadataRefreshRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._updating = False
        self._build_ui()
        self.set_page(0)
        self._validate_regex()
        self._update_format_preview()

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        self.title_label = SectionTitle("整体")
        self.hint_label = MutedLabel(TAB_HINTS["整体"])
        layout.addWidget(self.title_label)
        layout.addWidget(self.hint_label)
        layout.addWidget(Divider())

        self.pages = QStackedWidget()
        self.overall_page = self._build_overall_page()
        self.replace_page = self._build_replace_page()
        self.addremove_page = self._build_addremove_page()
        self.metadata_page = self._build_metadata_page()
        for page in (self.overall_page, self.replace_page, self.addremove_page, self.metadata_page):
            self.pages.addWidget(page)
        for combo in self.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(
                QComboBox.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMinimumContentsLength(6)
        layout.addWidget(self.pages, 1)

    # ---------- 整体 ----------
    def _build_overall_page(self) -> RulePage:
        page = RulePage()
        layout = page.layout

        layout.addWidget(SectionTitle("命名规则"))
        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("例如：A_#，留空则保留原名")
        self.template_edit.setClearButtonEnabled(True)
        layout.addWidget(self.template_edit)
        layout.addWidget(
            HintLabel(
                "使用 * 插入原始文件名，使用 # 插入编号；\n"
                "点击下方占位符可插入日期、拍摄时间、文件大小等内容。"
            )
        )

        layout.addWidget(Divider())
        layout.addWidget(SectionTitle("插入占位符"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(3, 1)
        for index, (token, tip) in enumerate(PLACEHOLDERS):
            button = QPushButton(token)
            button.setObjectName("PlaceholderButton")
            button.setToolTip(tip)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, value=token: self.placeholderRequested.emit(value)
            )
            grid.addWidget(button, index // 3, index % 3)
        layout.addLayout(grid)
        layout.addWidget(
            HintLabel("点击占位符会插入到上方命名规则的光标位置。")
        )

        layout.addWidget(Divider())
        layout.addWidget(SectionTitle("编号"))
        number_form = self._form()
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 999999)
        self.start_spin.setValue(1)
        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 9999)
        self.step_spin.setValue(1)
        self.digits_spin = QSpinBox()
        self.digits_spin.setRange(1, 12)
        self.digits_spin.setValue(1)
        number_form.addRow("开始于", self.start_spin)
        number_form.addRow("增量", self.step_spin)
        number_form.addRow("位数", self.digits_spin)

        number_flags = QVBoxLayout()
        number_flags.setSpacing(6)
        flags_row = QHBoxLayout()
        flags_row.setSpacing(12)
        self.pad_check = QCheckBox("不足位补齐")
        self.pad_check.setChecked(True)
        self.letter_check = QCheckBox("字母编号")
        self.letter_case_combo = QComboBox()
        for key, label in LETTER_CASE_OPTIONS.items():
            self.letter_case_combo.addItem(label, key)
        self.letter_case_combo.setEnabled(False)
        flags_row.addWidget(self.pad_check)
        flags_row.addWidget(self.letter_check)
        flags_row.addStretch(1)
        number_flags.addLayout(flags_row)
        number_flags.addWidget(self.letter_case_combo)
        number_form.addRow("", self._wrap(number_flags))
        layout.addLayout(number_form)

        layout.addWidget(Divider())
        layout.addWidget(SectionTitle("扩展名"))
        extension_row = QHBoxLayout()
        extension_row.setSpacing(8)
        self.change_ext_check = QCheckBox("扩展名改成")
        self.ext_edit = QLineEdit()
        self.ext_edit.setPlaceholderText("mp4")
        self.ext_edit.setMaximumWidth(120)
        self.ext_edit.setEnabled(False)
        extension_row.addWidget(self.change_ext_check)
        extension_row.addWidget(self.ext_edit)
        extension_row.addStretch(1)
        layout.addLayout(extension_row)

        layout.addWidget(Divider())
        layout.addWidget(SectionTitle("文件名称选项"))
        self.case_combo = QComboBox()
        for key, label in CASE_OPTIONS.items():
            self.case_combo.addItem(label, key)
        layout.addWidget(self.case_combo)

        self.auto_resolve_check = QCheckBox("自动解决冲突")
        self.auto_resolve_check.setToolTip("命名冲突时自动追加 (1)、(2)…")
        self.auto_resolve_check.setChecked(True)
        layout.addWidget(self.auto_resolve_check)
        layout.addStretch(1)

        self.template_edit.textChanged.connect(self._mark_changed)
        for spin in (self.start_spin, self.step_spin, self.digits_spin):
            spin.valueChanged.connect(self._mark_changed)
        self.pad_check.toggled.connect(self._mark_changed)
        self.letter_check.toggled.connect(self._on_letter_toggled)
        self.letter_case_combo.currentIndexChanged.connect(self._mark_changed)
        self.change_ext_check.toggled.connect(self._on_ext_toggled)
        self.ext_edit.textChanged.connect(self._mark_changed)
        self.case_combo.currentIndexChanged.connect(self._mark_changed)
        self.auto_resolve_check.toggled.connect(self._mark_changed)
        return page

    # ---------- 替换 ----------
    def _build_replace_page(self) -> RulePage:
        page = RulePage()
        layout = page.layout

        layout.addWidget(SectionTitle("替换文件名中的字符"))
        form = self._form()
        self.replace_old_edit = QLineEdit()
        self.replace_old_edit.setPlaceholderText("要查找的文本")
        self.replace_new_edit = QLineEdit()
        self.replace_new_edit.setPlaceholderText("替换成（可留空表示删除）")
        form.addRow("把", self.replace_old_edit)
        form.addRow("替换成", self.replace_new_edit)
        layout.addLayout(form)

        self.regex_check = QCheckBox("使用正则表达式")
        self.case_sensitive_check = QCheckBox("区分大小写")
        self.case_sensitive_check.setChecked(True)
        self.first_only_check = QCheckBox("仅替换首次匹配")
        self.include_ext_check = QCheckBox("包含扩展名")
        for check in (
            self.regex_check,
            self.case_sensitive_check,
            self.first_only_check,
            self.include_ext_check,
        ):
            layout.addWidget(check)

        self.regex_status = QLabel("")
        self.regex_status.setObjectName("Hint")
        self.regex_status.setWordWrap(True)
        layout.addWidget(self.regex_status)
        layout.addWidget(
            HintLabel(
                "正则示例：^IMG_(\\d+) → 照片_$1\n"
                "支持 $1、\\1 或 ${name} 形式的捕获组引用。"
            )
        )
        layout.addStretch(1)

        self.replace_old_edit.textChanged.connect(self._on_replace_changed)
        self.replace_new_edit.textChanged.connect(self._mark_changed)
        self.regex_check.toggled.connect(self._on_replace_changed)
        self.case_sensitive_check.toggled.connect(self._on_replace_changed)
        self.first_only_check.toggled.connect(self._mark_changed)
        self.include_ext_check.toggled.connect(self._mark_changed)
        return page

    # ---------- 添加删除 ----------
    def _build_addremove_page(self) -> RulePage:
        page = RulePage()
        layout = page.layout

        layout.addWidget(SectionTitle("添加"))
        form = self._form()
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("添加在文件名最前面")
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("添加在文件名最后面")
        form.addRow("文件名前添加", self.prefix_edit)
        form.addRow("文件名后添加", self.suffix_edit)

        self.insert_check = QCheckBox("扩展添加")
        form.addRow("", self.insert_check)
        self.insert_pos_spin = QSpinBox()
        self.insert_pos_spin.setRange(1, 9999)
        self.insert_pos_spin.setValue(1)
        self.insert_text_edit = QLineEdit()
        self.insert_text_edit.setPlaceholderText("要插入的字符串")
        self.insert_pos_spin.setEnabled(False)
        self.insert_text_edit.setEnabled(False)
        form.addRow("从文件名第", self._with_suffix(self.insert_pos_spin, "个字符开始"))
        form.addRow("添加字符串", self.insert_text_edit)
        layout.addLayout(form)

        layout.addWidget(Divider())
        layout.addWidget(SectionTitle("删除"))
        form2 = self._form()
        self.delete_text_edit = QLineEdit()
        self.delete_text_edit.setPlaceholderText("删除文件名中所有匹配文本")
        form2.addRow("删除文件名中的", self.delete_text_edit)
        self.cut_check = QCheckBox("扩展删除")
        form2.addRow("", self.cut_check)
        self.cut_pos_spin = QSpinBox()
        self.cut_pos_spin.setRange(1, 9999)
        self.cut_pos_spin.setValue(1)
        self.cut_count_spin = QSpinBox()
        self.cut_count_spin.setRange(1, 9999)
        self.cut_count_spin.setValue(1)
        self.cut_pos_spin.setEnabled(False)
        self.cut_count_spin.setEnabled(False)
        form2.addRow("从文件名第", self._with_suffix(self.cut_pos_spin, "个字符开始"))
        form2.addRow("共删除", self._with_suffix(self.cut_count_spin, "个字符"))
        layout.addLayout(form2)
        layout.addStretch(1)

        self.prefix_edit.textChanged.connect(self._mark_changed)
        self.suffix_edit.textChanged.connect(self._mark_changed)
        self.insert_check.toggled.connect(self._on_insert_toggled)
        self.insert_pos_spin.valueChanged.connect(self._mark_changed)
        self.insert_text_edit.textChanged.connect(self._mark_changed)
        self.delete_text_edit.textChanged.connect(self._mark_changed)
        self.cut_check.toggled.connect(self._on_cut_toggled)
        self.cut_pos_spin.valueChanged.connect(self._mark_changed)
        self.cut_count_spin.valueChanged.connect(self._mark_changed)
        return page

    # ---------- 元数据 ----------
    def _build_metadata_page(self) -> RulePage:
        page = RulePage()
        page.layout.setSpacing(8)
        layout = page.layout

        layout.addWidget(SectionTitle("日期来源"))
        form = self._form()
        form.setVerticalSpacing(6)
        self.date_source_combo = QComboBox()
        for key, label in DATE_SOURCES:
            self.date_source_combo.addItem(label, key)
        self.date_format_combo = QComboBox()
        for key, label in DATE_FORMATS:
            self.date_format_combo.addItem(label, key)
        self.custom_format_edit = QLineEdit()
        self.custom_format_edit.setPlaceholderText("%Y-%m-%d_%H%M%S")
        self.custom_format_edit.setEnabled(False)
        self.timezone_combo = QComboBox()
        for key, label in TIMEZONES:
            self.timezone_combo.addItem(label, key)
        self.timezone_combo.setToolTip(
            "EXIF 时间通常没有时区信息，默认保持原始值；视频 mvhd 是 UTC，"
            "选择“转换为本地时间”会按系统时区转换。"
        )
        form.addRow("日期来源", self.date_source_combo)
        form.addRow("日期格式", self.date_format_combo)
        form.addRow("自定义格式", self.custom_format_edit)
        form.addRow("时区", self.timezone_combo)
        layout.addLayout(form)

        self.format_preview = QLabel("")
        self.format_preview.setObjectName("Hint")
        layout.addWidget(self.format_preview)

        layout.addWidget(
            HintLabel(
                "优先读取 EXIF 与视频 mvhd 时间；找不到时自动回退文件修改时间，"
                "并在“拍摄时间”列用 ⓘ 标出。"
            )
        )

        refresh_row = QHBoxLayout()
        refresh_row.setSpacing(8)
        self.metadata_refresh_button = QPushButton("重新读取元数据")
        self.metadata_refresh_button.setToolTip(
            "清空拍摄时间缓存，重新读取列表中全部文件（文件被外部修改后使用）"
        )
        self.metadata_refresh_button.clicked.connect(
            lambda: self.metadataRefreshRequested.emit()
        )
        self.metadata_progress = QLabel("")
        self.metadata_progress.setObjectName("Hint")
        self.metadata_progress.setWordWrap(True)
        refresh_row.addWidget(self.metadata_refresh_button)
        refresh_row.addWidget(self.metadata_progress, 1)
        layout.addLayout(refresh_row)

        layout.addWidget(Divider())
        layout.addWidget(SectionTitle("当前文件"))
        self.selection_info = QLabel("未选择文件")
        self.selection_info.setObjectName("Hint")
        self.selection_info.setWordWrap(True)
        self.selection_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.selection_info)
        layout.addStretch(1)

        self.date_source_combo.currentIndexChanged.connect(self._on_metadata_changed)
        self.date_format_combo.currentIndexChanged.connect(self._on_metadata_changed)
        self.custom_format_edit.textChanged.connect(self._on_metadata_changed)
        self.timezone_combo.currentIndexChanged.connect(self._on_metadata_changed)
        return page

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def set_page(self, index: int) -> None:
        index = max(0, min(index, len(TAB_TITLES) - 1))
        self.pages.setCurrentIndex(index)
        self.title_label.setText(tr(TAB_TITLES[index]))
        self.hint_label.setText(tr(TAB_HINTS[TAB_TITLES[index]]))

    def retranslate_language(self) -> None:
        self.set_page(self.current_page())
        self._validate_regex()
        self._update_format_preview()

    def current_page(self) -> int:
        return self.pages.currentIndex()

    def ruleset(self) -> RuleSet:
        return RuleSet(
            add_remove=AddRemoveRule(
                prefix=self.prefix_edit.text(),
                suffix=self.suffix_edit.text(),
                insert_enabled=self.insert_check.isChecked(),
                insert_position=self.insert_pos_spin.value(),
                insert_text=self.insert_text_edit.text(),
                delete_text=self.delete_text_edit.text(),
                cut_enabled=self.cut_check.isChecked(),
                cut_position=self.cut_pos_spin.value(),
                cut_count=self.cut_count_spin.value(),
            ),
            replace=ReplaceRule(
                old=self.replace_old_edit.text(),
                new=self.replace_new_edit.text(),
                use_regex=self.regex_check.isChecked(),
                case_sensitive=self.case_sensitive_check.isChecked(),
                first_only=self.first_only_check.isChecked(),
                include_extension=self.include_ext_check.isChecked(),
            ),
            overall=OverallRule(
                template=self.template_edit.text(),
                start=self.start_spin.value(),
                step=self.step_spin.value(),
                digits=self.digits_spin.value(),
                pad=self.pad_check.isChecked(),
                letter_mode=self.letter_check.isChecked(),
                letter_case=self.letter_case_combo.currentData() or "lower",
                change_extension=self.change_ext_check.isChecked(),
                new_extension=self.ext_edit.text(),
                case_option=self.case_combo.currentData() or "none",
                auto_resolve=self.auto_resolve_check.isChecked(),
            ),
            metadata=self.metadata_rule(),
        )

    def metadata_rule(self) -> MetadataRule:
        return MetadataRule(
            date_source=self.date_source_combo.currentData() or "exif",
            date_format=self.date_format_combo.currentData() or "date",
            custom_format=self.custom_format_edit.text(),
            timezone=self.timezone_combo.currentData() or "original",
        )

    def set_ruleset(self, rules: RuleSet) -> None:
        self._updating = True
        try:
            overall = rules.overall
            self.template_edit.setText(overall.template)
            self.start_spin.setValue(overall.start)
            self.step_spin.setValue(overall.step)
            self.digits_spin.setValue(overall.digits)
            self.pad_check.setChecked(overall.pad)
            self.letter_check.setChecked(overall.letter_mode)
            self._set_combo_data(self.letter_case_combo, overall.letter_case)
            self.letter_case_combo.setEnabled(overall.letter_mode)
            self.change_ext_check.setChecked(overall.change_extension)
            self.ext_edit.setText(overall.new_extension)
            self.ext_edit.setEnabled(overall.change_extension)
            self._set_combo_data(self.case_combo, overall.case_option)
            self.auto_resolve_check.setChecked(overall.auto_resolve)

            add_remove = rules.add_remove
            self.prefix_edit.setText(add_remove.prefix)
            self.suffix_edit.setText(add_remove.suffix)
            self.insert_check.setChecked(add_remove.insert_enabled)
            self.insert_pos_spin.setValue(add_remove.insert_position)
            self.insert_text_edit.setText(add_remove.insert_text)
            self.insert_pos_spin.setEnabled(add_remove.insert_enabled)
            self.insert_text_edit.setEnabled(add_remove.insert_enabled)
            self.delete_text_edit.setText(add_remove.delete_text)
            self.cut_check.setChecked(add_remove.cut_enabled)
            self.cut_pos_spin.setValue(add_remove.cut_position)
            self.cut_count_spin.setValue(add_remove.cut_count)
            self.cut_pos_spin.setEnabled(add_remove.cut_enabled)
            self.cut_count_spin.setEnabled(add_remove.cut_enabled)

            replace = rules.replace
            self.replace_old_edit.setText(replace.old)
            self.replace_new_edit.setText(replace.new)
            self.regex_check.setChecked(replace.use_regex)
            self.case_sensitive_check.setChecked(replace.case_sensitive)
            self.first_only_check.setChecked(replace.first_only)
            self.include_ext_check.setChecked(replace.include_extension)

            metadata = rules.metadata
            self._set_combo_data(self.date_source_combo, metadata.date_source)
            self._set_combo_data(self.date_format_combo, metadata.date_format)
            self.custom_format_edit.setText(metadata.custom_format)
            self.custom_format_edit.setEnabled(metadata.date_format == "custom")
            self._set_combo_data(self.timezone_combo, metadata.timezone)
        finally:
            self._updating = False
        self._validate_regex()
        self._update_format_preview()
        self.changed.emit()

    def insert_placeholder(self, token: str) -> None:
        edit = self.template_edit
        text = edit.text()
        start = edit.selectionStart()
        end = edit.selectionEnd()
        if start < 0:
            start = end = len(text)
        edit.setText(text[:start] + token + text[end:])
        edit.setCursorPosition(start + len(token))
        edit.setFocus()
        self.set_page(0)

    def set_selection_info(self, text: str) -> None:
        self.selection_info.setText(text)

    def set_metadata_progress(self, text: str) -> None:
        self.metadata_progress.setText(text)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    @staticmethod
    def _form() -> QFormLayout:
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return form

    @staticmethod
    def _wrap(layout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        return widget

    @staticmethod
    def _with_suffix(widget: QWidget, suffix: str) -> QWidget:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(widget)
        row.addWidget(QLabel(suffix))
        row.addStretch(1)
        return RulesPanel._wrap(row)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _mark_changed(self, *_args) -> None:
        if not self._updating:
            self.changed.emit()

    def _on_letter_toggled(self, checked: bool) -> None:
        self.letter_case_combo.setEnabled(checked)
        self._mark_changed()

    def _on_ext_toggled(self, checked: bool) -> None:
        self.ext_edit.setEnabled(checked)
        if checked and not self.ext_edit.text():
            self.ext_edit.setFocus()
        self._mark_changed()

    def _on_insert_toggled(self, checked: bool) -> None:
        self.insert_pos_spin.setEnabled(checked)
        self.insert_text_edit.setEnabled(checked)
        if checked and not self.insert_text_edit.text():
            self.insert_text_edit.setFocus()
        self._mark_changed()

    def _on_cut_toggled(self, checked: bool) -> None:
        self.cut_pos_spin.setEnabled(checked)
        self.cut_count_spin.setEnabled(checked)
        self._mark_changed()

    def _on_replace_changed(self, *_args) -> None:
        self._validate_regex()
        self._mark_changed()

    def _validate_regex(self) -> None:
        pattern = self.replace_old_edit.text()
        if not self.regex_check.isChecked() or not pattern:
            self.regex_status.setObjectName("Hint")
            self.regex_status.setText("")
        else:
            try:
                re.compile(pattern, 0 if self.case_sensitive_check.isChecked() else re.IGNORECASE)
            except re.error as exc:
                self.regex_status.setObjectName("DangerText")
                self.regex_status.setText(tr("正则表达式无效：{error}", error=exc))
            else:
                self.regex_status.setObjectName("OkText")
                self.regex_status.setText(tr("正则表达式有效"))
        self.regex_status.style().unpolish(self.regex_status)
        self.regex_status.style().polish(self.regex_status)

    def _on_metadata_changed(self, *_args) -> None:
        custom = self.date_format_combo.currentData() == "custom"
        self.custom_format_edit.setEnabled(custom)
        self._update_format_preview()
        self._mark_changed()

    def _update_format_preview(self) -> None:
        if not hasattr(self, "format_preview"):
            return
        now = datetime.now()
        key = self.date_format_combo.currentData()
        if key == "compact":
            sample = now.strftime("%Y%m%d")
        elif key == "datetime":
            sample = now.strftime("%Y-%m-%d_%H%M%S")
        elif key == "custom":
            pattern = self.custom_format_edit.text().strip()
            try:
                sample = now.strftime(pattern) if pattern else tr("（请输入自定义格式）")
            except ValueError:
                sample = tr("（格式无效）")
        else:
            sample = now.strftime("%Y-%m-%d")
        self.format_preview.setText(tr("格式示例：{sample}", sample=sample))
