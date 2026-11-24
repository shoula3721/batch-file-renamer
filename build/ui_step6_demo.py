"""第 6 步演示：55 个文件真实改名、撤销、还原与崩溃恢复，并截图。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.engine.backup import (
    KIND_RENAME,
    STATE_COMPLETED,
    STATE_COMPLETED_WITH_ERRORS,
    STATE_RENAMING,
    STATUS_OK,
    BackupItem,
    BackupStore,
)
from app.engine.undo import CONFLICT_SKIP
from app.main_window import MainWindow
from app.paths import resource_path
from app.ui.progress_dialog import ProgressDialog
from app.ui.restore_dialog import RestoreDialog
from app.ui.result_dialog import ResultDialog

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "ui_step6_files"
SETTINGS = ROOT / "ui_step6_settings"
BACKUPS = ROOT / "ui_step6_backups"
RECOVERY_DIR = ROOT / "ui_step6_recovery_files"
RECOVERY_BACKUPS = ROOT / "ui_step6_recovery_backups"
SHOTS = ROOT.parent / "docs"


def patch_dialogs() -> None:
    """自动应答确认框，便于无人值守演示。"""
    QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    QMessageBox.critical = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)


def close_results(window: MainWindow) -> None:
    for dialog in window.findChildren(ResultDialog):
        dialog.close()
    QApplication.processEvents()


def latest_rename_batch(store: BackupStore):
    for record in store.list_records():
        if record.kind == KIND_RENAME and record.state in (
            STATE_COMPLETED,
            STATE_COMPLETED_WITH_ERRORS,
        ):
            return record
    return None


def main() -> int:
    for path in (WORK, BACKUPS, RECOVERY_DIR, RECOVERY_BACKUPS, SETTINGS):
        if path.exists():
            shutil.rmtree(path)
    WORK.mkdir(parents=True)
    SETTINGS.mkdir(parents=True)
    BACKUPS.mkdir(parents=True)
    RECOVERY_DIR.mkdir(parents=True)
    SHOTS.mkdir(parents=True, exist_ok=True)

    sources = [f"{index:02d}.1080P.WEB-DL.mp4" for index in range(1, 56)]
    for name in sources:
        (WORK / name).write_text(f"content:{name}", encoding="utf-8")

    patch_dialogs()
    app = QApplication(sys.argv)
    app.setOrganizationName("批量文件改名")
    app.setApplicationName("批量文件改名")
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(SETTINGS))
    QSettings().clear()
    QSettings().setValue("ui/language", "zh")
    QSettings().setValue("ui/theme", "light")

    window = MainWindow()
    window.backup_store = BackupStore(BACKUPS)
    window._backup_error = ""
    window._refresh_edit_actions()
    window.show()

    try:
        window.file_list.add_paths([WORK])
        window.rules_panel.template_edit.setText("批量_#")
        window.rules_panel.digits_spin.setValue(3)
        window._apply_previews()
        assert window.wait_for_previews(), "预览超时"
        assert window.file_list.visible_count() == 55

        # 1. 真实改名 55 个文件
        window._on_start()
        assert window.wait_for_operation(), "改名超时"
        assert window.wait_for_previews(), "改名后预览超时"
        assert len(list(WORK.glob("批量_*.mp4"))) == 55
        assert (WORK / "批量_001.mp4").exists()
        assert (WORK / "批量_055.mp4").exists()
        entries = window.file_list.entries()
        assert all(entry.result == "成功" for entry in entries)
        assert not list(WORK.glob("*.tmp"))

        dialogs = window.findChildren(ResultDialog)
        assert dialogs, "没有显示结果对话框"
        dialogs[0].grab().save(str(SHOTS / "ui_step6_result.png"))
        close_results(window)
        window.grab().save(str(SHOTS / "ui_step6_demo.png"))

        # 2. 撤销，全部恢复原名
        window._undo_last()
        assert window.wait_for_operation(), "撤销超时"
        assert window.wait_for_previews(), "撤销后预览超时"
        close_results(window)
        assert (WORK / sources[0]).exists()
        assert not list(WORK.glob("批量_*.mp4"))
        assert len(list(WORK.iterdir())) == 55

        # 3. 再改名一次，然后从备份对话框还原
        window._on_start()
        assert window.wait_for_operation(), "第二次改名超时"
        assert window.wait_for_previews(), "第二次改名后预览超时"
        close_results(window)
        batch = latest_rename_batch(window.backup_store)
        assert batch is not None

        restore_dialog = RestoreDialog(window.backup_store, window)
        restore_dialog.show()
        app.processEvents()
        restore_dialog.grab().save(str(SHOTS / "ui_step6_restore.png"))
        restore_dialog.close()
        app.processEvents()

        progress = ProgressDialog(
            window, "正在重命名", "共 55 个文件，按“写入备份 → 临时名 → 目标名”执行。"
        )
        progress.update_progress(27, 55, "正在写入目标名称")
        progress.show()
        app.processEvents()
        progress.grab().save(str(SHOTS / "ui_step6_progress.png"))
        progress.close()
        app.processEvents()

        window._restore_batch(batch.batch_id, CONFLICT_SKIP, confirm=True)
        assert window.wait_for_operation(), "还原超时"
        assert window.wait_for_previews(), "还原后预览超时"
        close_results(window)
        assert (WORK / sources[0]).exists()
        assert not list(WORK.glob("批量_*.mp4"))

        # 4. 模拟崩溃：一个文件停在临时名，一个已落到新名字
        first = RECOVERY_DIR / "恢复_1.txt"
        second = RECOVERY_DIR / "恢复_2.txt"
        first.write_text("one", encoding="utf-8")
        second.write_text("two", encoding="utf-8")
        temp = RECOVERY_DIR / ".~br_test-0.tmp"
        first.rename(temp)
        renamed = RECOVERY_DIR / "已改_2.txt"
        second.rename(renamed)

        recovery_store = BackupStore(RECOVERY_BACKUPS)
        record = recovery_store.create(
            [
                BackupItem(
                    old=str(first),
                    new=str(RECOVERY_DIR / "已改_1.txt"),
                    status="pending",
                ),
                BackupItem(
                    old=str(second),
                    new=str(renamed),
                    status=STATUS_OK,
                ),
            ],
            kind=KIND_RENAME,
        )
        record.items[0].temp = str(temp)
        record.state = STATE_RENAMING
        recovery_store.save(record)

        window.backup_store = recovery_store
        window._check_startup_recovery()
        app.processEvents()
        assert first.exists() and first.read_text(encoding="utf-8") == "one"
        assert second.exists() and second.read_text(encoding="utf-8") == "two"
        assert not temp.exists()
        recovered = recovery_store.find(record.batch_id)
        assert recovered is not None and recovered.state != STATE_RENAMING
    finally:
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
