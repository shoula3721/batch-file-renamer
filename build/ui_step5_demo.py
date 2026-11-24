"""第 5 步演示：EXIF / 视频拍摄时间、后台预览、按拍摄时间排序并截图。"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.paths import resource_path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "ui_step5_files"
SETTINGS = ROOT / "ui_step5_settings"
SHOTS = ROOT.parent / "docs"
MP4_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)
COLORS = [
    (226, 104, 90),
    (92, 148, 225),
    (110, 196, 140),
    (233, 178, 88),
    (158, 132, 214),
    (87, 190, 200),
]


def mp4_box(kind: bytes, payload: bytes) -> bytes:
    return (8 + len(payload)).to_bytes(4, "big") + kind + payload


def make_jpeg(path: Path, taken: str, color: tuple[int, int, int]) -> None:
    image = Image.new("RGB", (640, 420), color)
    exif = image.getexif()
    exif[36867] = taken
    image.save(path, exif=exif)


def make_mp4(path: Path, created_utc: datetime) -> None:
    seconds = int((created_utc - MP4_EPOCH).total_seconds())
    mvhd = b"\x00\x00\x00\x00" + seconds.to_bytes(4, "big") + b"\x00" * 12
    path.write_bytes(
        mp4_box(b"ftyp", b"isomisom")
        + mp4_box(b"moov", mp4_box(b"mvhd", mvhd))
        + mp4_box(b"mdat", b"\x00" * 16)
    )


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    if SETTINGS.exists():
        shutil.rmtree(SETTINGS)
    WORK.mkdir(parents=True)
    SETTINGS.mkdir(parents=True)
    SHOTS.mkdir(parents=True, exist_ok=True)

    # 9 张有 EXIF 拍摄时间的照片
    for index in range(1, 10):
        moment = datetime(2026, 11, 21, 21, 40, 0) + timedelta(seconds=index * 7)
        make_jpeg(
            WORK / f"DSC_{index:04d}.JPG",
            moment.strftime("%Y:%m:%d %H:%M:%S"),
            COLORS[index % len(COLORS)],
        )
    # 3 段视频：mvhd 存 UTC
    for index in range(1, 4):
        make_mp4(
            WORK / f"CLIP_{index:02d}.MP4",
            datetime(2026, 11, 21, 13, 40, 0, tzinfo=timezone.utc)
            + timedelta(seconds=index * 5),
        )
    # 没有 EXIF 的封面：回退文件修改时间
    Image.new("RGB", (400, 560), (70, 82, 110)).save(WORK / "封面.jpg")

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
    window.show()

    try:
        window.file_list.add_paths([WORK])
        window.rules_panel.template_edit.setText("{date}_{time}_*")
        window._apply_previews()
        assert window.wait_for_previews(), "后台预览超时"

        entries = window.file_list.entries()
        assert len(entries) == 13, len(entries)
        photos = [entry for entry in entries if entry.path.suffix.lower() == ".jpg"]
        assert photos and photos[0].taken_source == "EXIF 拍摄时间"
        assert photos[0].preview.startswith("2026-11-21_2140"), photos[0].preview
        cover = next(entry for entry in entries if entry.path.name == "封面.jpg")
        assert cover.taken_fallback is True
        videos = [entry for entry in entries if entry.path.suffix.lower() == ".mp4"]
        assert videos and "视频拍摄时间" in videos[0].taken_source

        photo_row = next(
            index for index, entry in enumerate(entries) if entry.path.name == "DSC_0001.JPG"
        )
        window.file_list.table.selectRow(photo_row)
        app.processEvents()
        assert "EXIF" in window.rules_panel.selection_info.text()

        window.tab_buttons[0].click()
        app.processEvents()
        window.grab().save(str(SHOTS / "ui_step5_overall.png"))
        window.tab_buttons[3].click()
        app.processEvents()
        window.grab().save(str(SHOTS / "ui_step5_metadata.png"))

        window.act_sort_taken.trigger()
        assert window.wait_for_previews(), "按拍摄时间排序超时"
        app.processEvents()
        stamps = [
            entry.taken_at if entry.taken_at is not None else entry.mtime
            for entry in window.file_list.entries()
        ]
        assert stamps == sorted(stamps), stamps

        window.file_list.filter_edit.setText("jpg")
        app.processEvents()
        assert window.file_list.visible_count() == 10
        window.tab_buttons[0].click()
        app.processEvents()
        window.grab().save(str(SHOTS / "ui_step5_demo.png"))
        window.file_list.clear_filter()
        app.processEvents()

        window.resize(1040, 680)
        app.processEvents()
        window.grab().save(str(SHOTS / "ui_step5_min.png"))
    finally:
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
