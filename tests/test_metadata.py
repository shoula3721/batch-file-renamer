"""拍摄时间读取、缓存与占位符数据测试。"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.engine.metadata import (
    CaptureCache,
    CaptureInfo,
    MetadataError,
    adjust_timezone,
    build_placeholder_metadata,
    canonical_tags,
    parse_exif_datetime,
    parse_offset,
    parse_xmp,
    read_capture,
    read_media_tags,
    read_mp4_creation_time,
    resolve_date,
)
from app.engine.rules import MetadataRule
from media_helpers import write_id3_audio, write_jpeg, write_mp4, write_png


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------
def test_parse_exif_datetime_variants() -> None:
    assert parse_exif_datetime("2026:11:21 21:40:05") == datetime(2026, 11, 21, 21, 40, 5)
    assert parse_exif_datetime("2026-11-21 21:40:05") == datetime(2026, 11, 21, 21, 40, 5)
    assert parse_exif_datetime("2026:11:21 21:40:05.25") == datetime(
        2026, 11, 21, 21, 40, 5, 250000
    )
    assert parse_exif_datetime(b"2026:11:21 21:40:05\x00") == datetime(
        2026, 11, 21, 21, 40, 5
    )
    assert parse_exif_datetime("2026:11:21") == datetime(2026, 11, 21)
    assert parse_exif_datetime("not a date") is None
    assert parse_exif_datetime(None) is None


def test_parse_timezone_offset() -> None:
    assert parse_offset("+08:00") == 480
    assert parse_offset("-05:30") == -330
    assert parse_offset("+8:00") == 480
    assert parse_offset("") is None
    assert parse_offset("abc") is None


# ---------------------------------------------------------------------------
# EXIF
# ---------------------------------------------------------------------------
def test_exif_datetime_original_with_subsec_and_offset(tmp_path: Path) -> None:
    photo = write_jpeg(
        tmp_path / "photo.jpg",
        "2026:11:21 21:40:05",
        subsec="250",
        offset="+08:00",
    )

    info = read_capture(photo)

    assert info.found
    assert info.source == "exif"
    assert info.taken_at == datetime(2026, 11, 21, 21, 40, 5, 250000)
    assert info.raw == "2026:11:21 21:40:05"
    assert info.offset_minutes == 480
    assert info.utc is False


def test_exif_without_datetime_is_empty(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "plain.jpg", taken=None)

    info = read_capture(photo)

    assert info.found is False
    assert info.source == ""


def test_non_image_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")

    info = read_capture(path)

    assert info.found is False
    assert info.detail


# ---------------------------------------------------------------------------
# MP4 / MOV
# ---------------------------------------------------------------------------
def test_mp4_mvhd_creation_time(tmp_path: Path) -> None:
    created = datetime(2026, 11, 21, 13, 40, 5, tzinfo=timezone.utc)
    video = write_mp4(tmp_path / "clip.mp4", created)

    info = read_capture(video)

    assert info.found
    assert info.source == "video"
    assert info.utc is True
    assert info.taken_at == created.replace(tzinfo=None)
    assert info.raw == "2026-11-21T13:40:05Z"


def test_mvhd_version_one_is_supported(tmp_path: Path) -> None:
    created = datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
    video = write_mp4(tmp_path / "v1.mov", created, version=1)

    assert read_mp4_creation_time(video) == created.replace(tzinfo=None)


def test_mp4_without_moov_is_empty(tmp_path: Path) -> None:
    video = tmp_path / "broken.mp4"
    video.write_bytes(b"\x00\x00\x00\x10ftypisomisom")

    info = read_capture(video)

    assert info.found is False


def test_mp4_zero_creation_time_is_ignored(tmp_path: Path) -> None:
    video = write_mp4(tmp_path / "zero.mp4", datetime(1904, 1, 1, tzinfo=timezone.utc))

    assert read_mp4_creation_time(video) is None


def test_mp4_truncated_does_not_raise(tmp_path: Path) -> None:
    video = tmp_path / "cut.mp4"
    video.write_bytes(b"\x00\x00\x00\x20moov\x00\x00\x00\x08mvhd")

    assert read_mp4_creation_time(video) is None


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------
def test_cache_reuses_result_until_file_changes(tmp_path: Path) -> None:
    cache = CaptureCache()
    photo = write_jpeg(tmp_path / "photo.jpg")

    first = cache.get(photo)
    second = cache.get(photo)

    assert first is second
    assert cache.reads == 1
    assert len(cache) == 1

    os.utime(photo, ns=(1_000_000_000, 1_000_000_000))
    cache.get(photo)
    assert cache.reads == 2


def test_cache_invalidate_and_clear(tmp_path: Path) -> None:
    cache = CaptureCache()
    photo = write_jpeg(tmp_path / "photo.jpg")
    cache.get(photo)

    cache.invalidate(photo)
    assert len(cache) == 0

    cache.get(photo)
    cache.clear()
    assert len(cache) == 0


def test_cache_negative_result_is_cached(tmp_path: Path) -> None:
    cache = CaptureCache()
    note = tmp_path / "note.txt"
    note.write_text("x", encoding="utf-8")

    assert cache.get(note).found is False
    assert cache.get(note).found is False
    assert cache.reads == 1


# ---------------------------------------------------------------------------
# 日期来源与时区
# ---------------------------------------------------------------------------
def test_resolve_date_falls_back_to_mtime() -> None:
    modified = datetime(2026, 1, 2, 3, 4, 5)
    created = datetime(2026, 1, 1, 0, 0, 0)

    resolved = resolve_date(CaptureInfo(), modified, created, MetadataRule())

    assert resolved.value == modified
    assert resolved.fallback is True
    assert "未找到拍摄时间" in resolved.label


def test_resolve_date_respects_explicit_source() -> None:
    modified = datetime(2026, 1, 2, 3, 4, 5)
    created = datetime(2026, 1, 1, 0, 0, 0)
    capture = CaptureInfo(taken_at=datetime(2025, 12, 31, 23, 0, 0), source="exif")

    mtime = resolve_date(capture, modified, created, MetadataRule(date_source="mtime"))
    ctime = resolve_date(capture, modified, created, MetadataRule(date_source="ctime"))
    exif = resolve_date(capture, modified, created, MetadataRule())

    assert mtime.value == modified
    assert ctime.value == created
    assert exif.value == capture.taken_at
    assert exif.label == "EXIF 拍摄时间"
    assert exif.fallback is False


def test_video_time_is_converted_to_local_when_requested() -> None:
    utc_moment = datetime(2026, 11, 21, 13, 40, 5)
    capture = CaptureInfo(taken_at=utc_moment, source="video", utc=True)
    expected = (
        utc_moment.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    )

    assert adjust_timezone(capture, "original") == utc_moment
    assert adjust_timezone(capture, "local") == expected


def test_exif_offset_is_used_for_local_conversion() -> None:
    moment = datetime(2026, 11, 21, 21, 40, 5)
    capture = CaptureInfo(taken_at=moment, source="exif", offset_minutes=480)
    source_zone = timezone(timedelta(minutes=480))
    expected = moment.replace(tzinfo=source_zone).astimezone().replace(tzinfo=None)

    assert adjust_timezone(capture, "original") == moment
    assert adjust_timezone(capture, "local") == expected


# ---------------------------------------------------------------------------
# 占位符数据
# ---------------------------------------------------------------------------
def test_placeholder_metadata_uses_settings(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "photo.jpg", "2026:11:21 21:40:05", subsec="500")
    capture = read_capture(photo)
    settings = MetadataRule(date_format="compact")

    meta = build_placeholder_metadata(photo, capture, settings)

    assert meta["date_format"] == "%Y%m%d"
    assert meta["date"] == datetime(2026, 11, 21, 21, 40, 5, 500000)
    assert meta["time"] == "214005"
    assert meta["year"] == "2026"
    assert meta["exif"] == "2026:11:21 21:40:05"
    assert meta["capture_source"] == "EXIF 拍摄时间"
    assert meta["capture_fallback"] is False


def test_invalid_custom_format_raises(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "photo.jpg")
    settings = MetadataRule(date_format="custom", custom_format="%Y-%m-%d %")

    with pytest.raises(MetadataError, match="日期格式无效"):
        build_placeholder_metadata(photo, read_capture(photo), settings)


def test_empty_custom_format_raises(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "photo.jpg")

    with pytest.raises(MetadataError, match="自定义日期格式为空"):
        build_placeholder_metadata(
            photo,
            read_capture(photo),
            MetadataRule(date_format="custom", custom_format="   "),
        )


class _Frame:
    def __init__(self, text: str) -> None:
        self.text = [text]


def test_image_camera_lens_iso_aperture(tmp_path: Path) -> None:
    photo = write_jpeg(
        tmp_path / "photo.jpg",
        "2024:05:06 07:08:09",
        exif_tags={
            271: "Canon",
            272: "EOS R5",
            42036: "RF24-70mm F2.8 L",
            34855: 400,
            33437: (28, 10),
        },
    )

    info = read_capture(photo)

    assert info.tags["camera"] == "Canon EOS R5"
    assert info.tags["lens"] == "RF24-70mm F2.8 L"
    assert info.tags["iso"] == "400"
    assert info.tags["aperture"] == "f2.8"


def test_xmp_and_png_text_fields(tmp_path: Path) -> None:
    xmp = (
        "<x:xmpmeta><rdf:RDF><rdf:Description>"
        "<dc:title><rdf:Alt><rdf:li>Sunset</rdf:li></rdf:Alt></dc:title>"
        "<xmp:CreateDate>2022-02-03T04:05:06</xmp:CreateDate>"
        "<tiff:Model>X-T5</tiff:Model>"
        "<aux:Lens>XF 23mm</aux:Lens>"
        "<exif:FNumber>2.0</exif:FNumber>"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    png = write_png(
        tmp_path / "image.png",
        text={
            "Title": "PNG Title",
            "Artist": "Alice",
            "Creation Time": "2023-01-02T03:04:05",
            "XML:com.adobe.xmp": xmp,
        },
    )

    info = read_capture(png)

    assert info.source == "xmp"
    assert info.taken_at == datetime(2022, 2, 3, 4, 5, 6)
    assert info.tags["title"] == "Sunset"
    assert info.tags["artist"] == "Alice"
    assert info.tags["camera"] == "X-T5"
    assert info.tags["lens"] == "XF 23mm"
    assert info.tags["aperture"] == "f2"


def test_parse_xmp_variants() -> None:
    xml = (
        "<rdf:RDF><dc:creator><rdf:Seq><rdf:li>Bob</rdf:li></rdf:Seq></dc:creator>"
        "<dc:description><rdf:Alt><rdf:li>Desc</rdf:li></rdf:Alt></dc:description>"
        "<exif:ISOSpeedRatings><rdf:Seq><rdf:li>200</rdf:li></rdf:Seq></exif:ISOSpeedRatings>"
        "</rdf:RDF>"
    )
    tags = parse_xmp(xml)
    assert tags["artist"] == "Bob"
    assert tags["comment"] == "Desc"
    assert tags["iso"] == "200"
    assert parse_xmp("not xml") == {}


def test_canonical_tags_maps_id3_mp4_and_vorbis() -> None:
    id3 = canonical_tags(
        {
            "TIT2": _Frame("Song"),
            "\xa9ART": ["Director"],
            "TALB": ["Series"],
            "DATE": ["2020-05-01"],
            "GENRE": ["Rock"],
        }
    )
    assert id3["title"] == "Song"
    assert id3["artist"] == "Director"
    assert id3["album"] == "Series"
    assert id3["year"] == "2020"

    vorbis = canonical_tags(
        {
            "TITLE": "V Title",
            "ARTIST": "V Artist",
            "ALBUM": "V Album",
            "DATE": "1999",
            "GENRE": "Jazz",
        }
    )
    assert vorbis == {
        "title": "V Title",
        "artist": "V Artist",
        "album": "V Album",
        "date": "1999",
        "genre": "Jazz",
        "year": "1999",
    }


def test_read_audio_id3_tags_and_date(tmp_path: Path) -> None:
    song = write_id3_audio(tmp_path / "song.mp3")

    info = read_capture(song)

    assert info.found
    assert info.source == "audio"
    assert info.taken_at == datetime(2021, 7, 8)
    assert info.tags["title"] == "Song Title"
    assert info.tags["artist"] == "The Artist"
    assert info.tags["album"] == "Album Name"
    assert info.tags["genre"] == "Rock"
    assert info.tags["year"] == "2021"
    assert read_media_tags(song)["title"] == "Song Title"


def test_placeholder_metadata_exposes_media_fields(tmp_path: Path) -> None:
    song = write_id3_audio(tmp_path / "song.mp3")
    info = read_capture(song)

    meta = build_placeholder_metadata(song, info, MetadataRule())

    assert meta["title"] == "Song Title"
    assert meta["artist"] == "The Artist"
    assert meta["album"] == "Album Name"
    assert meta["genre"] == "Rock"
    assert meta["tag_year"] == "2021"
    assert meta["tag_date"] == "2021-07-08"
    assert meta["media_tags"]["artist"] == "The Artist"


def test_placeholder_metadata_image_fields(tmp_path: Path) -> None:
    photo = write_jpeg(
        tmp_path / "photo.jpg",
        exif_tags={272: "X100V", 34855: 160, 33437: (2, 1), 42036: "23mm"},
    )
    info = read_capture(photo)

    meta = build_placeholder_metadata(photo, info, MetadataRule())

    assert meta["camera"] == "X100V"
    assert meta["iso"] == "160"
    assert meta["aperture"] == "f2"
    assert meta["lens"] == "23mm"
