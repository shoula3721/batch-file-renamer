"""Windows 文件名校验、拆分与冲突处理测试。"""
from __future__ import annotations

import pytest

from app.engine.validate import (
    NameConflictError,
    allocate_unique,
    join_name,
    normalize_extension,
    prepare_fs_path,
    split_name,
    to_extended_path,
    utf16_len,
    validate_filename,
)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("a.txt", ("a", "txt")),
        ("a.tar.gz", ("a.tar", "gz")),
        (".gitignore", (".gitignore", "")),
        ("noext", ("noext", "")),
        ("a.", ("a", "")),
        ("a b.mp4", ("a b", "mp4")),
        ("中文 文件.JPG", ("中文 文件", "JPG")),
    ],
)
def test_split_name(filename: str, expected: tuple[str, str]) -> None:
    assert split_name(filename) == expected


def test_join_name() -> None:
    assert join_name("a", "txt") == "a.txt"
    assert join_name("a", "") == "a"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("mp4", "mp4"), (".mp4", "mp4"), ("  .mp4  ", "mp4"), ("", ""), (".", "")],
)
def test_normalize_extension(raw: str, expected: str) -> None:
    assert normalize_extension(raw) == expected


def test_valid_names() -> None:
    assert validate_filename("普通 文件-01_final.mp4") == []
    assert validate_filename(".gitignore") == []
    assert validate_filename("A" * 255) == []


@pytest.mark.parametrize("char", list('<>:"/\\|?*'))
def test_forbidden_characters(char: str) -> None:
    errors = validate_filename(f"a{char}b.txt")
    assert any("非法字符" in message for message in errors)


def test_control_character() -> None:
    errors = validate_filename("a\x01b.txt")
    assert any("控制字符" in message for message in errors)


def test_trailing_space_or_dot() -> None:
    assert any("结尾" in message for message in validate_filename("a.txt "))
    assert any("结尾" in message for message in validate_filename("a.txt."))


@pytest.mark.parametrize("name", ["CON", "con.txt", "COM1", "LPT9.mp4", "nul.tar.gz"])
def test_reserved_names(name: str) -> None:
    assert any("保留名称" in message for message in validate_filename(name))


def test_reserved_like_names_are_allowed() -> None:
    assert validate_filename("CONSOLE.txt") == []
    assert validate_filename("COM10.txt") == []


def test_empty_and_dot_names() -> None:
    assert validate_filename("") == ["文件名不能为空"]
    assert validate_filename(".") == ["文件名不能是 . 或 .."]
    assert validate_filename("..") == ["文件名不能是 . 或 .."]


def test_length_uses_utf16_units() -> None:
    assert utf16_len("abc") == 3
    assert utf16_len("😀") == 2
    assert any("文件名过长" in message for message in validate_filename("A" * 256))
    assert any("文件名过长" in message for message in validate_filename("😀" * 128))


def test_allocate_unique_without_conflict() -> None:
    stem, ext, resolved = allocate_unique("a", "txt", {"b.txt"})
    assert (stem, ext, resolved) == ("a", "txt", False)


def test_allocate_unique_appends_number() -> None:
    taken = {"a.txt", "a (1).txt"}
    stem, ext, resolved = allocate_unique("a", "txt", taken)
    assert (stem, ext, resolved) == ("a (2)", "txt", True)


def test_allocate_unique_is_case_insensitive() -> None:
    stem, ext, resolved = allocate_unique("A", "TXT", {"a.txt"})
    assert (stem, ext, resolved) == ("A (1)", "TXT", True)


def test_allocate_unique_raises_when_disabled() -> None:
    with pytest.raises(NameConflictError):
        allocate_unique("a", "txt", {"a.txt"}, auto_resolve=False)


def test_extended_path_prefix() -> None:
    path = to_extended_path(r"C:\folder\a.txt")
    assert path.startswith("\\\\?\\")
    assert path.endswith(r"C:\folder\a.txt")


def test_extended_unc_path() -> None:
    path = to_extended_path(r"\\server\share\a.txt")
    assert path == r"\\?\UNC\server\share\a.txt"


def test_short_path_is_unchanged() -> None:
    path = prepare_fs_path(r"C:\folder\a.txt")
    assert path == r"C:\folder\a.txt"
