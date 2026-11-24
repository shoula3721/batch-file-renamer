"""文件列表模型测试：去重、排序、移动、删除。"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from app.ui.file_list import FileTableModel


@pytest.fixture(scope="module", autouse=True)
def qt_core_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def make_files(directory: Path, names: list[str]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        path = directory / name
        path.write_text(name, encoding="utf-8")
        paths.append(path)
    return paths


def test_add_deduplicates(tmp_path: Path) -> None:
    paths = make_files(tmp_path, ["a.txt", "b.txt"])
    model = FileTableModel()

    added, skipped = model.add_paths(paths + paths)

    assert added == 2
    assert skipped == 2
    assert [entry.path.name for entry in model.entries] == ["a.txt", "b.txt"]


def test_natural_sort(tmp_path: Path) -> None:
    paths = make_files(tmp_path, ["10.txt", "2.txt", "1.txt"])
    model = FileTableModel()
    model.add_paths(paths)

    model.sort_by_key("natural", True)

    assert [entry.path.name for entry in model.entries] == ["1.txt", "2.txt", "10.txt"]


def test_move_multiple_selection_to_top(tmp_path: Path) -> None:
    paths = make_files(tmp_path, ["a.txt", "b.txt", "c.txt", "d.txt"])
    model = FileTableModel()
    model.add_paths(paths)

    rows = model.move_rows([2, 3], -999)

    assert rows == [0, 1]
    assert [entry.path.name for entry in model.entries] == [
        "c.txt",
        "d.txt",
        "a.txt",
        "b.txt",
    ]


def test_move_disjoint_selection_down_one(tmp_path: Path) -> None:
    paths = make_files(tmp_path, ["a.txt", "b.txt", "c.txt", "d.txt"])
    model = FileTableModel()
    model.add_paths(paths)

    rows = model.move_rows([0, 2], 1)

    assert rows == [1, 3]
    assert [entry.path.name for entry in model.entries] == [
        "b.txt",
        "a.txt",
        "d.txt",
        "c.txt",
    ]


def test_remove_rows(tmp_path: Path) -> None:
    paths = make_files(tmp_path, ["a.txt", "b.txt", "c.txt"])
    model = FileTableModel()
    model.add_paths(paths)

    removed = model.remove_rows([0, 2])

    assert removed == 2
    assert [entry.path.name for entry in model.entries] == ["b.txt"]


def test_sort_by_taken_time_falls_back_to_mtime(tmp_path: Path) -> None:
    paths = make_files(tmp_path, ["a.txt", "b.txt", "c.txt"])
    model = FileTableModel()
    model.add_paths(paths)
    entries = {entry.path.name: entry for entry in model.entries}
    entries["a.txt"].taken_at = 3000.0
    entries["b.txt"].taken_at = 1000.0
    entries["c.txt"].taken_at = None
    entries["c.txt"].mtime = 500.0

    model.sort_by_key("taken", True)

    assert [entry.path.name for entry in model.entries] == ["c.txt", "b.txt", "a.txt"]
