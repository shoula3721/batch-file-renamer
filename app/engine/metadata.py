"""拍摄时间与文件属性：EXIF、MP4/MOV 的 mvhd、文件时间，带线程安全缓存。

本模块只依赖标准库与 Pillow，不依赖 Qt，可独立测试。

时间语义：
- EXIF 里的 DateTimeOriginal 是“相机本地时间”，本模块保留原始值（naive）；
  若存在 OffsetTimeOriginal（+08:00 之类），会记录偏移量供“转换为本地时间”使用。
- MP4/MOV 的 mvhd creation_time 按规范是 UTC，本模块标记 utc=True，
  在“转换为本地时间”时再转换。
"""
from __future__ import annotations

import html
import os
import re
import struct
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .rules import MetadataRule

SOURCE_EXIF = "exif"
SOURCE_XMP = "xmp"
SOURCE_IMAGE_TEXT = "image_text"
SOURCE_VIDEO = "video"
SOURCE_VIDEO_TAG = "video_tag"
SOURCE_AUDIO = "audio"
SOURCE_TAG = "tag"

SOURCE_LABELS = {
    SOURCE_EXIF: "EXIF 拍摄时间",
    SOURCE_XMP: "XMP 拍摄时间",
    SOURCE_IMAGE_TEXT: "图片文本时间",
    SOURCE_VIDEO: "视频拍摄时间",
    SOURCE_VIDEO_TAG: "视频标签时间",
    SOURCE_AUDIO: "音频标签时间",
    SOURCE_TAG: "媒体标签时间",
}

IMAGE_EXTENSIONS = frozenset(
    {
        "jpg",
        "jpeg",
        "jpe",
        "jfif",
        "png",
        "tif",
        "tiff",
        "webp",
        "bmp",
        "gif",
        "heic",
        "heif",
        "avif",
        "dng",
        "cr2",
        "nef",
        "arw",
    }
)
VIDEO_EXTENSIONS = frozenset({"mp4", "mov", "m4v", "3gp", "3g2"})
AUDIO_EXTENSIONS = frozenset(
    {
        "mp3",
        "flac",
        "ogg",
        "oga",
        "opus",
        "ape",
        "wav",
        "m4a",
        "m4b",
        "aac",
        "wma",
        "aif",
        "aiff",
        "alac",
    }
)

DATE_PATTERNS = {
    "date": "%Y-%m-%d",
    "compact": "%Y%m%d",
    "datetime": "%Y-%m-%d_%H%M%S",
}
DEFAULT_DATE_PATTERN = DATE_PATTERNS["date"]
DEFAULT_DATETIME_PATTERN = DATE_PATTERNS["datetime"]

# 1904-01-01 00:00:00 UTC，MP4/MOV 的时间起点
_MP4_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)

_EXIF_DATE_TAGS = (
    (36867, "DateTimeOriginal"),
    (36868, "DateTimeDigitized"),
    (306, "DateTime"),
)
_EXIF_SUBSEC_TAGS = (37521, 37520, 37522)
_EXIF_OFFSET_TAGS = (36880, 36881, 36882)

_DATE_RE = re.compile(
    r"^(?P<year>\d{4})[:\-](?P<month>\d{1,2})[:\-](?P<day>\d{1,2})"
    r"(?:[ T](?P<hour>\d{1,2}):(?P<minute>\d{1,2}):(?P<second>\d{1,2}))?"
    r"(?:\.(?P<fraction>\d+))?$"
)


class MetadataError(ValueError):
    """日期格式等元数据设置不合法。"""


@dataclass(frozen=True)
class CaptureInfo:
    """从文件中读到的拍摄时间与媒体标签。

    taken_at 为 None 表示没有可用日期；tags 中保存标题、艺术家、相机等
    归一化后的字段，键名见 TAG_KEYS。
    """

    taken_at: datetime | None = None
    source: str = ""
    raw: str = ""
    utc: bool = False
    offset_minutes: int | None = None
    detail: str = ""
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return self.taken_at is not None

    @property
    def label(self) -> str:
        return SOURCE_LABELS.get(self.source, "拍摄时间")


@dataclass(frozen=True)
class ResolvedDate:
    value: datetime
    label: str
    fallback: bool = False


# ---------------------------------------------------------------------------
# 标签归一化
# ---------------------------------------------------------------------------
TAG_KEYS = (
    "title",
    "artist",
    "album",
    "genre",
    "date",
    "year",
    "comment",
    "albumartist",
    "composer",
    "director",
    "series",
    "camera",
    "lens",
    "iso",
    "aperture",
)

_TAG_ALIASES: dict[str, frozenset[str]] = {
    "title": frozenset(
        {"title", "tit2", "tt2", "©nam", "\xa9nam", "name", "dc:title"}
    ),
    "artist": frozenset(
        {"artist", "tpe1", "tp1", "©art", "\xa9art", "author", "dc:creator", "performer"}
    ),
    "album": frozenset(
        {"album", "talb", "tal", "©alb", "\xa9alb", "series", "tvsh", "grouping", "tit1"}
    ),
    "genre": frozenset({"genre", "tcon", "tco", "©gen", "\xa9gen", "style"}),
    "date": frozenset(
        {
            "date",
            "tdrc",
            "tyer",
            "tdrl",
            "tdor",
            "©day",
            "\xa9day",
            "year",
            "originaldate",
            "creationdate",
            "creation time",
            "date:create",
            "xmp:createdate",
            "photoshop:datecreated",
        }
    ),
    "year": frozenset({"year", "tyer"}),
    "comment": frozenset({"comment", "comm", "©cmt", "\xa9cmt", "description", "desc"}),
    "albumartist": frozenset({"albumartist", "tpe2", "tp2", "aart"}),
    "composer": frozenset({"composer", "tcom", "©wrt", "\xa9wrt"}),
    "director": frozenset({"director", "©dir", "\xa9dir"}),
    "series": frozenset({"series", "tvsh", "tit1"}),
    "camera": frozenset(
        {"camera", "model", "tiff:model", "aux:model", "make", "tiff:make"}
    ),
    "lens": frozenset(
        {"lens", "lensmodel", "aux:lens", "exifex:lensmodel", "exif:lensmodel"}
    ),
    "iso": frozenset(
        {
            "iso",
            "isospeedratings",
            "photographicsensitivity",
            "exif:isospeedratings",
        }
    ),
    "aperture": frozenset({"aperture", "fnumber", "exif:fnumber", "aperturevalue"}),
}


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                text = value.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = value.decode("utf-8", "ignore")
    elif isinstance(value, (list, tuple)):
        parts = [_clean_text(item) for item in value]
        text = "; ".join(part for part in parts if part)
    else:
        text = str(value)
    return text.replace("\x00", "").strip()


def _stringify_tag(value: object) -> str:
    """把 mutagen 的帧 / 列表 / 字节统一成可读字符串。"""
    text_attr = getattr(value, "text", None)
    if text_attr is not None:
        return _clean_text(text_attr)
    if isinstance(value, (list, tuple)):
        parts = [_stringify_tag(item) for item in value]
        return "; ".join(part for part in parts if part)
    if isinstance(value, bytes):
        return _clean_text(value)
    return _clean_text(value)


def _normalize_key(key: object) -> str:
    text = _clean_text(key).lower()
    if text.startswith("----:"):
        text = text.split(":")[-1]
    return text


def _format_number(value: object) -> str:
    """把 28/10、2.8、['2.8'] 等统一成简洁数字。"""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            denominator = float(value[1])
            return f"{float(value[0]) / denominator:g}" if denominator else ""
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        try:
            denominator = float(value.denominator)
            return f"{float(value.numerator) / denominator:g}" if denominator else ""
        except (TypeError, ValueError, ZeroDivisionError):
            return ""
    text = _clean_text(value)
    if not text:
        return ""
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        try:
            return f"{float(numerator) / float(denominator):g}"
        except (ValueError, ZeroDivisionError):
            return text
    try:
        return f"{float(text):g}"
    except ValueError:
        return text


def _format_aperture(value: object) -> str:
    number = _format_number(value)
    if not number:
        return ""
    # 文件名里不能出现 /，统一写成 f2.8 形式
    if number.lower().startswith("f/"):
        number = "f" + number[2:]
    elif number.lower().startswith("f"):
        return number
    else:
        number = "f" + number
    return number


def _format_iso(value: object) -> str:
    number = _format_number(value)
    return number


def _format_camera(make: object, model: object) -> str:
    make_text = _clean_text(make)
    model_text = _clean_text(model)
    if not model_text:
        return make_text
    if make_text and not model_text.lower().startswith(make_text.lower()):
        return f"{make_text} {model_text}"
    return model_text


def canonical_tags(raw: Mapping[object, object]) -> dict[str, str]:
    """把不同容器的标签键归一化为 title/artist/album 等字段。"""
    result: dict[str, str] = {}
    for key, value in raw.items():
        normalized = _normalize_key(key)
        text = _stringify_tag(value)
        if not normalized or not text:
            continue
        for canonical, aliases in _TAG_ALIASES.items():
            if normalized not in aliases:
                continue
            if canonical == "camera" and normalized == "make" and result.get("camera"):
                continue
            if canonical in result and result[canonical]:
                continue
            result[canonical] = text
    if not result.get("year") and result.get("date"):
        match = re.search(r"(19|20)\d{2}", result["date"])
        if match:
            result["year"] = match.group(0)
    if result.get("series") and not result.get("album"):
        result["album"] = result["series"]
    if result.get("director") and not result.get("artist"):
        result["artist"] = result["director"]
    return result


def _strip_xml(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _xmp_field(xml: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, xml, re.IGNORECASE | re.DOTALL)
        if match:
            value = _strip_xml(match.group(1))
            if value:
                return value
    return ""


def parse_xmp(text: object) -> dict[str, str]:
    """从 XMP 包中提取标题、创作者、日期、相机、镜头、ISO、光圈等字段。"""
    xml = _clean_text(text)
    if not xml or "<" not in xml:
        return {}
    tags: dict[str, str] = {}
    title = _xmp_field(
        xml,
        [
            r"<dc:title[^>]*>.*?<rdf:li[^>]*>(.*?)</rdf:li>",
            r"<dc:title[^>]*>(.*?)</dc:title>",
        ],
    )
    creator = _xmp_field(
        xml,
        [
            r"<dc:creator[^>]*>.*?<rdf:li[^>]*>(.*?)</rdf:li>",
            r"<dc:creator[^>]*>(.*?)</dc:creator>",
        ],
    )
    description = _xmp_field(
        xml,
        [
            r"<dc:description[^>]*>.*?<rdf:li[^>]*>(.*?)</rdf:li>",
            r"<dc:description[^>]*>(.*?)</dc:description>",
        ],
    )
    date = _xmp_field(
        xml,
        [
            r"<xmp:CreateDate[^>]*>(.*?)</xmp:CreateDate>",
            r"<photoshop:DateCreated[^>]*>(.*?)</photoshop:DateCreated>",
            r"<xmp:MetadataDate[^>]*>(.*?)</xmp:MetadataDate>",
        ],
    )
    camera = _xmp_field(
        xml,
        [
            r"<tiff:Model[^>]*>(.*?)</tiff:Model>",
            r"<aux:Model[^>]*>(.*?)</aux:Model>",
        ],
    )
    lens = _xmp_field(
        xml,
        [
            r"<aux:Lens[^>]*>(.*?)</aux:Lens>",
            r"<exifEX:LensModel[^>]*>(.*?)</exifEX:LensModel>",
        ],
    )
    iso = _xmp_field(
        xml,
        [
            r"<exif:ISOSpeedRatings[^>]*>.*?<rdf:li[^>]*>(.*?)</rdf:li>",
            r"<exif:PhotographicSensitivity[^>]*>(.*?)</exif:PhotographicSensitivity>",
        ],
    )
    aperture = _xmp_field(
        xml,
        [
            r"<exif:FNumber[^>]*>(.*?)</exif:FNumber>",
            r"<exif:ApertureValue[^>]*>(.*?)</exif:ApertureValue>",
        ],
    )
    genre = _xmp_field(
        xml,
        [
            r"<xmp:Genre[^>]*>(.*?)</xmp:Genre>",
            r"<dc:subject[^>]*>.*?<rdf:li[^>]*>(.*?)</rdf:li>",
        ],
    )
    for key, value in (
        ("title", title),
        ("artist", creator),
        ("comment", description),
        ("date", date),
        ("camera", camera),
        ("lens", lens),
        ("iso", iso),
        ("aperture", aperture),
        ("genre", genre),
    ):
        if value:
            tags[key] = value
    if tags.get("aperture"):
        tags["aperture"] = _format_aperture(tags["aperture"])
    if not tags.get("year") and tags.get("date"):
        match = re.search(r"(19|20)\d{2}", tags["date"])
        if match:
            tags["year"] = match.group(0)
    return tags


def _parse_media_datetime(text: object) -> datetime | None:
    value = _clean_text(text)
    if not value:
        return None
    year_only = re.match(r"^(19|20)\d{2}$", value)
    if year_only:
        try:
            return datetime(int(value), 1, 1)
        except ValueError:
            return None
    parsed = parse_exif_datetime(value)
    if parsed is not None:
        return parsed
    cleaned = value.replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    return moment.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# EXIF
# ---------------------------------------------------------------------------
def parse_exif_datetime(text: object) -> datetime | None:
    """解析 2026:11:21 21:40:05（也接受 - 分隔、缺秒、带小数秒）。"""
    if text is None:
        return None
    if isinstance(text, bytes):
        text = text.decode("utf-8", "ignore")
    cleaned = str(text).replace("\x00", "").strip()
    match = _DATE_RE.match(cleaned)
    if not match:
        return None
    parts = match.groupdict()
    fraction = parts.get("fraction") or ""
    microsecond = int((fraction + "000000")[:6]) if fraction else 0
    try:
        return datetime(
            int(parts["year"]),
            int(parts["month"]),
            int(parts["day"]),
            int(parts.get("hour") or 0),
            int(parts.get("minute") or 0),
            int(parts.get("second") or 0),
            microsecond,
        )
    except ValueError:
        return None


def parse_offset(text: object) -> int | None:
    """解析 EXIF 的时区偏移，如 +08:00 -> 480。"""
    if text is None:
        return None
    if isinstance(text, bytes):
        text = text.decode("utf-8", "ignore")
    match = re.match(r"^\s*([+-])(\d{1,2}):?(\d{2})\s*$", str(text).replace("\x00", ""))
    if not match:
        return None
    sign = 1 if match.group(1) == "+" else -1
    hours = int(match.group(2))
    minutes = int(match.group(3))
    if hours > 23 or minutes > 59:
        return None
    return sign * (hours * 60 + minutes)


def _exif_value(exif: Any, exif_ifd: Mapping[int, Any], tag: int) -> Any:
    value = exif_ifd.get(tag) if exif_ifd else None
    if value in (None, ""):
        try:
            value = exif.get(tag)
        except (AttributeError, KeyError):
            value = None
    return value


def read_exif(path: str | Path) -> CaptureInfo:
    """读取图片元数据：EXIF、XMP、PNG iTXt 文本与拍摄参数。

    函数名保留为 read_exif 兼容旧调用；失败时返回带 detail 的空结果，不抛异常。
    """
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow 是必装依赖
        return CaptureInfo(detail="未安装 Pillow，无法读取 EXIF")

    try:
        with Image.open(path) as image:
            info: Mapping[object, object] = getattr(image, "info", {}) or {}
            text_dict: dict[str, str] = {}
            text_attr = getattr(image, "text", None)
            if isinstance(text_attr, Mapping):
                for key, value in text_attr.items():
                    text_dict[str(key)] = _clean_text(value)
            for key, value in info.items():
                if isinstance(key, str) and isinstance(value, str):
                    text_dict.setdefault(key, value)

            exif = image.getexif()
            exif_ifd: Mapping[int, Any] = {}
            if exif:
                try:
                    exif_ifd = exif.get_ifd(0x8769) or {}
                except (KeyError, ValueError, OSError, AttributeError):
                    exif_ifd = {}

            tags: dict[str, str] = {}
            if exif:
                camera = _format_camera(
                    _exif_value(exif, exif_ifd, 271),
                    _exif_value(exif, exif_ifd, 272),
                )
                lens = _clean_text(_exif_value(exif, exif_ifd, 42036))
                iso = _format_iso(_exif_value(exif, exif_ifd, 34855))
                aperture = _format_aperture(_exif_value(exif, exif_ifd, 33437))
                for key, value in (
                    ("camera", camera),
                    ("lens", lens),
                    ("iso", iso),
                    ("aperture", aperture),
                ):
                    if value:
                        tags[key] = value

            # XMP：JPEG APP1、PNG iTXt、EXIF tag 700 都可能携带
            xmp_candidates: list[object] = [
                info.get("xmp"),
                info.get("XML:com.adobe.xmp"),
                text_dict.get("XML:com.adobe.xmp"),
                text_dict.get("xmp"),
            ]
            if exif:
                xmp_candidates.append(_exif_value(exif, exif_ifd, 700))
            xmp_tags: dict[str, str] = {}
            for candidate in xmp_candidates:
                parsed = parse_xmp(candidate)
                for key, value in parsed.items():
                    xmp_tags.setdefault(key, value)

            # PNG iTXt / tEXt 常用键
            text_tags: dict[str, str] = {}
            text_keys = {
                "title": "title",
                "artist": "artist",
                "author": "artist",
                "album": "album",
                "genre": "genre",
                "year": "year",
                "date": "date",
                "creation time": "date",
                "creation_time": "date",
                "description": "comment",
                "comment": "comment",
            }
            for key, value in text_dict.items():
                canonical = text_keys.get(key.strip().casefold())
                if canonical and value and canonical not in text_tags:
                    text_tags[canonical] = value

            for source_tags in (xmp_tags, text_tags):
                for key, value in source_tags.items():
                    if value and key not in tags:
                        tags[key] = value

            taken_raw: Any = None
            taken_at: datetime | None = None
            source = ""
            detail = ""

            if exif:
                for tag, name in _EXIF_DATE_TAGS:
                    value = _exif_value(exif, exif_ifd, tag)
                    parsed = parse_exif_datetime(value)
                    if parsed is not None:
                        taken_raw = value
                        taken_at = parsed
                        source = SOURCE_EXIF
                        detail = name
                        break
                if taken_at is not None:
                    microsecond = 0
                    for tag in _EXIF_SUBSEC_TAGS:
                        value = _exif_value(exif, exif_ifd, tag)
                        if value is not None and str(value).strip().isdigit():
                            digits = str(value).strip()
                            microsecond = int((digits + "000000")[:6])
                            break
                    if microsecond:
                        taken_at = taken_at.replace(microsecond=microsecond)

            if taken_at is None and xmp_tags.get("date"):
                taken_at = _parse_media_datetime(xmp_tags["date"])
                if taken_at is not None:
                    source = SOURCE_XMP
                    taken_raw = xmp_tags["date"]
                    detail = "XMP CreateDate"
            if taken_at is None and text_tags.get("date"):
                taken_at = _parse_media_datetime(text_tags["date"])
                if taken_at is not None:
                    source = SOURCE_IMAGE_TEXT
                    taken_raw = text_tags["date"]
                    detail = "PNG text"

            if not tags and taken_at is None:
                return CaptureInfo()

            offset = None
            if exif:
                for tag in _EXIF_OFFSET_TAGS:
                    value = _exif_value(exif, exif_ifd, tag)
                    offset = parse_offset(value)
                    if offset is not None:
                        break
            raw = _clean_text(taken_raw)
            if taken_at is not None and not raw:
                raw = taken_at.strftime("%Y-%m-%d_%H%M%S")
            if taken_at is not None:
                tags.setdefault("date", raw)
                tags.setdefault("year", f"{taken_at.year:04d}")
            return CaptureInfo(
                taken_at=taken_at,
                source=source,
                raw=raw,
                offset_minutes=offset,
                detail=detail or "标签",
                tags=tags,
            )
    except (OSError, ValueError, SyntaxError):
        return CaptureInfo(detail="无法读取图片元数据")
    except Exception:  # noqa: BLE001 - 第三方解码器可能抛任意异常
        return CaptureInfo(detail="图片元数据读取失败")


# ---------------------------------------------------------------------------
# MP4 / MOV
# ---------------------------------------------------------------------------
def _iter_boxes(stream: Any, start: int, end: int) -> Iterable[tuple[bytes, int, int]]:
    """遍历 [start, end) 内的 ISO BMFF box，产出 (类型, 数据起点, box 终点)。"""
    position = start
    while position + 8 <= end:
        stream.seek(position)
        header = stream.read(8)
        if len(header) < 8:
            return
        size = int.from_bytes(header[:4], "big")
        kind = bytes(header[4:8])
        header_size = 8
        if size == 1:
            extended = stream.read(8)
            if len(extended) < 8:
                return
            size = int.from_bytes(extended, "big")
            header_size = 16
        elif size == 0:
            size = end - position
        if size < header_size or position + size > end:
            return
        yield kind, position + header_size, position + size
        position += size


def _find_box(stream: Any, start: int, end: int, kind: bytes) -> tuple[int, int] | None:
    for box_kind, data_start, box_end in _iter_boxes(stream, start, end):
        if box_kind == kind:
            return data_start, box_end
    return None


def read_mp4_creation_time(path: str | Path) -> datetime | None:
    """解析 MP4/MOV 的 moov/mvhd creation_time，返回 UTC（naive）。"""
    try:
        with open(path, "rb") as stream:
            stream.seek(0, os.SEEK_END)
            total = stream.tell()
            moov = _find_box(stream, 0, total, b"moov")
            if moov is None:
                return None
            mvhd = _find_box(stream, moov[0], moov[1], b"mvhd")
            if mvhd is None:
                return None
            stream.seek(mvhd[0])
            head = stream.read(12)
            if len(head) < 8:
                return None
            version = head[0]
            if version == 0:
                seconds = int.from_bytes(head[4:8], "big")
            else:
                stream.seek(mvhd[0] + 4)
                extended = stream.read(8)
                if len(extended) < 8:
                    return None
                seconds = int.from_bytes(extended, "big")
    except (OSError, ValueError, struct.error):
        return None
    if seconds <= 0:
        return None
    try:
        moment = _MP4_EPOCH + timedelta(seconds=seconds)
    except OverflowError:
        return None
    # 过滤明显错误的 1970/1980 以前的值（很多编码器写 0 或 2082844800）
    if moment.year < 1970:
        return None
    return moment.replace(tzinfo=None)


def read_media_tags(path: str | Path) -> dict[str, str]:
    """读取音频 / 视频容器标签（ID3、APE、Vorbis、MP4 等），归一化字段。"""
    try:
        from mutagen import File as MutagenFile
    except ImportError:  # pragma: no cover - 打包时会包含 mutagen
        return {}

    tags_object: Any = None
    try:
        media = MutagenFile(path)
    except Exception:  # noqa: BLE001 - 损坏文件不应影响预览
        media = None
    if media is not None:
        tags_object = getattr(media, "tags", None)
    if tags_object is None and Path(path).suffix.lower() == ".mp3":
        try:
            from mutagen.id3 import ID3

            tags_object = ID3(path)
        except Exception:  # noqa: BLE001
            tags_object = None
    if tags_object is None:
        return {}
    try:
        raw = dict(tags_object)
    except (TypeError, ValueError):
        return {}
    return canonical_tags(raw)


def read_audio(path: str | Path) -> CaptureInfo:
    """读取音频标签与发行/录制日期。"""
    tags = read_media_tags(path)
    moment: datetime | None = None
    raw = tags.get("date", "")
    if raw:
        moment = _parse_media_datetime(raw)
    if moment is None and tags.get("year"):
        moment = _parse_media_datetime(tags["year"])
    return CaptureInfo(
        taken_at=moment,
        source=SOURCE_AUDIO if moment is not None else "",
        raw=raw,
        detail="音频标签" if tags else "",
        tags=tags,
    )


def read_video(path: str | Path) -> CaptureInfo:
    tags = read_media_tags(path)
    moment = read_mp4_creation_time(path)
    source = SOURCE_VIDEO
    raw = ""
    detail = ""
    if moment is not None:
        raw = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        detail = "mvhd creation_time"
    elif tags.get("date"):
        moment = _parse_media_datetime(tags["date"])
        if moment is not None:
            source = SOURCE_VIDEO_TAG
            raw = tags["date"]
            detail = "MP4 标签日期"
    return CaptureInfo(
        taken_at=moment,
        source=source if moment is not None else "",
        raw=raw,
        utc=source == SOURCE_VIDEO,
        detail=detail,
        tags=tags,
    )


# ---------------------------------------------------------------------------
# 统一入口与缓存
# ---------------------------------------------------------------------------
def read_capture(path: str | Path) -> CaptureInfo:
    """按扩展名读取图片 / 音频 / 视频元数据；未知格式依次尝试。"""
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in VIDEO_EXTENSIONS:
        return read_video(path)
    if suffix in AUDIO_EXTENSIONS:
        return read_audio(path)
    info = read_exif(path)
    if info.found or info.tags:
        return info
    if suffix in IMAGE_EXTENSIONS:
        return info
    audio_info = read_audio(path)
    return audio_info if (audio_info.found or audio_info.tags) else info


def _file_key(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


class CaptureCache:
    """按 (路径, mtime_ns, 大小) 缓存拍摄时间；文件被修改后自动失效。"""

    def __init__(self, max_items: int = 20000) -> None:
        self._lock = threading.RLock()
        self._items: OrderedDict[str, tuple[tuple[int, int], CaptureInfo]] = OrderedDict()
        self._max_items = max(1, max_items)
        self._reads = 0

    def get(
        self,
        path: str | Path,
        *,
        stat: os.stat_result | None = None,
        refresh: bool = False,
    ) -> CaptureInfo:
        try:
            file_stat = stat or os.stat(path)
        except OSError:
            return CaptureInfo(detail="无法读取文件属性")
        stamp = (file_stat.st_mtime_ns, file_stat.st_size)
        key = _file_key(path)
        with self._lock:
            cached = self._items.get(key)
            if cached is not None and cached[0] == stamp and not refresh:
                self._items.move_to_end(key)
                return cached[1]
        info = read_capture(path)
        with self._lock:
            self._items[key] = (stamp, info)
            self._items.move_to_end(key)
            self._reads += 1
            while len(self._items) > self._max_items:
                self._items.popitem(last=False)
        return info

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def invalidate(self, path: str | Path) -> None:
        with self._lock:
            self._items.pop(_file_key(path), None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    @property
    def reads(self) -> int:
        with self._lock:
            return self._reads


# ---------------------------------------------------------------------------
# 占位符数据
# ---------------------------------------------------------------------------
def format_pattern(settings: MetadataRule) -> str:
    """把界面上的日期格式选项转成 strftime 模式。"""
    if settings.date_format == "custom":
        pattern = settings.custom_format.strip()
        if not pattern:
            raise MetadataError("自定义日期格式为空")
        return pattern
    return DATE_PATTERNS.get(settings.date_format, DEFAULT_DATE_PATTERN)


def adjust_timezone(capture: CaptureInfo, mode: str) -> datetime:
    """按设置把拍摄时间转换为本地时间；无时区信息时原样返回。"""
    moment = capture.taken_at
    if moment is None:
        raise ValueError("没有拍摄时间")
    if mode != "local":
        return moment
    if capture.utc:
        return (
            moment.replace(tzinfo=timezone.utc)
            .astimezone()
            .replace(tzinfo=None)
        )
    if capture.offset_minutes is not None:
        source_zone = timezone(timedelta(minutes=capture.offset_minutes))
        return moment.replace(tzinfo=source_zone).astimezone().replace(tzinfo=None)
    return moment


def resolve_date(
    capture: CaptureInfo | None,
    modified: datetime,
    created: datetime,
    settings: MetadataRule,
) -> ResolvedDate:
    """按“日期来源”选出用于命名的日期，并给出来源说明。"""
    source = settings.date_source
    if source == "mtime":
        return ResolvedDate(modified, "文件修改时间")
    if source == "ctime":
        return ResolvedDate(created, "文件创建时间")
    if capture is not None and capture.found:
        moment = adjust_timezone(capture, settings.timezone)
        label = capture.label
        if capture.utc:
            label += "（UTC → 本地）" if settings.timezone == "local" else "（UTC）"
        elif settings.timezone == "local" and capture.offset_minutes is not None:
            label += "（已转换为本地时间）"
        return ResolvedDate(moment, label)
    return ResolvedDate(modified, "文件修改时间（未找到拍摄时间）", fallback=True)


def build_placeholder_metadata(
    path: str | Path,
    capture: CaptureInfo | None,
    settings: MetadataRule,
    *,
    stat: os.stat_result | None = None,
) -> dict[str, Any]:
    """构造 {date}、{size} 等占位符的取值；日期格式非法时抛 MetadataError。"""
    file_stat = stat or os.stat(path)
    modified = datetime.fromtimestamp(file_stat.st_mtime)
    created = datetime.fromtimestamp(file_stat.st_ctime)
    resolved = resolve_date(capture, modified, created, settings)
    chosen = resolved.value
    pattern = format_pattern(settings)
    try:
        date_text = chosen.strftime(pattern)
        chosen.strftime(DEFAULT_DATETIME_PATTERN)
    except ValueError as exc:
        raise MetadataError(f"日期格式无效：{exc}") from exc

    info = capture or CaptureInfo()
    tags = dict(info.tags or {})
    title = tags.get("title", "")
    artist = tags.get("artist", "") or tags.get("director", "")
    album = tags.get("album", "") or tags.get("series", "")
    tag_date_raw = tags.get("date", "")
    tag_date = tag_date_raw
    if tag_date_raw:
        parsed_tag_date = _parse_media_datetime(tag_date_raw)
        if parsed_tag_date is not None:
            tag_date = parsed_tag_date.strftime("%Y-%m-%d")
    return {
        "size": file_stat.st_size,
        "mtime": modified,
        "ctime": created,
        "date": chosen,
        "datetime": chosen,
        "date_format": pattern,
        "date_text": date_text,
        "time": chosen.strftime("%H%M%S"),
        "year": f"{chosen.year:04d}",
        "month": f"{chosen.month:02d}",
        "day": f"{chosen.day:02d}",
        "hour": f"{chosen.hour:02d}",
        "min": f"{chosen.minute:02d}",
        "sec": f"{chosen.second:02d}",
        "exif": info.raw or "",
        "title": title,
        "artist": artist,
        "album": album,
        "genre": tags.get("genre", ""),
        "tag_year": tags.get("year", ""),
        "tag_date": tag_date,
        "camera": tags.get("camera", ""),
        "lens": tags.get("lens", ""),
        "iso": tags.get("iso", ""),
        "aperture": tags.get("aperture", ""),
        # 仅供界面显示，不参与命名
        "capture_at": chosen,
        "capture_timestamp": chosen.timestamp(),
        "capture_source": resolved.label,
        "capture_raw": info.raw,
        "capture_fallback": resolved.fallback,
        "capture_detail": info.detail,
        "media_tags": tags,
    }


def capture_time_text(capture: CaptureInfo | None) -> str:
    """给状态栏/提示使用的简短描述。"""
    if capture is None or not capture.found:
        return "未检测到拍摄时间"
    moment = capture.taken_at
    assert moment is not None
    return moment.strftime("%Y-%m-%d %H:%M:%S")
