"""备份记录与 JSON 存储。

每次改名/还原都会先落盘一份备份，状态机：
    preparing -> renaming -> completed / completed_with_errors / incomplete
还原成功后原批次标记为 rolled_back。
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from app import __version__
from app.paths import backup_dir

SCHEMA_VERSION = 1

STATE_PREPARING = "preparing"
STATE_RENAMING = "renaming"
STATE_COMPLETED = "completed"
STATE_COMPLETED_WITH_ERRORS = "completed_with_errors"
STATE_INCOMPLETE = "incomplete"
STATE_ROLLED_BACK = "rolled_back"

FINAL_STATES = frozenset(
    {STATE_COMPLETED, STATE_COMPLETED_WITH_ERRORS, STATE_ROLLED_BACK}
)
UNFINISHED_STATES = frozenset({STATE_PREPARING, STATE_RENAMING, STATE_INCOMPLETE})

KIND_RENAME = "rename"
KIND_UNDO = "undo"
KIND_RESTORE = "restore"

STATUS_PENDING = "pending"
STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_ROLLED_BACK = "rolled_back"


class BackupError(RuntimeError):
    """备份无法创建或写入。"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _new_batch_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


@dataclass
class BackupItem:
    old: str
    new: str
    status: str = STATUS_PENDING
    error: str = ""
    size: int = 0
    mtime: str = ""
    temp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "old": self.old,
            "new": self.new,
            "status": self.status,
            "error": self.error,
            "size": self.size,
            "mtime": self.mtime,
            "temp": self.temp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupItem":
        return cls(
            old=str(data.get("old", "")),
            new=str(data.get("new", "")),
            status=str(data.get("status", STATUS_PENDING)),
            error=str(data.get("error", "")),
            size=int(data.get("size", 0) or 0),
            mtime=str(data.get("mtime", "")),
            temp=str(data.get("temp", "")),
        )


@dataclass
class BackupRecord:
    batch_id: str
    created_at: str
    kind: str = KIND_RENAME
    state: str = STATE_PREPARING
    app_version: str = __version__
    rules: dict[str, Any] = field(default_factory=dict)
    items: list[BackupItem] = field(default_factory=list)
    finished_at: str = ""
    note: str = ""
    path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "kind": self.kind,
            "state": self.state,
            "app_version": self.app_version,
            "note": self.note,
            "rules": self.rules,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupRecord":
        items = [
            BackupItem.from_dict(item)
            for item in data.get("items", [])
            if isinstance(item, dict)
        ]
        return cls(
            batch_id=str(data.get("batch_id", "")),
            created_at=str(data.get("created_at", "")),
            kind=str(data.get("kind", KIND_RENAME)),
            state=str(data.get("state", STATE_PREPARING)),
            app_version=str(data.get("app_version", "")),
            rules=data.get("rules", {}) if isinstance(data.get("rules"), dict) else {},
            items=items,
            finished_at=str(data.get("finished_at", "")),
            note=str(data.get("note", "")),
        )

    @property
    def counts(self) -> dict[str, int]:
        result = {STATUS_OK: 0, STATUS_FAILED: 0, STATUS_SKIPPED: 0, STATUS_PENDING: 0}
        for item in self.items:
            result[item.status] = result.get(item.status, 0) + 1
        return result

    @property
    def finished(self) -> bool:
        return self.state in FINAL_STATES


class BackupStore:
    """备份目录的读写。root 可注入，便于测试。"""

    def __init__(self, root: Path | None = None, keep: int = 100) -> None:
        try:
            self.root = Path(root) if root is not None else backup_dir()
        except OSError as exc:
            raise BackupError(f"无法创建备份目录：{exc}") from exc
        self.keep = keep
        self.errors: list[str] = []
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BackupError(f"无法创建备份目录 {self.root}：{exc}") from exc

    # ---------- 创建 / 保存 ----------
    def create(
        self,
        items: Iterable[BackupItem],
        rules: dict[str, Any] | None = None,
        kind: str = KIND_RENAME,
    ) -> BackupRecord:
        record = BackupRecord(
            batch_id=_new_batch_id(),
            created_at=now_iso(),
            kind=kind,
            state=STATE_PREPARING,
            rules=rules or {},
            items=list(items),
        )
        record.path = self._unique_path(record.batch_id)
        self.save(record)
        return record

    def save(self, record: BackupRecord) -> Path:
        if record.path is None:
            record.path = self._unique_path(record.batch_id)
        try:
            self._atomic_write_json(record.path, record.to_dict())
        except OSError as exc:
            raise BackupError(f"写入备份失败：{exc}") from exc
        return record.path

    def _unique_path(self, batch_id: str) -> Path:
        path = self.root / f"{batch_id}.json"
        counter = 1
        while path.exists():
            path = self.root / f"{batch_id}-{counter}.json"
            counter += 1
        return path

    @staticmethod
    def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
        temp = path.with_name(path.name + ".tmp")
        try:
            with open(temp, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            if temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass

    # ---------- 读取 ----------
    def load(self, path: Path | str) -> BackupRecord:
        file_path = Path(path)
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise BackupError(f"读取备份失败 {file_path}：{exc}") from exc
        record = BackupRecord.from_dict(data)
        record.path = file_path
        return record

    def list_records(self) -> list[BackupRecord]:
        self.errors = []
        records: list[BackupRecord] = []
        for path in self.root.glob("*.json"):
            if path.name.endswith(".tmp"):
                continue
            try:
                records.append(self.load(path))
            except BackupError as exc:
                self.errors.append(str(exc))
        records.sort(key=lambda record: (record.created_at, record.batch_id), reverse=True)
        return records

    def find(self, batch_id: str) -> BackupRecord | None:
        for record in self.list_records():
            if record.batch_id == batch_id:
                return record
        return None

    def latest(
        self,
        kind: str | None = None,
        states: set[str] | frozenset[str] | None = None,
    ) -> BackupRecord | None:
        for record in self.list_records():
            if kind is not None and record.kind != kind:
                continue
            if states is not None and record.state not in states:
                continue
            return record
        return None

    def unfinished(self) -> list[BackupRecord]:
        return [
            record
            for record in self.list_records()
            if record.state in UNFINISHED_STATES
        ]

    # ---------- 清理 ----------
    def cleanup(self) -> int:
        records = self.list_records()
        if len(records) <= self.keep:
            return 0
        removed = 0
        for record in records[self.keep :]:
            if record.state not in FINAL_STATES:
                continue
            if record.path and record.path.exists():
                try:
                    record.path.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed
