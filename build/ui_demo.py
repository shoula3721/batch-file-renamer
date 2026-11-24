"""界面联调脚本：添加示例文件、套用规则、筛选、排序并截图。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.paths import resource_path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "ui_demo_files"


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    names = [f"{index:02d}.1080P.WEB-DL.mp4" for index in range(1, 13)]
    for name in names:
        (WORK / name).write_text(f"content:{name}", encoding="utf-8")
    (WORK / "封面.jpg").write_text("cover", encoding="utf-8")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(resource_path("app/resources/style.qss").read_text(encoding="utf-8"))
    window = MainWindow()
    window.show()

    window.file_list.add_paths([WORK])
    window.rules_panel.template_edit.setText("视频_#")
    window.rules_panel.change_ext_check.setChecked(True)
    window.rules_panel.ext_edit.setText("mp4")
    window._apply_previews()
    assert window.wait_for_previews(), "后台预览超时"
    app.processEvents()

    entries = window.file_list.entries()
    assert len(entries) == 13, len(entries)
    assert entries[0].preview == "视频_1.mp4", entries[0].preview
    assert entries[0].status == "就绪", entries[0].status

    window.file_list.table.selectRow(0)
    for index, name in enumerate(("overall", "replace", "addremove", "metadata")):
        window.tab_buttons[index].click()
        app.processEvents()
        window.grab().save(str(ROOT / f"ui_step4_{name}.png"))
    assert "1080P" in window.rules_panel.selection_info.text()

    window.file_list.filter_edit.setText("jpg")
    app.processEvents()
    assert window.file_list.visible_count() == 1
    window.file_list.clear_filter()
    app.processEvents()
    assert window.file_list.visible_count() == 13

    window.file_list.sort_by_key("name", False)
    assert window.file_list.entries()[0].path.name == "封面.jpg"
    window.file_list.table.selectRow(0)
    window.file_list._move(-999)
    assert window.file_list.entries()[0].path.name == "封面.jpg"

    window.grab().save(str(ROOT / "ui_step4_demo.png"))
    window.resize(980, 640)
    app.processEvents()
    window.grab().save(str(ROOT / "ui_step4_min.png"))
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
