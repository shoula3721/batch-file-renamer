"""界面预览逻辑测试（不依赖 Qt）。"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

from app.engine.metadata import CaptureCache
from app.engine.rules import MetadataRule, OverallRule, ReplaceRule, RuleSet
from app.ui.preview import build_previews
from media_helpers import write_id3_audio, write_jpeg, write_mp4


def write_files(directory: Path, names: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_text(f"content:{name}", encoding="utf-8")


def test_template_and_extension_preview(tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["01.mp4", "02.mp4"])
    rules = RuleSet(
        overall=OverallRule(
            template="视频_#",
            digits=2,
            pad=True,
            change_extension=True,
            new_extension="mkv",
        )
    )

    infos = build_previews([folder / "01.mp4", folder / "02.mp4"], rules)

    assert [info.target_name for info in infos] == ["视频_01.mkv", "视频_02.mkv"]
    assert all(info.status == "就绪" for info in infos)


def test_existing_name_gets_conflict_suffix(tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "x.txt"])
    rules = RuleSet(overall=OverallRule(template="x"))

    infos = build_previews([folder / "a.txt"], rules)

    assert infos[0].target_name == "x (1).txt"
    assert infos[0].status == "冲突已处理"
    assert infos[0].conflict_resolved is True


def test_numbering_continues_across_directories(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    write_files(first, ["a.txt"])
    write_files(second, ["b.txt"])
    rules = RuleSet(overall=OverallRule(template="文件_#"))

    infos = build_previews([first / "a.txt", second / "b.txt"], rules)

    assert [info.target_name for info in infos] == ["文件_1.txt", "文件_2.txt"]


def test_same_name_in_different_directories_does_not_conflict(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    write_files(first, ["a.txt"])
    write_files(second, ["a.txt"])
    rules = RuleSet(overall=OverallRule(template="same"))

    infos = build_previews([first / "a.txt", second / "a.txt"], rules)

    assert [info.target_name for info in infos] == ["same.txt", "same.txt"]
    assert all(info.status == "就绪" for info in infos)


def test_invalid_regex_reports_error(tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    rules = RuleSet(replace=ReplaceRule(old="[", new="x", use_regex=True))

    infos = build_previews([folder / "a.txt"], rules)

    assert infos[0].status == "错误"
    assert "正则" in infos[0].error


def test_date_placeholder_uses_file_mtime(tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    timestamp = datetime(2026, 1, 2, 3, 4, 5).timestamp()
    os.utime(folder / "a.txt", (timestamp, timestamp))
    rules = RuleSet(overall=OverallRule(template="{date}_*"))

    infos = build_previews([folder / "a.txt"], rules)

    assert infos[0].target_name == "2026-01-02_a.txt"


def test_unchanged_name_is_marked(tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    rules = RuleSet(overall=OverallRule(template="*"))

    infos = build_previews([folder / "a.txt"], rules)

    assert infos[0].status == "未更改"
    assert infos[0].unchanged is True


def test_filtered_subset_starts_numbering_at_one(tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["1.txt", "2.txt", "3.txt"])
    rules = RuleSet(overall=OverallRule(template="视频_#", digits=2, pad=True))

    infos = build_previews([folder / "3.txt"], rules)

    assert infos[0].target_name == "视频_01.txt"


def test_filtered_subset_still_avoids_hidden_files_on_disk(tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "视频_1.txt"])
    rules = RuleSet(overall=OverallRule(template="视频_#"))

    infos = build_previews([folder / "a.txt"], rules)

    assert infos[0].target_name == "视频_1 (1).txt"
    assert infos[0].conflict_resolved is True


# ---------------------------------------------------------------------------
# 拍摄时间
# ---------------------------------------------------------------------------
def test_exif_time_is_used_for_preview(tmp_path: Path) -> None:
    folder = tmp_path / "photos"
    photo = write_jpeg(folder / "IMG_0001.JPG", "2026:11:21 21:40:05", subsec="250")
    rules = RuleSet(overall=OverallRule(template="{date}_{time}_*"))

    infos = build_previews([photo], rules)

    assert infos[0].target_name == "2026-11-21_214005_IMG_0001.JPG"
    assert infos[0].status == "就绪"
    assert infos[0].taken_source == "EXIF 拍摄时间"
    assert infos[0].taken_raw == "2026:11:21 21:40:05"
    assert infos[0].taken_fallback is False
    assert infos[0].taken_at == datetime(2026, 11, 21, 21, 40, 5, 250000).timestamp()


def test_compact_date_format(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "photos" / "IMG_0001.JPG")
    rules = RuleSet(
        overall=OverallRule(template="{date}_*"),
        metadata=MetadataRule(date_format="compact"),
    )

    infos = build_previews([photo], rules)

    assert infos[0].target_name == "20261121_IMG_0001.JPG"


def test_custom_date_format(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "photos" / "IMG_0001.JPG")
    rules = RuleSet(
        overall=OverallRule(template="{date}_*"),
        metadata=MetadataRule(date_format="custom", custom_format="%d.%m.%Y"),
    )

    infos = build_previews([photo], rules)

    assert infos[0].target_name == "21.11.2026_IMG_0001.JPG"


def test_explicit_mtime_source_overrides_exif(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "photos" / "IMG_0001.JPG")
    timestamp = datetime(2020, 1, 2, 3, 4, 5).timestamp()
    os.utime(photo, (timestamp, timestamp))
    rules = RuleSet(
        overall=OverallRule(template="{date}_*"),
        metadata=MetadataRule(date_source="mtime"),
    )

    infos = build_previews([photo], rules)

    assert infos[0].target_name == "2020-01-02_IMG_0001.JPG"
    assert infos[0].taken_source == "文件修改时间"
    assert infos[0].taken_fallback is False


def test_missing_capture_falls_back_to_mtime(tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["note.txt"])
    note = folder / "note.txt"
    timestamp = datetime(2021, 5, 6, 7, 8, 9).timestamp()
    os.utime(note, (timestamp, timestamp))
    rules = RuleSet(overall=OverallRule(template="{date}_*"))

    infos = build_previews([note], rules)

    assert infos[0].target_name == "2021-05-06_note.txt"
    assert "未找到拍摄时间" in infos[0].taken_source
    assert infos[0].taken_fallback is True


def test_video_time_can_be_converted_to_local(tmp_path: Path) -> None:
    created = datetime(2026, 11, 21, 13, 40, 5, tzinfo=timezone.utc)
    video = write_mp4(tmp_path / "videos" / "clip.mp4", created)
    rules = RuleSet(
        overall=OverallRule(template="{datetime}_*"),
        metadata=MetadataRule(date_format="datetime", timezone="local"),
    )
    expected = created.astimezone().replace(tzinfo=None)

    infos = build_previews([video], rules)

    assert infos[0].target_name == f"{expected:%Y-%m-%d_%H%M%S}_clip.mp4"
    assert infos[0].taken_source.startswith("视频拍摄时间")


def test_invalid_custom_format_reports_error(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "photos" / "IMG_0001.JPG")
    rules = RuleSet(
        overall=OverallRule(template="{date}_*"),
        metadata=MetadataRule(date_format="custom", custom_format="%Y-%m-%d %"),
    )

    infos = build_previews([photo], rules)

    assert infos[0].status == "错误"
    assert "日期格式" in infos[0].error


def test_explicit_metadata_mapping_still_supported(tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    rules = RuleSet(overall=OverallRule(template="{date}"))

    infos = build_previews(
        [folder / "a.txt"],
        rules,
        metadata={str(folder / "a.txt"): {"date": date(2026, 1, 2)}},
    )

    assert infos[0].target_name == "2026-01-02.txt"


def test_previews_share_capture_cache(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "photos" / "IMG_0001.JPG")
    cache = CaptureCache()
    rules = RuleSet(overall=OverallRule(template="{date}_*"))

    first = build_previews([photo], rules, cache=cache)
    second = build_previews([photo], rules, cache=cache)

    assert first[0].target_name == second[0].target_name == "2026-11-21_IMG_0001.JPG"
    assert cache.reads == 1


def test_audio_tags_are_used_for_preview(tmp_path: Path) -> None:
    song = write_id3_audio(tmp_path / "song.mp3")
    rules = RuleSet(overall=OverallRule(template="{artist}_{title}_{tag_year}"))

    infos = build_previews([song], rules)

    assert infos[0].target_name == "The Artist_Song Title_2021.mp3"
    assert infos[0].media_tags["artist"] == "The Artist"
    assert infos[0].media_tags["album"] == "Album Name"
    assert infos[0].taken_source == "音频标签时间"


def test_image_camera_fields_are_used_for_preview(tmp_path: Path) -> None:
    photo = write_jpeg(
        tmp_path / "photo.jpg",
        exif_tags={272: "X100V", 34855: 160, 33437: (2, 1), 42036: "23mm"},
    )
    rules = RuleSet(
        overall=OverallRule(template="{camera}_{iso}_{aperture}_{lens}_*")
    )

    infos = build_previews([photo], rules)

    assert infos[0].target_name == "X100V_160_f2_23mm_photo.jpg"
    assert infos[0].media_tags["iso"] == "160"
