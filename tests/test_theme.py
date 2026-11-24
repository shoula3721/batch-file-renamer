"""主题样式与翻译表完整性测试。"""
from __future__ import annotations

import re
from pathlib import Path

from app.i18n import set_language, tr
from app.i18n_data import TRANSLATIONS
from app.paths import resource_path
from app.ui import theme


def test_dark_map_covers_every_colour() -> None:
    qss = resource_path("app/resources/style.qss").read_text(encoding="utf-8")
    colours = set(re.findall(r"#[0-9A-Fa-f]{6}", qss))
    assert colours
    assert not (colours - set(theme.DARK_MAP))


def test_build_stylesheet_replaces_resources_and_colours() -> None:
    light = theme.build_stylesheet(theme.THEME_LIGHT)
    dark = theme.build_stylesheet(theme.THEME_DARK)

    assert "@RES@" not in light
    assert "@RES@" not in dark
    assert "#F5F7FA" in light
    assert "#0B1220" in dark
    assert "#F5F7FA" not in dark
    assert "QToolTip" in dark


def test_translation_tables_have_same_keys_and_placeholders() -> None:
    english = TRANSLATIONS["en"]
    japanese = TRANSLATIONS["ja"]
    assert english.keys() == japanese.keys()
    assert len(english) > 200
    for key in english:
        assert english[key]
        assert japanese[key]
        assert set(re.findall(r"\{(\w+)\}", key)) == set(
            re.findall(r"\{(\w+)\}", english[key])
        )
        assert set(re.findall(r"\{(\w+)\}", english[key])) == set(
            re.findall(r"\{(\w+)\}", japanese[key])
        )


def test_translate_and_dynamic_templates() -> None:
    set_language("en", save=False)
    assert tr("{count} 个文件", count=3) == "3 files"
    assert "Read 3 files" in tr("已读取 3 个文件：EXIF 3")
    assert tr("成功 {success} 个 · 失败 {failed} 个 · 跳过 {skipped} 个", success=2, failed=0, skipped=1)
    set_language("ja", save=False)
    assert "3 ファイル" in tr("{count} 个文件", count=3)
    set_language("zh", save=False)
    assert tr("中文") == "中文"


def test_help_files_exist_with_version() -> None:
    for name in ("help.html", "help_en.html", "help_ja.html"):
        path = resource_path(f"app/resources/{name}")
        assert path.exists(), name
        assert "37.21.beta3" in path.read_text(encoding="utf-8")
