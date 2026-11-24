"""第 7 步演示：方案导入导出、最近方案、配置记忆与离线帮助。"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.engine.scheme import Scheme, SchemeError
from app.main_window import MainWindow
from app.paths import resource_path
from app.ui.help_dialog import HelpDialog

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "ui_step7_files"
SETTINGS_DIR = ROOT / "ui_step7_settings"
SCHEME = ROOT / "ui_step7_scheme.bfr.json"
SHOTS = ROOT.parent / "docs"


def main() -> int:
    for path in (WORK, SETTINGS_DIR, SCHEME):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    WORK.mkdir(parents=True)
    SETTINGS_DIR.mkdir(parents=True)
    SHOTS.mkdir(parents=True, exist_ok=True)

    for name in ("01.mp4", "02.mp4", "03.mp4", "封面.jpg", "花絮.jpg"):
        (WORK / name).write_text(f"content:{name}", encoding="utf-8")

    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(SETTINGS_DIR))

    QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)

    app = QApplication(sys.argv)
    app.setOrganizationName("批量文件改名")
    app.setApplicationName("批量文件改名")
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    QSettings().setValue("ui/language", "zh")
    QSettings().setValue("ui/theme", "light")

    window = MainWindow()
    window.show()
    try:
        window.file_list.add_paths([WORK])
        window.rules_panel.template_edit.setText("方案_#")
        window.rules_panel.digits_spin.setValue(2)
        window.rules_panel.date_format_combo.setCurrentIndex(1)  # 20261121
        window.file_list.filter_edit.setText("mp4")
        window.file_list.sort_by_key("name", False)
        window._apply_previews()
        assert window.wait_for_previews(), "预览超时"
        app.processEvents()

        window.save_scheme(SCHEME)
        assert SCHEME.exists()
        data = json.loads(SCHEME.read_text(encoding="utf-8"))
        assert data["rules"]["overall"]["template"] == "方案_#"
        assert data["filters"]["extensions"] == ["mp4"]
        assert data["sort"] == {"key": "name", "ascending": False}

        # 改乱界面后重新应用方案
        window.rules_panel.template_edit.setText("破坏_#")
        window.file_list.clear_filter()
        window.file_list.sort_by_key("natural", True)
        window._apply_scheme(Scheme.load(SCHEME))
        app.processEvents()
        assert window.rules_panel.template_edit.text() == "方案_#"
        assert window.file_list.filter_extensions() == ["mp4"]
        assert window.file_list.sort_state() == ("name", False)
        assert window.rules_panel.date_format_combo.currentData() == "compact"

        window._remember_scheme(SCHEME)
        assert window._recent_paths()[0] == str(SCHEME)
        window._rebuild_recent_menu()
        assert window.recent_menu.actions()[0].text() == SCHEME.name

        window.rules_panel.template_edit.setText("又改乱")
        window._load_recent_scheme(str(SCHEME))
        assert window.rules_panel.template_edit.text() == "方案_#"

        window._last_dir = str(WORK)
        window.tab_buttons[3].click()
        window.resize(1200, 760)
        app.processEvents()
        window.grab().save(str(SHOTS / "ui_step7_demo.png"))

        help_dialog = HelpDialog(window)
        help_dialog.show()
        app.processEvents()
        help_dialog.grab().save(str(SHOTS / "ui_step7_help.png"))
        help_dialog.close()
        app.processEvents()
    finally:
        window.close()

    # 重新打开，验证窗口大小、标签页、规则、筛选、排序与最近目录都被记住
    restored = MainWindow()
    restored.show()
    try:
        app.processEvents()
        assert restored.rules_panel.template_edit.text() == "方案_#"
        assert restored.file_list.filter_extensions() == ["mp4"]
        assert restored.file_list.sort_state() == ("name", False)
        assert restored.rules_panel.current_page() == 3
        assert restored._last_dir == str(WORK)
        assert restored._recent_paths()[0] == str(SCHEME)
        assert restored.width() >= 1040
    finally:
        restored.close()

    # 损坏的方案不会污染现有设置
    broken = ROOT / "ui_step7_broken.bfr.json"
    broken.write_text("{not json", encoding="utf-8")
    try:
        try:
            Scheme.load(broken)
        except SchemeError:
            pass
        else:
            raise AssertionError("损坏的方案应当报错")
    finally:
        broken.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
