"""离线使用说明对话框。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app import i18n
from app.paths import resource_path
from app.ui import theme as theme_module

DARK_HELP_CSS = """
  body { color: #E5E7EB; }
  h1, h2 { color: #F8FAFC; }
  th { background: #0F172A; color: #D1D5DB; }
  td, th { border-color: #334155; }
  code { background: #1E293B; color: #93C5FD; }
  kbd { background: #1E293B; border-color: #475569; color: #E5E7EB; }
  .muted { color: #94A3B8; }
  .note { background: #172554; border-color: #1E40AF; }
  .warn { background: #3B2A12; border-color: #92400E; }
"""


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("使用说明")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.resize(820, 700)
        self.setMinimumSize(640, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setOpenLinks(True)
        help_name = {
            "zh": "help.html",
            "en": "help_en.html",
            "ja": "help_ja.html",
        }.get(i18n.current_language(), "help.html")
        try:
            html = resource_path(f"app/resources/{help_name}").read_text(
                encoding="utf-8"
            )
        except OSError:
            try:
                html = resource_path("app/resources/help.html").read_text(
                    encoding="utf-8"
                )
            except OSError:
                html = (
                    "<h2>使用说明</h2><p>帮助文件缺失。请查看项目 README.md，"
                    "或重新安装程序。</p>"
                )
        if theme_module.resolve_theme(theme_module.load_theme_mode()) == theme_module.THEME_DARK:
            if "</style>" in html:
                html = html.replace("</style>", DARK_HELP_CSS + "</style>")
            else:
                html = f"<style>{DARK_HELP_CSS}</style>" + html
        browser.setHtml(html)
        document = browser.document()
        document.setDocumentMargin(10)
        layout.addWidget(browser, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        i18n.translate_widget_tree(self)
