"""撤销、一键还原与崩溃恢复测试。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.engine.backup import (
    BackupItem,
    BackupStore,
    STATE_COMPLETED,
    STATE_COMPLETED_WITH_ERRORS,
    STATE_INCOMPLETE,
    STATE_PREPARING,
    STATE_RENAMING,
    STATE_ROLLED_BACK,
    STATUS_OK,
    STATUS_PENDING,
)
from app.engine.executor import RenameExecutor, RenameItem
from app.engine.undo import (
    CONFLICT_RENAME,
    UndoError,
    latest_restorable,
    recover_incomplete,
    restore_batch,
    undo_last,
)


@pytest.fixture
def store(tmp_path: Path) -> BackupStore:
    return BackupStore(tmp_path / "backups")


def write_files(directory: Path, names: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_text(f"content:{name}", encoding="utf-8")


def make_items(directory: Path, pairs: list[tuple[str, str]]) -> list[RenameItem]:
    return [RenameItem(directory / old, directory / new) for old, new in pairs]


def make_record(
    store: BackupStore,
    old: Path,
    new: Path,
    temp: Path | None = None,
    state: str = STATE_RENAMING,
    status: str = STATUS_PENDING,
):
    record = store.create(
        [BackupItem(old=str(old), new=str(new), temp=str(temp) if temp else "")]
    )
    record.state = state
    record.items[0].status = status
    store.save(record)
    return record


def test_undo_last_restores_everything(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt", "c.txt"])
    RenameExecutor(store).execute(
        make_items(folder, [("a.txt", "x.txt"), ("b.txt", "y.txt"), ("c.txt", "z.txt")])
    )

    outcome = undo_last(store)

    assert outcome.result.success == 3
    assert outcome.fully_restored is True
    assert sorted(path.name for path in folder.iterdir()) == ["a.txt", "b.txt", "c.txt"]
    assert outcome.original.state == STATE_ROLLED_BACK
    assert store.latest(kind="restore") is not None


def test_undo_without_history_raises(store: BackupStore) -> None:
    with pytest.raises(UndoError, match="没有可撤销"):
        undo_last(store)


def test_undo_twice_raises(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    RenameExecutor(store).execute(make_items(folder, [("a.txt", "b.txt")]))

    undo_last(store)

    with pytest.raises(UndoError):
        undo_last(store)
    assert latest_restorable(store) is None


def test_restore_conflict_is_skipped_by_default(
    store: BackupStore, tmp_path: Path
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt"])
    RenameExecutor(store).execute(
        make_items(folder, [("a.txt", "x.txt"), ("b.txt", "y.txt")])
    )
    (folder / "a.txt").write_text("new file", encoding="utf-8")

    outcome = undo_last(store)

    assert outcome.fully_restored is False
    assert len(outcome.plan.skipped) == 1
    assert outcome.result.success == 1
    assert (folder / "a.txt").read_text(encoding="utf-8") == "new file"
    assert (folder / "b.txt").exists()
    assert outcome.original.state != STATE_ROLLED_BACK


def test_restore_conflict_can_rename(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    RenameExecutor(store).execute(make_items(folder, [("a.txt", "b.txt")]))
    (folder / "a.txt").write_text("new file", encoding="utf-8")

    record = latest_restorable(store)
    outcome = restore_batch(store, record.batch_id, conflict=CONFLICT_RENAME)

    assert outcome.fully_restored is True
    assert (folder / "a.txt").read_text(encoding="utf-8") == "new file"
    assert (folder / "a (1).txt").read_text(encoding="utf-8") == "content:a.txt"


def test_restore_missing_file_raises(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    RenameExecutor(store).execute(make_items(folder, [("a.txt", "b.txt")]))
    (folder / "b.txt").unlink()

    with pytest.raises(UndoError):
        undo_last(store)


def test_partial_missing_files_restore_the_rest(
    store: BackupStore, tmp_path: Path
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt"])
    RenameExecutor(store).execute(
        make_items(folder, [("a.txt", "x.txt"), ("b.txt", "y.txt")])
    )
    (folder / "y.txt").unlink()

    outcome = undo_last(store)

    assert outcome.result.success == 1
    assert outcome.plan.missing
    assert (folder / "a.txt").exists()
    assert not (folder / "b.txt").exists()


def test_restore_unknown_batch_raises(store: BackupStore) -> None:
    with pytest.raises(UndoError, match="找不到"):
        restore_batch(store, "does-not-exist")


def test_restore_already_rolled_back_raises(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    RenameExecutor(store).execute(make_items(folder, [("a.txt", "b.txt")]))
    record = latest_restorable(store)
    undo_last(store)

    with pytest.raises(UndoError, match="已经还原"):
        restore_batch(store, record.batch_id)


def test_failed_items_are_not_restored(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt", "b.txt", "c.txt"])
    RenameExecutor(store).execute(
        make_items(folder, [("a.txt", "b.txt"), ("c.txt", "d.txt")])
    )
    assert store.latest(kind="rename").state == STATE_COMPLETED_WITH_ERRORS

    outcome = undo_last(store)

    assert outcome.result.success == 1
    assert (folder / "c.txt").exists()
    assert (folder / "b.txt").read_text(encoding="utf-8") == "content:b.txt"


# ---------------------------------------------------------------------------
# 崩溃恢复
# ---------------------------------------------------------------------------
def test_recover_after_phase_one(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    temp = folder / ".~br_test-0.tmp"
    record = make_record(store, folder / "a.txt", folder / "b.txt", temp=temp)
    (folder / "a.txt").rename(temp)

    outcomes = recover_incomplete(store)

    assert outcomes[0].restored == 1
    assert (folder / "a.txt").read_text(encoding="utf-8") == "content:a.txt"
    assert not temp.exists()
    assert outcomes[0].record.state == STATE_ROLLED_BACK


def test_recover_after_phase_two(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["b.txt"])
    record = make_record(store, folder / "a.txt", folder / "b.txt", state=STATE_RENAMING)
    record.items[0].status = STATUS_OK
    store.save(record)

    outcomes = recover_incomplete(store)

    assert outcomes[0].restored == 1
    assert (folder / "a.txt").exists()
    assert not (folder / "b.txt").exists()
    assert outcomes[0].record.state == STATE_ROLLED_BACK


def test_recover_untouched_batch(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    record = make_record(
        store, folder / "a.txt", folder / "b.txt", state=STATE_PREPARING
    )

    outcomes = recover_incomplete(store)

    assert (folder / "a.txt").exists()
    assert outcomes[0].record.state == STATE_ROLLED_BACK
    assert outcomes[0].record.batch_id == record.batch_id


def test_recover_missing_file_reports_error(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    folder.mkdir()
    record = make_record(store, folder / "a.txt", folder / "b.txt")

    outcomes = recover_incomplete(store)

    assert outcomes[0].errors
    assert outcomes[0].record.state == STATE_INCOMPLETE


def test_recover_keeps_temp_when_original_is_occupied(
    store: BackupStore, tmp_path: Path
) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    temp = folder / ".~br_test-0.tmp"
    temp.write_text("moved", encoding="utf-8")
    record = make_record(store, folder / "a.txt", folder / "b.txt", temp=temp)

    outcomes = recover_incomplete(store)

    assert outcomes[0].errors
    assert temp.exists()
    assert outcomes[0].record.state == STATE_INCOMPLETE


def test_recover_restores_case_only_rename(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["A.txt"])
    record = make_record(
        store, folder / "a.txt", folder / "A.txt", state=STATE_RENAMING
    )
    record.items[0].status = STATUS_OK
    store.save(record)

    recover_incomplete(store)

    assert [path.name for path in folder.iterdir()] == ["a.txt"]


def test_recover_skips_completed_batches(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    record = make_record(
        store, folder / "a.txt", folder / "b.txt", state=STATE_COMPLETED
    )

    outcomes = recover_incomplete(store)

    assert outcomes == []
    assert store.load(record.path).state == STATE_COMPLETED


def test_recover_partial_phase_two(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    folder.mkdir()
    (folder / "x.txt").write_text("A", encoding="utf-8")
    temp = folder / ".~br_test-1.tmp"
    temp.write_text("B", encoding="utf-8")

    record = store.create(
        [
            BackupItem(old=str(folder / "a.txt"), new=str(folder / "x.txt"), status=STATUS_OK),
            BackupItem(
                old=str(folder / "b.txt"), new=str(folder / "y.txt"), temp=str(temp)
            ),
        ]
    )
    record.state = STATE_RENAMING
    store.save(record)

    outcomes = recover_incomplete(store)

    assert (folder / "a.txt").read_text(encoding="utf-8") == "A"
    assert (folder / "b.txt").read_text(encoding="utf-8") == "B"
    assert outcomes[0].record.state == STATE_ROLLED_BACK


def test_undo_case_only_rename(store: BackupStore, tmp_path: Path) -> None:
    folder = tmp_path / "files"
    write_files(folder, ["a.txt"])
    RenameExecutor(store).execute(make_items(folder, [("a.txt", "A.txt")]))

    outcome = undo_last(store)

    assert outcome.fully_restored is True
    assert [path.name for path in folder.iterdir()] == ["a.txt"]


@pytest.mark.parametrize("crash_after", [3, 7])
def test_process_crash_is_recoverable(tmp_path: Path, crash_after: int) -> None:
    """子进程在第 N 次改名后 os._exit，父进程用备份恢复。"""
    folder = tmp_path / "files"
    backups = tmp_path / "backups"
    script = Path(__file__).resolve().parent.parent / "build" / "crash_sim.py"

    env = {
        **os.environ,
        "BFR_FOLDER": str(folder),
        "BFR_BACKUP": str(backups),
        "BFR_CRASH_AFTER": str(crash_after),
        "PYTHONPATH": str(script.parent.parent),
    }
    process = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        cwd=script.parent.parent,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert process.returncode == 9, process.stderr

    store = BackupStore(backups)
    outcomes = recover_incomplete(store)

    assert outcomes
    assert outcomes[0].record.state == STATE_ROLLED_BACK
    assert sorted(path.name for path in folder.iterdir()) == [
        "1.txt",
        "2.txt",
        "3.txt",
        "4.txt",
        "5.txt",
    ]
    for name in ("1.txt", "2.txt", "3.txt", "4.txt", "5.txt"):
        assert (folder / name).read_text(encoding="utf-8") == f"content:{name}"
    assert not list(folder.glob("*.tmp"))
