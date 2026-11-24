"""浅色 / 深色主题与“跟随系统”。"""
from __future__ import annotations

import re
import sys

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from app.paths import resource_path

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"
THEME_MODES = (THEME_LIGHT, THEME_DARK, THEME_SYSTEM)
SETTING_KEY = "ui/theme"

# 浅色主题中的颜色 -> 深色主题颜色
DARK_MAP = {
    "#F5F7FA": "#0B1220",  # 应用背景
    "#FFFFFF": "#111827",  # 卡片 / 输入框
    "#FAFBFD": "#0F172A",  # 次级背景 / 斑马纹
    "#F7F9FC": "#0F172A",  # 表头
    "#F5F8FF": "#172554",  # 占位符按钮
    "#EEF1F6": "#243044",  # 分割线 / 进度条底
    "#E3E8EF": "#2A3648",  # 边框
    "#D5DCE6": "#334155",  # 输入框边框
    "#B9C4D4": "#475569",  # hover 边框
    "#E9EDF4": "#1E293B",  # 分段控件底
    "#EEF3FE": "#1E3A5F",
    "#F3F5F9": "#1E293B",
    "#F0F3F8": "#243044",
    "#F5F6F9": "#1E293B",
    "#F3F6FE": "#93A4C3",
    "#E8F0FE": "#1E3A5F",  # 选中
    "#DCE8FF": "#1E3A5F",
    "#DCE6FA": "#1E40AF",
    "#B9CFF7": "#3B82F6",
    "#EAF1FF": "#1E3A5F",
    "#DCE2EB": "#334155",
    "#E5E9F0": "#1F2937",
    "#1F2937": "#E5E7EB",  # 正文
    "#111827": "#F8FAFC",  # 标题
    "#374151": "#D1D5DB",
    "#4B5563": "#CBD5E1",
    "#6B7280": "#94A3B8",
    "#8A93A3": "#94A3B8",
    "#9CA3AF": "#64748B",
    "#A6AEBB": "#64748B",
    "#AEB9C9": "#64748B",
    "#CBD3DF": "#475569",
    "#2F6FED": "#60A5FA",  # 主色
    "#255FD0": "#3B82F6",
    "#1E4FBC": "#2563EB",
    "#C7D6F5": "#1E3A5F",
    "#047857": "#34D399",
    "#DC2626": "#F87171",
}

DARK_OVERRIDES = """
QToolTip {
    background: #0B1220;
    color: #F8FAFC;
    border: 1px solid #334155;
}
QPushButton#Primary,
QPushButton#Primary:hover,
QPushButton#Primary:pressed {
    color: #F8FAFC;
}
QPushButton#Primary:disabled {
    color: #CBD5E1;
}
"""


def load_theme_mode() -> str:
    value = str(QSettings().value(SETTING_KEY, THEME_SYSTEM))
    return value if value in THEME_MODES else THEME_SYSTEM


def save_theme_mode(mode: str) -> None:
    if mode not in THEME_MODES:
        mode = THEME_SYSTEM
    settings = QSettings()
    settings.setValue(SETTING_KEY, mode)
    settings.sync()


def system_is_dark() -> bool:
    hints = QGuiApplication.styleHints()
    scheme = getattr(hints, "colorScheme", lambda: None)()
    color_scheme = getattr(Qt, "ColorScheme", None)
    if color_scheme is not None:
        if scheme == color_scheme.Dark:
            return True
        if scheme == color_scheme.Light:
            return False
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
        except OSError:
            return False
    return False


def resolve_theme(mode: str) -> str:
    if mode == THEME_DARK:
        return THEME_DARK
    if mode == THEME_LIGHT:
        return THEME_LIGHT
    return THEME_DARK if system_is_dark() else THEME_LIGHT


def build_stylesheet(theme: str) -> str:
    qss_path = resource_path("app/resources/style.qss")
    try:
        text = qss_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    resources = resource_path("app/resources").as_posix()
    text = text.replace("@RES@", resources)
    if theme == THEME_DARK:
        pattern = re.compile(
            "|".join(re.escape(color) for color in sorted(DARK_MAP, key=len, reverse=True))
        )
        text = pattern.sub(lambda match: DARK_MAP[match.group(0)], text)
        text += "\n" + DARK_OVERRIDES
    return text


def apply_theme(app: QApplication | None = None, mode: str | None = None) -> str:
    """应用主题并返回实际使用的 light / dark。"""
    application = app or QApplication.instance()
    if application is None:
        return THEME_LIGHT
    chosen = resolve_theme(mode or load_theme_mode())
    application.setStyleSheet(build_stylesheet(chosen))
    return chosen
