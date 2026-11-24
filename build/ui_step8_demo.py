"""第 8 步演示：多语言、媒体标签、文件夹扫描、主题与重置默认。"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.i18n import current_language
from app.main_window import MainWindow
from app.paths import resource_path
from app.ui import theme
from app.ui.help_dialog import HelpDialog

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "ui_step8_files"
NESTED = ROOT / "ui_step8_nested"
SETTINGS = ROOT / "ui_step8_settings"
SHOTS = ROOT.parent / "docs"


def make_jpeg(path: Path, taken: str, camera: str, lens: str, iso: int, aperture: tuple[int, int]) -> None:
    image = Image.new("RGB", (320, 220), (110, 150, 190))
    exif = image.getexif()
    exif[36867] = taken
    exif[271] = "Fujifilm"
    exif[272] = camera
    exif[42036] = lens
    exif[34855] = iso
    exif[33437] = aperture
    image.save(path, exif=exif)


def make_mp3(path: Path) -> None:
    from mutagen.id3 import ID3, TALB, TCON, TDRC, TIT2, TPE1

    path.write_bytes(b"")
    tags = ID3()
    tags.add(TIT2(encoding=3, text=["Night Drive"]))
    tags.add(TPE1(encoding=3, text=["Aoi"]))
    tags.add(TALB(encoding=3, text=["City Lights"]))
    tags.add(TDRC(encoding=3, text=["2019-04-05"]))
    tags.add(TCON(encoding=3, text=["Synthwave"]))
    tags.save(path)


def main() -> int:
    for path in (WORK, NESTED, SETTINGS):
        if path.exists():
            shutil.rmtree(path)
    WORK.mkdir()
    NESTED.mkdir()
    SETTINGS.mkdir()
    SHOTS.mkdir(parents=True, exist_ok=True)

    make_jpeg(WORK / "DSC_0001.JPG", "2024:05:06 07:08:09", "X100V", "23mm F2", 160, (2, 1))
    make_jpeg(WORK / "DSC_0002.JPG", "2024:05:06 07:09:10", "X-T5", "XF 16-55mm", 400, (28, 10))
    make_mp3(WORK / "track01.mp3")
    (WORK / "notes.txt").write_text("hello", encoding="utf-8")

    (NESTED / "top.txt").write_text("top", encoding="utf-8")
    (NESTED / "sub").mkdir()
    (NESTED / "sub" / "deep.txt").write_text("deep", encoding="utf-8")

    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(SETTINGS))
    QSettings().clear()

    QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)

    app = QApplication(sys.argv)
    app.setOrganizationName("批量文件改名")
    app.setApplicationName("批量文件改名")
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet("")

    window = MainWindow()
    window.show()
    try:
        window.file_list.add_paths([WORK])
        window.rules_panel.template_edit.setText("{date}_{time}_*")
        window._apply_previews()
        assert window.wait_for_previews(), "预览超时"

        # 文件夹扫描：不含子文件夹 / 含子文件夹
        window.file_list.clear_all(confirm=False)
        window.file_list.set_include_subfolders(False)
        added, _ = window.file_list.add_paths([NESTED], recursive=False)
        assert added == 1, added
        window.file_list.clear_all(confirm=False)
        window.file_list.set_include_subfolders(True)
        added, _ = window.file_list.add_paths([NESTED], recursive=True)
        assert added == 2, added
        window.file_list.clear_all(confirm=False)

        window.file_list.add_paths([WORK])
        window._apply_previews()
        assert window.wait_for_previews()
        entries = window.file_list.entries()
        photo_row = next(i for i, entry in enumerate(entries) if entry.path.name == "DSC_0001.JPG")
        window.file_list.table.selectRow(photo_row)
        app.processEvents()
        assert "X100V" in window.rules_panel.selection_info.text()

        # 深色 + English
        window._set_theme(theme.THEME_DARK)
        window._switch_language("en")
        window._apply_previews()
        assert window.wait_for_previews()
        assert window.rules_panel.template_edit.text() == "{date}_{time}_*"
        window.file_list.table.selectRow(photo_row)
        app.processEvents()
        assert "X100V" in window.rules_panel.selection_info.text()
        window.grab().save(str(SHOTS / "ui_step8_dark_en.png"))

        help_en = HelpDialog(window)
        help_en.show()
        app.processEvents()
        help_en.grab().save(str(SHOTS / "ui_step8_help_en.png"))
        help_en.close()

        # 设置持久化：重新打开窗口应恢复语言、主题与规则
        window._save_settings()
        restored = MainWindow()
        restored.show()
        app.processEvents()
        assert current_language() == "en"
        assert theme.load_theme_mode() == theme.THEME_DARK
        assert restored.rules_panel.template_edit.text() == "{date}_{time}_*"
        assert restored.file_list.include_subfolders() is True
        restored.close()
        app.processEvents()

        # 浅色 + 日本語
        window._set_theme(theme.THEME_LIGHT)
        window._switch_language("ja")
        window._apply_previews()
        assert window.wait_for_previews()
        assert window.menuBar().actions()[0].text() == "ファイル"
        window.grab().save(str(SHOTS / "ui_step8_light_ja.png"))

        # 重置默认设置
        window.rules_panel.template_edit.setText("temp_#")
        window._set_theme(theme.THEME_DARK)
        window._switch_language("en")
        window._reset_defaults()
        app.processEvents()
        assert current_language() == "zh"
        assert window.rules_panel.template_edit.text() == ""
        assert theme.load_theme_mode() == theme.THEME_SYSTEM
        assert window.file_list.filter_extensions() == []
        window.grab().save(str(SHOTS / "ui_step8_reset.png"))
    finally:
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
