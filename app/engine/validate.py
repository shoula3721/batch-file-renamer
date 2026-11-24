"""文件名拆分、Windows 合法性校验与冲突处理。"""
from __future__ import annotations

import os
from pathlib import Path

MAX_NAME_UNITS = 255
LONG_PATH_THRESHOLD = 240

FORBIDDEN_CHARS = frozenset('<>:"/\\|?*')
RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


class NameConflictError(ValueError):
    """目标名称已存在且未开启自动解决。"""


def utf16_len(text: str) -> int:
    """Windows 文件名长度按 UTF-16 码元计算，emoji 占 2。"""
    return len(text.encode("utf-16-le")) // 2


def split_name(filename: str) -> tuple[str, str]:
    """拆成 (主体, 扩展名)，扩展名不含点。

    - "a.txt"      -> ("a", "txt")
    - "a.tar.gz"   -> ("a.tar", "gz")
    - ".gitignore" -> (".gitignore", "")
    - "a."         -> ("a", "")
    """
    index = filename.rfind(".")
    if index <= 0:
        return filename, ""
    return filename[:index], filename[index + 1 :]


def join_name(stem: str, ext: str) -> str:
    return f"{stem}.{ext}" if ext else stem


def normalize_extension(value: str) -> str:
    """允许用户输入 "mp4"、".mp4"、" .mp4 "。"""
    return value.strip().lstrip(".").strip()


def validate_filename(name: str) -> list[str]:
    """返回全部错误信息；空列表表示合法。"""
    errors: list[str] = []
    if not name:
        return ["文件名不能为空"]
    if name in {".", ".."}:
        return ["文件名不能是 . 或 .."]

    bad_chars = sorted({char for char in name if char in FORBIDDEN_CHARS})
    if bad_chars:
        errors.append("包含非法字符：" + " ".join(bad_chars))

    if any(ord(char) < 32 for char in name):
        errors.append("包含控制字符")

    if name[-1] in " .":
        errors.append("文件名不能以空格或点结尾")

    reserved_key = name.split(".")[0].upper()
    if reserved_key in RESERVED_NAMES:
        errors.append(f"“{reserved_key}”是 Windows 保留名称")

    length = utf16_len(name)
    if length > MAX_NAME_UNITS:
        errors.append(f"文件名过长（{length}/{MAX_NAME_UNITS} 个字符）")

    return errors


def allocate_unique(
    stem: str,
    ext: str,
    taken: set[str],
    auto_resolve: bool = True,
) -> tuple[str, str, bool]:
    """在 taken（全部小写化）中分配不冲突的名称。

    返回 (主体, 扩展名, 是否追加了序号)。
    """
    if join_name(stem, ext).casefold() not in taken:
        return stem, ext, False
    if not auto_resolve:
        raise NameConflictError(f"目标名称已存在：{join_name(stem, ext)}")
    for number in range(1, 10000):
        candidate_stem = f"{stem} ({number})"
        if join_name(candidate_stem, ext).casefold() not in taken:
            return candidate_stem, ext, True
    raise NameConflictError("自动解决命名冲突失败：尝试次数超过 9999 次")


def to_extended_path(path: str | Path) -> str:
    """转换为 Windows 长路径形式（\\\\?\\ 或 UNC 形式）。"""
    absolute = os.path.abspath(str(path))
    if absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def prepare_fs_path(path: str | Path) -> str:
    """路径较长时才加长路径前缀，普通路径保持原样便于日志阅读。"""
    absolute = os.path.abspath(str(path))
    if utf16_len(absolute) < LONG_PATH_THRESHOLD:
        return absolute
    return to_extended_path(absolute)
