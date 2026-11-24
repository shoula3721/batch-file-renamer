"""备份存储测试。"""
from __future__ import annotations

import json

import pytest

from app.engine.backup import (
    BackupError,
    BackupItem,
    BackupRecord,
    BackupStore,
    STATE_COMPLETED,
    STATE_PREPARING,
    STATE_RENAMING,
    STATE_ROLLED_BACK,
    STATUS_OK,
    STATUS_SKIPPED,
)


def test_create_writes_readable_json(tmp_path) -> None:
    store = BackupStore(tmp_path / "backups")
    record = store.create(
        [BackupItem(old=r"C:\a\1.txt", new=r"C:\a\2.txt", size=12)],
        rules={"overall": {"template": "x"}},
    )
    assert record.path is not None and record.path.exists()

    data = json.loads(record.path.read_text(encoding="utf-8"))
    assert data["schema"] == 1
    assert data["state"] == STATE_PREPARING
    assert data["items"][0]["old"] == r"C:\a\1.txt"
    assert data["rules"]["overall"]["template"] == "x"


def test_save_roundtrip(tmp_path) -> None:
    store = BackupStore(tmp_path)
    record = store.create([BackupItem(old="a", new="b")])
    record.state = STATE_COMPLETED
    record.items[0].status = STATUS_OK
    store.save(record)

    loaded = store.load(record.path)
    assert loaded.state == STATE_COMPLETED
    assert loaded.items[0].status == STATUS_OK
    assert loaded.batch_id == record.batch_id


def test_atomic_write_leaves_no_temp_file(tmp_path) -> None:
    store = BackupStore(tmp_path)
    record = store.create([BackupItem(old="a", new="b")])
    store.save(record)
    assert not list(tmp_path.glob("*.tmp"))


def test_batch_ids_are_unique(tmp_path) -> None:
    store = BackupStore(tmp_path)
    first = store.create([BackupItem(old="a", new="b")])
    second = store.create([BackupItem(old="c", new="d")])
    assert first.batch_id != second.batch_id
    assert first.path != second.path


def test_list_records_newest_first(tmp_path) -> None:
    store = BackupStore(tmp_path)
    first = store.create([BackupItem(old="a", new="b")])
    first.created_at = "2026-01-01T00:00:00+08:00"
    store.save(first)
    second = store.create([BackupItem(old="c", new="d")])
    second.created_at = "2026-02-01T00:00:00+08:00"
    store.save(second)

    records = store.list_records()
    assert [record.batch_id for record in records] == [second.batch_id, first.batch_id]


def test_latest_filters_by_kind_and_state(tmp_path) -> None:
    store = BackupStore(tmp_path)
    rename = store.create([BackupItem(old="a", new="b")], kind="rename")
    rename.state = STATE_COMPLETED
    store.save(rename)
    undo = store.create([BackupItem(old="b", new="a")], kind="undo")
    undo.state = STATE_COMPLETED
    store.save(undo)

    assert store.latest(kind="rename").batch_id == rename.batch_id
    assert store.latest(kind="undo").batch_id == undo.batch_id


def test_unfinished_records(tmp_path) -> None:
    store = BackupStore(tmp_path)
    preparing = store.create([BackupItem(old="a", new="b")])
    renaming = store.create([BackupItem(old="c", new="d")])
    renaming.state = STATE_RENAMING
    store.save(renaming)
    finished = store.create([BackupItem(old="e", new="f")])
    finished.state = STATE_COMPLETED
    store.save(finished)

    ids = {record.batch_id for record in store.unfinished()}
    assert ids == {preparing.batch_id, renaming.batch_id}


def test_cleanup_keeps_newest_and_preserves_unfinished(tmp_path) -> None:
    store = BackupStore(tmp_path, keep=2)
    records = []
    for index in range(4):
        record = store.create([BackupItem(old=f"a{index}", new=f"b{index}")])
        record.created_at = f"2026-01-0{index + 1}T00:00:00+08:00"
        record.state = STATE_COMPLETED
        store.save(record)
        records.append(record)

    # 最旧的一条改成未完成，应保留
    records[0].state = STATE_RENAMING
    store.save(records[0])

    removed = store.cleanup()
    remaining = {record.batch_id for record in store.list_records()}
    assert removed == 1
    assert records[0].batch_id in remaining
    assert records[3].batch_id in remaining
    assert records[1].batch_id not in remaining


def test_corrupt_file_is_skipped(tmp_path) -> None:
    store = BackupStore(tmp_path)
    store.create([BackupItem(old="a", new="b")])
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    records = store.list_records()
    assert len(records) == 1
    assert store.errors and "broken.json" in store.errors[0]


def test_unknown_fields_are_tolerated() -> None:
    record = BackupRecord.from_dict(
        {
            "batch_id": "x",
            "created_at": "2026-01-01",
            "state": "weird",
            "items": [{"old": "a", "new": "b", "status": "ok", "extra": 1}],
            "unknown": True,
        }
    )
    assert record.batch_id == "x"
    assert record.items[0].status == STATUS_OK


def test_counts() -> None:
    record = BackupRecord(
        batch_id="x",
        created_at="2026-01-01",
        items=[
            BackupItem(old="a", new="b", status=STATUS_OK),
            BackupItem(old="c", new="d", status=STATUS_SKIPPED),
            BackupItem(old="e", new="f", status=STATUS_SKIPPED),
        ],
    )
    counts = record.counts
    assert counts[STATUS_OK] == 1
    assert counts[STATUS_SKIPPED] == 2


def test_missing_backup_file_raises(tmp_path) -> None:
    store = BackupStore(tmp_path)
    with pytest.raises(BackupError):
        store.load(tmp_path / "nope.json")


def test_rolled_back_state_is_final(tmp_path) -> None:
    record = BackupRecord(batch_id="x", created_at="2026-01-01", state=STATE_ROLLED_BACK)
    assert record.finished is True


def test_root_path_that_is_a_file_raises_backup_error(tmp_path) -> None:
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")

    with pytest.raises(BackupError):
        BackupStore(blocker)
