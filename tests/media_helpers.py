"""测试用媒体文件生成：带 EXIF 的 JPEG 与带 mvhd 的 MP4。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

MP4_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)


def write_jpeg(
    path: Path,
    taken: str | None = "2026:11:21 21:40:05",
    *,
    subsec: str | None = None,
    offset: str | None = None,
    exif_tags: dict[int, object] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (24, 16), (180, 40, 40))
    if taken is not None or exif_tags:
        exif = image.getexif()
        if taken is not None:
            exif[36867] = taken
        if subsec is not None:
            exif[37521] = subsec
        if offset is not None:
            exif[36880] = offset
        for tag, value in (exif_tags or {}).items():
            exif[tag] = value
        image.save(path, exif=exif)
    else:
        image.save(path)
    return path


def write_png(path: Path, *, text: dict[str, str] | None = None) -> Path:
    from PIL import PngImagePlugin

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (24, 16), (40, 90, 180))
    info = PngImagePlugin.PngInfo()
    for key, value in (text or {}).items():
        info.add_itxt(key, value)
    image.save(path, pnginfo=info)
    return path


def write_id3_audio(
    path: Path,
    *,
    title: str = "Song Title",
    artist: str = "The Artist",
    album: str = "Album Name",
    date: str = "2021-07-08",
    genre: str = "Rock",
) -> Path:
    from mutagen.id3 import ID3, TALB, TCON, TDRC, TIT2, TPE1

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    tags = ID3()
    tags.add(TIT2(encoding=3, text=[title]))
    tags.add(TPE1(encoding=3, text=[artist]))
    tags.add(TALB(encoding=3, text=[album]))
    tags.add(TDRC(encoding=3, text=[date]))
    tags.add(TCON(encoding=3, text=[genre]))
    tags.save(path)
    return path


def mp4_box(kind: bytes, payload: bytes) -> bytes:
    return (8 + len(payload)).to_bytes(4, "big") + kind + payload


def write_mp4(path: Path, created_utc: datetime, *, version: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    seconds = int((created_utc - MP4_EPOCH).total_seconds())
    if version == 0:
        body = b"\x00\x00\x00\x00" + seconds.to_bytes(4, "big") + b"\x00" * 12
    else:
        body = b"\x01\x00\x00\x00" + seconds.to_bytes(8, "big") + b"\x00" * 16
    payload = (
        mp4_box(b"ftyp", b"isomisom")
        + mp4_box(b"moov", mp4_box(b"mvhd", body))
        + mp4_box(b"mdat", b"\x00" * 16)
    )
    path.write_bytes(payload)
    return path
