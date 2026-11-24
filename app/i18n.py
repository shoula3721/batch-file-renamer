"""轻量多语言支持：中文（默认）、English、日本語。

界面文本在构建后由 translate_widget_tree 统一翻译；动态文本通过 tr() 翻译。
切换语言时重新遍历控件，原始中文保存在控件属性里，因此可以反复切换。
"""
from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QEvent, QLibraryInfo, QObject, QSettings, Qt, QTranslator
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTabWidget,
    QTableWidget,
    QWidget,
)

from app.i18n_data import TRANSLATIONS

DEFAULT_LANGUAGE = "zh"
LANGUAGES = {"zh": "中文", "en": "English", "ja": "日本語"}
SETTING_KEY = "ui/language"

_current_language = DEFAULT_LANGUAGE
_SOURCE_ROLE = int(Qt.UserRole) + 101
_PROP_PREFIX = "_i18n_src_"
_PATTERN_CACHE: dict[tuple[str, str], re.Pattern[str]] = {}
_DYNAMIC_CACHE: dict[tuple[str, str], str | None] = {}
_FIELD_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _compile_template(template: str) -> re.Pattern[str]:
    parts: list[str] = []
    seen: set[str] = set()
    position = 0
    for match in _FIELD_RE.finditer(template):
        parts.append(re.escape(template[position : match.start()]))
        name = match.group(1)
        if name in seen:
            parts.append(f"(?P={name})")
        else:
            parts.append(f"(?P<{name}>.*?)")
            seen.add(name)
        position = match.end()
    parts.append(re.escape(template[position:]))
    return re.compile("^" + "".join(parts) + "$", re.DOTALL)


def _dynamic_translation(text: str) -> str | None:
    key = (_current_language, text)
    if key in _DYNAMIC_CACHE:
        return _DYNAMIC_CACHE[key]
    table = TRANSLATIONS.get(_current_language, {})
    result: str | None = None
    for template, translated in table.items():
        if "{" not in template:
            continue
        cache_key = (_current_language, template)
        pattern = _PATTERN_CACHE.get(cache_key)
        if pattern is None:
            pattern = _compile_template(template)
            _PATTERN_CACHE[cache_key] = pattern
        match = pattern.match(text)
        if match:
            try:
                result = translated.format(**match.groupdict())
            except (KeyError, IndexError, ValueError):
                result = None
            if result is not None:
                break
    _DYNAMIC_CACHE[key] = result
    return result


def initialize() -> str:
    global _current_language
    value = str(QSettings().value(SETTING_KEY, DEFAULT_LANGUAGE))
    _current_language = value if value in LANGUAGES else DEFAULT_LANGUAGE
    return _current_language


def current_language() -> str:
    return _current_language


def set_language(language: str, save: bool = True) -> str:
    global _current_language
    if language not in LANGUAGES:
        language = DEFAULT_LANGUAGE
    _current_language = language
    _DYNAMIC_CACHE.clear()
    if save:
        settings = QSettings()
        settings.setValue(SETTING_KEY, language)
        settings.sync()
    return language


def tr(text: str, **kwargs: Any) -> str:
    """翻译一段文本；未知文本原样返回，支持 {name} 占位参数。"""
    if not text:
        return text
    table = TRANSLATIONS.get(_current_language, {})
    translated = table.get(text)
    if translated is None:
        translated = _dynamic_translation(text)
    if translated is None:
        translated = text
    if kwargs:
        try:
            return translated.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return translated
    return translated


def _translate_property(obj: Any, prop: str, getter, setter) -> None:
    key = _PROP_PREFIX + prop
    source = obj.property(key)
    if source is None:
        source = getter()
        if not source:
            return
        obj.setProperty(key, source)
    translated = tr(source)
    if translated != getter():
        setter(translated)


def translate_widget_tree(root: QWidget | QAction) -> None:
    """遍历控件与 QAction，翻译所有静态文本（可重复调用）。"""
    widgets: list[QWidget] = []
    actions: list[QAction] = []
    if isinstance(root, QAction):
        actions.append(root)
    else:
        widgets.append(root)
        widgets.extend(root.findChildren(QWidget))
        actions.extend(root.findChildren(QAction))

    for widget in widgets:
        if isinstance(widget, QAbstractButton):
            _translate_property(widget, "text", widget.text, widget.setText)
        elif isinstance(widget, QLabel):
            _translate_property(widget, "text", widget.text, widget.setText)
        elif isinstance(widget, QGroupBox):
            _translate_property(widget, "title", widget.title, widget.setTitle)
        elif isinstance(widget, QLineEdit):
            _translate_property(
                widget,
                "placeholder",
                widget.placeholderText,
                widget.setPlaceholderText,
            )
        elif isinstance(widget, QComboBox):
            for index in range(widget.count()):
                source = widget.itemData(index, _SOURCE_ROLE)
                if source is None:
                    source = widget.itemText(index)
                    if not source:
                        continue
                    widget.setItemData(index, source, _SOURCE_ROLE)
                translated = tr(str(source))
                if translated != widget.itemText(index):
                    widget.setItemText(index, translated)
        elif isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                source = widget.tabText(index)
                if source:
                    widget.setTabText(index, tr(source))
        elif isinstance(widget, QTableWidget):
            for column in range(widget.columnCount()):
                item = widget.horizontalHeaderItem(column)
                if item is not None:
                    item.setText(tr(item.text()))

        _translate_property(
            widget, "windowTitle", widget.windowTitle, widget.setWindowTitle
        )
        _translate_property(
            widget, "toolTip", widget.toolTip, widget.setToolTip
        )
        _translate_property(
            widget, "statusTip", widget.statusTip, widget.setStatusTip
        )
        if isinstance(widget, QMenu):
            _translate_property(widget, "title", widget.title, widget.setTitle)

    for action in actions:
        _translate_property(action, "text", action.text, action.setText)
        _translate_property(
            action, "toolTip", action.toolTip, action.setToolTip
        )
        _translate_property(
            action, "statusTip", action.statusTip, action.setStatusTip
        )


def add_combo_item(combo: QComboBox, text: str, data: Any = None) -> None:
    """添加下拉项，同时记住原始中文以便切换语言。"""
    combo.addItem(tr(text), data)
    combo.setItemData(combo.count() - 1, text, _SOURCE_ROLE)


class _MessageTranslationFilter(QObject):
    """QMessageBox 显示前自动翻译其中的文本。"""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if isinstance(obj, QMessageBox) and event.type() == QEvent.Show:
            translate_widget_tree(obj)
        return False


_message_filter: _MessageTranslationFilter | None = None
_qt_translator: QTranslator | None = None


def install_qt_translator(app: QApplication | None = None) -> None:
    """加载 Qt 自带翻译，让标准按钮（是 / 否 / 确定）跟随界面语言。"""
    global _qt_translator
    application = app or QApplication.instance()
    if application is None:
        return
    if _qt_translator is not None:
        application.removeTranslator(_qt_translator)
        _qt_translator = None
    names = {
        "zh": "qtbase_zh_CN.qm",
        "ja": "qtbase_ja_JP.qm",
        "en": "qtbase_en.qm",
    }
    filename = names.get(_current_language)
    if not filename:
        return
    from pathlib import Path

    path = (
        Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath)) / filename
    )
    if not path.exists():
        return
    translator = QTranslator(application)
    if translator.load(str(path)):
        application.installTranslator(translator)
        _qt_translator = translator


def install_message_filter(app: QApplication | None = None) -> None:
    global _message_filter
    application = app or QApplication.instance()
    if application is None or _message_filter is not None:
        return
    _message_filter = _MessageTranslationFilter(application)
    application.installEventFilter(_message_filter)
