"""两阶段执行器测试（真实临时文件）。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.engine.backup import (
    BackupError,
    BackupStore,
    STATE_COMPLETED,
    STATE_COMPLETED_WITH_ERRORS,
    STATE_RENAMING,
    STATUS_OK,
    STATUS_SKIPPED,
)
from app.engine.executor import RenameExecutor, RenameItem
from app.engine.namer import plan_batch
from app.engine.rules import OverallRule, RuleSet


@pytest.fixture
def store(tmp_path: Path) -> BackupStore:
    return BackupStore(tmp_path / "backups")


def write_files(directory: Path, names: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_text(f"content:{name}", encoding="utf-8")


def make_items(directory: Path, pairs: list[tuple[str, str]]) -> list[RenameItem]:
    return [RenameItem(directory / old, directory / new) for old, new in pairs]


def names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_simple_rename(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt", "c.txt"])

    result = RenameExecutor(store).execute(
        make_items(folder, [("a.txt", "x.txt"), ("b.txt", "y.txt"), ("c.txt", "z.txt")])
    )

    assert result.success == 3
    assert result.failed == 0
    assert result.state == STATE_COMPLETED
    assert names(folder) == ["x.txt", "y.txt", "z.txt"]
    assert not list(folder.glob("*.tmp"))

    record = store.load(result.backup_path)
    assert record.state == STATE_COMPLETED
    assert all(item.status == STATUS_OK for item in record.items)
    assert all(item.temp == "" for item in record.items)


def test_swap_does_not_deadlock(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    folder.mkdir()
    (folder / "1.txt").write_text("ONE", encoding="utf-8")
    (folder / "2.txt").write_text("TWO", encoding="utf-8")

    result = RenameExecutor(store).execute(
        make_items(folder, [("1.txt", "2.txt"), ("2.txt", "1.txt")])
    )

    assert result.success == 2
    assert (folder / "1.txt").read_text(encoding="utf-8") == "TWO"
    assert (folder / "2.txt").read_text(encoding="utf-8") == "ONE"


def test_chain_rename(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["1.txt", "2.txt", "3.txt"])

    result = RenameExecutor(store).execute(
        make_items(folder, [("1.txt", "2.txt"), ("2.txt", "3.txt"), ("3.txt", "4.txt")])
    )

    assert result.success == 3
    assert names(folder) == ["2.txt", "3.txt", "4.txt"]


def test_case_only_rename(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])

    result = RenameExecutor(store).execute(make_items(folder, [("a.txt", "A.txt")]))

    assert result.success == 1
    assert names(folder) == ["A.txt"]


def test_unchanged_is_skipped(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])

    result = RenameExecutor(store).execute(make_items(folder, [("a.txt", "a.txt")]))

    assert result.skipped == 1
    assert result.success == 0
    record = store.load(result.backup_path)
    assert record.items[0].status == STATUS_SKIPPED


def test_existing_target_fails_without_touching_files(
    store: BackupStore, tmp_path: Path
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt"])

    result = RenameExecutor(store).execute(make_items(folder, [("a.txt", "b.txt")]))

    assert result.failed == 1
    assert "已存在" in result.errors[0].error
    assert result.state == STATE_COMPLETED_WITH_ERRORS
    assert (folder / "a.txt").read_text(encoding="utf-8") == "content:a.txt"
    assert (folder / "b.txt").read_text(encoding="utf-8") == "content:b.txt"


def test_duplicate_targets_are_rejected(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt"])

    result = RenameExecutor(store).execute(
        make_items(folder, [("a.txt", "x.txt"), ("b.txt", "x.txt")])
    )

    assert result.failed == 2
    assert all("重复" in item.error for item in result.errors)
    assert names(folder) == ["a.txt", "b.txt"]


def test_missing_source_does_not_stop_batch(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])

    result = RenameExecutor(store).execute(
        make_items(folder, [("ghost.txt", "g.txt"), ("a.txt", "b.txt")])
    )

    assert result.failed == 1
    assert result.success == 1
    assert names(folder) == ["b.txt"]


def test_invalid_target_is_rejected(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])

    result = RenameExecutor(store).execute(
        make_items(folder, [("a.txt", "bad|name.txt")])
    )

    assert result.failed == 1
    assert "非法字符" in result.errors[0].error
    assert names(folder) == ["a.txt"]


def test_directory_source_is_rejected(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    folder.mkdir()
    (folder / "sub").mkdir()

    result = RenameExecutor(store).execute(make_items(folder, [("sub", "sub2")]))

    assert result.failed == 1
    assert "文件夹" in result.errors[0].error


def test_target_is_directory(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    (folder / "x").mkdir()

    result = RenameExecutor(store).execute(make_items(folder, [("a.txt", "x")]))

    assert result.failed == 1
    assert "文件夹" in result.errors[0].error


def test_source_duplicate_is_rejected(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])

    result = RenameExecutor(store).execute(
        make_items(folder, [("a.txt", "b.txt"), ("a.txt", "c.txt")])
    )

    assert result.failed == 1
    assert "源文件重复" in result.errors[0].error
    assert names(folder) == ["b.txt"]


def test_phase_two_failure_rolls_back(
    store: BackupStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])

    real_rename = os.rename

    def fake_rename(source, target):
        if Path(target).name == "boom.txt":
            raise PermissionError("locked")
        return real_rename(source, target)

    monkeypatch.setattr("app.engine.executor.os.rename", fake_rename)

    result = RenameExecutor(store, retry_delay=0).execute(
        make_items(folder, [("a.txt", "boom.txt")])
    )

    assert result.failed == 1
    assert "改名失败" in result.errors[0].error
    assert names(folder) == ["a.txt"]
    assert (folder / "a.txt").read_text(encoding="utf-8") == "content:a.txt"


def test_retry_then_success(
    store: BackupStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    calls = {"count": 0}
    real_rename = os.rename

    def flaky_rename(source, target):
        if Path(target).name == "slow.txt":
            calls["count"] += 1
            if calls["count"] < 3:
                raise PermissionError("busy")
        return real_rename(source, target)

    monkeypatch.setattr("app.engine.executor.os.rename", flaky_rename)

    result = RenameExecutor(store, retries=3, retry_delay=0).execute(
        make_items(folder, [("a.txt", "slow.txt")])
    )

    assert result.success == 1
    assert calls["count"] == 3
    assert names(folder) == ["slow.txt"]


def test_backup_failure_aborts_before_rename(
    store: BackupStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])

    def fail_create(*args, **kwargs):
        raise BackupError("disk full")

    monkeypatch.setattr(store, "create", fail_create)

    with pytest.raises(BackupError):
        RenameExecutor(store).execute(make_items(folder, [("a.txt", "b.txt")]))

    assert names(folder) == ["a.txt"]


def test_progress_callback(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt"])
    events: list[tuple[int, int, str]] = []

    RenameExecutor(store, progress=lambda done, total, msg: events.append((done, total, msg))).execute(
        make_items(folder, [("a.txt", "x.txt"), ("b.txt", "y.txt")])
    )

    assert events[-1][0] == 4
    assert events[-1][1] == 4


def test_backup_is_written_before_first_rename(
    store: BackupStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    observed: dict[str, str] = {}
    real_rename = os.rename

    def spy_rename(source, target):
        if not observed:
            record = store.list_records()[0]
            observed["state"] = record.state
            observed["temp"] = record.items[0].temp
        return real_rename(source, target)

    monkeypatch.setattr("app.engine.executor.os.rename", spy_rename)

    RenameExecutor(store).execute(make_items(folder, [("a.txt", "b.txt")]))

    assert observed["state"] == STATE_RENAMING
    assert observed["temp"].endswith(".tmp")


def test_rules_snapshot_is_saved(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    rules = RuleSet(overall=OverallRule(template="A_#"))

    result = RenameExecutor(store).execute(
        make_items(folder, [("a.txt", "A_1.txt")]), rules=rules
    )

    record = store.load(result.backup_path)
    assert record.rules["overall"]["template"] == "A_#"


def test_chinese_and_emoji_names(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["中文 😀.txt"])

    result = RenameExecutor(store).execute(
        make_items(folder, [("中文 😀.txt", "新 名字😀.txt")])
    )

    assert result.success == 1
    assert names(folder) == ["新 名字😀.txt"]


def test_batch_of_55_reference_files(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    sources = [f"{index:02d}.1080P.WEB-DL.mp4" for index in range(1, 56)]
    write_files(folder, sources)
    rules = RuleSet(
        overall=OverallRule(
            template="视频_#",
            start=1,
            digits=3,
            pad=True,
            change_extension=True,
            new_extension="mp4",
        )
    )
    plans = plan_batch(sources, rules, taken_names=set(sources))
    items = [RenameItem(folder / plan.source, folder / plan.target) for plan in plans]

    result = RenameExecutor(store).execute(items, rules=rules)

    assert result.success == 55
    assert result.failed == 0
    assert (folder / "视频_001.mp4").exists()
    assert (folder / "视频_055.mp4").exists()
    assert len(names(folder)) == 55
    assert not list(folder.glob("*.tmp"))


def test_cancel_before_start_leaves_files_untouched(
    store: BackupStore, tmp_path: Path
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt"])

    result = RenameExecutor(store, should_cancel=lambda: True).execute(
        make_items(folder, [("a.txt", "x.txt"), ("b.txt", "y.txt")])
    )

    assert result.success == 0
    assert result.failed == 0
    assert result.skipped == 2
    assert names(folder) == ["a.txt", "b.txt"]
    record = store.load(result.backup_path)
    assert record.state == STATE_COMPLETED
    assert all(item.status == STATUS_SKIPPED for item in record.items)


def test_cancel_midway_finishes_moved_files_and_skips_rest(
    store: BackupStore, tmp_path: Path
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt", "c.txt", "d.txt"])
    state = {"done": 0}

    def progress(done: int, _total: int, _message: str) -> None:
        state["done"] = done

    def should_cancel() -> bool:
        return state["done"] >= 2

    result = RenameExecutor(
        store, progress=progress, should_cancel=should_cancel
    ).execute(
        make_items(
            folder,
            [
                ("a.txt", "A.txt"),
                ("b.txt", "B.txt"),
                ("c.txt", "C.txt"),
                ("d.txt", "D.txt"),
            ],
        )
    )

    assert result.success == 2
    assert result.failed == 0
    assert result.skipped == 2
    assert names(folder) == ["A.txt", "B.txt", "c.txt", "d.txt"]
    assert not list(folder.glob("*.tmp"))
