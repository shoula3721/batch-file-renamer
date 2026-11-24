"""两阶段重命名执行器。

阶段一：所有源文件改到同目录的临时名（.~br_<批次>-<序号>.tmp）
阶段二：临时名再改到目标名

任何阶段都使用 os.rename（目标存在即报错），绝不覆盖；单条失败立即回滚。
"""
from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from .backup import (
    BackupError,
    BackupItem,
    BackupRecord,
    BackupStore,
    KIND_RENAME,
    STATE_COMPLETED,
    STATE_COMPLETED_WITH_ERRORS,
    STATE_INCOMPLETE,
    STATE_RENAMING,
    STATUS_FAILED,
    STATUS_OK,
    STATUS_SKIPPED,
    now_iso,
)
from .rules import RuleSet
from .validate import prepare_fs_path, validate_filename

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class RenameItem:
    source: Path
    target: Path


@dataclass
class ItemResult:
    source: Path
    target: Path
    status: str
    error: str = ""


@dataclass
class BatchResult:
    batch_id: str
    backup_path: Path | None
    state: str
    items: list[ItemResult] = field(default_factory=list)
    note: str = ""

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def success(self) -> int:
        return sum(1 for item in self.items if item.status == STATUS_OK)

    @property
    def failed(self) -> int:
        return sum(1 for item in self.items if item.status == STATUS_FAILED)

    @property
    def skipped(self) -> int:
        return sum(1 for item in self.items if item.status == STATUS_SKIPPED)

    @property
    def errors(self) -> list[ItemResult]:
        return [item for item in self.items if item.status == STATUS_FAILED]


# ---------------------------------------------------------------------------
# 路径与改名原语（undo / recovery 复用）
# ---------------------------------------------------------------------------
def absolute_path(path: Path | str) -> Path:
    return Path(os.path.abspath(str(path)))


def norm_path(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def same_file(first: Path | str, second: Path | str) -> bool:
    return norm_path(first) == norm_path(second)


def path_exists(path: Path | str) -> bool:
    return os.path.exists(prepare_fs_path(path))


def path_is_dir(path: Path | str) -> bool:
    return os.path.isdir(prepare_fs_path(path))


def rename_with_retry(
    source: Path | str,
    target: Path | str,
    retries: int = 3,
    retry_delay: float = 0.05,
) -> None:
    last_error: OSError | None = None
    for attempt in range(max(1, retries)):
        try:
            os.rename(prepare_fs_path(source), prepare_fs_path(target))
            return
        except OSError as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(max(0.0, retry_delay))
    assert last_error is not None
    raise last_error


def _same_volume(first: Path | str, second: Path | str) -> bool:
    try:
        return os.stat(prepare_fs_path(first)).st_dev == os.stat(
            prepare_fs_path(second)
        ).st_dev
    except OSError:
        return True


class RenameExecutor:
    def __init__(
        self,
        store: BackupStore,
        retries: int = 3,
        retry_delay: float = 0.05,
        progress: ProgressCallback | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        self.store = store
        self.retries = max(1, retries)
        self.retry_delay = max(0.0, retry_delay)
        self.progress = progress
        self.should_cancel = should_cancel

    # ------------------------------------------------------------------
    def execute(
        self,
        items: Sequence[RenameItem],
        rules: RuleSet | None = None,
        kind: str = KIND_RENAME,
    ) -> BatchResult:
        work = [
            RenameItem(absolute_path(item.source), absolute_path(item.target))
            for item in items
        ]

        backup_items = [
            BackupItem(
                old=str(item.source),
                new=str(item.target),
                size=self._file_size(item.source),
                mtime=self._file_mtime(item.source),
            )
            for item in work
        ]

        # 关键：备份先落盘，失败则一个文件都不动
        record = self.store.create(
            backup_items,
            rules=rules.to_dict() if rules is not None else {},
            kind=kind,
        )

        try:
            self._run(work, record)
        except Exception as exc:  # noqa: BLE001 - 需要把任何异常写进备份
            record.state = STATE_INCOMPLETE
            record.note = f"执行中断：{exc}"
            record.finished_at = now_iso()
            try:
                self.store.save(record)
            except BackupError:
                pass
            raise

        result = self._result_from_record(record)
        try:
            self.store.save(record)
        except BackupError as exc:
            result.note = f"备份最终状态写入失败：{exc}"
        try:
            self.store.cleanup()
        except BackupError:
            pass
        return result

    # ------------------------------------------------------------------
    def _run(self, work: list[RenameItem], record: BackupRecord) -> None:
        batch_sources = {norm_path(item.source) for item in work}
        seen_sources: set[str] = set()
        seen_targets: dict[str, list[int]] = {}
        movable: list[int] = []

        for index, (item, backup) in enumerate(zip(work, record.items)):
            source, target = item.source, item.target

            # 注意：WindowsPath 比较会忽略大小写，这里必须按字符串精确比较
            if str(source) == str(target):
                backup.status = STATUS_SKIPPED
                backup.error = "名称未变化"
                continue

            if not path_exists(source):
                backup.status = STATUS_FAILED
                backup.error = "源文件不存在"
                continue

            if path_is_dir(source):
                backup.status = STATUS_FAILED
                backup.error = "暂不支持重命名文件夹"
                continue

            source_key = norm_path(source)
            if source_key in seen_sources:
                backup.status = STATUS_FAILED
                backup.error = "源文件重复"
                continue
            seen_sources.add(source_key)

            errors = validate_filename(target.name)
            if errors:
                backup.status = STATUS_FAILED
                backup.error = "；".join(errors)
                continue

            if not path_exists(target.parent):
                backup.status = STATUS_FAILED
                backup.error = "目标目录不存在"
                continue

            if not _same_volume(source, target.parent):
                backup.status = STATUS_FAILED
                backup.error = "目标目录与源文件不在同一磁盘，无法安全移动"
                continue

            if path_exists(target):
                if path_is_dir(target):
                    backup.status = STATUS_FAILED
                    backup.error = "目标位置存在同名文件夹"
                    continue
                if not same_file(source, target) and norm_path(target) not in batch_sources:
                    backup.status = STATUS_FAILED
                    backup.error = "目标名称已存在"
                    continue

            backup.temp = str(self._temp_path(source, record.batch_id, index))
            movable.append(index)
            seen_targets.setdefault(norm_path(target), []).append(index)

        for indices in seen_targets.values():
            if len(indices) > 1:
                for index in indices:
                    record.items[index].status = STATUS_FAILED
                    record.items[index].error = "目标名称重复"
                movable = [index for index in movable if index not in indices]

        # 临时名先写进备份，再开始改任何文件，保证崩溃后可恢复
        record.state = STATE_RENAMING
        self.store.save(record)

        total = len(movable) * 2
        done = 0

        # ---------------- 阶段一：源文件 -> 临时名 ----------------
        moved: list[int] = []
        for index in movable:
            item = work[index]
            backup = record.items[index]
            if self._cancelled():
                backup.status = STATUS_SKIPPED
                backup.error = "已取消"
                continue
            temp = Path(backup.temp)
            try:
                rename_with_retry(
                    item.source, temp, self.retries, self.retry_delay
                )
                moved.append(index)
            except OSError as exc:
                backup.status = STATUS_FAILED
                backup.error = f"无法移动到临时名称：{exc}"
                backup.temp = ""
            done += 1
            self._notify(done, total, "正在准备临时名称")

        # ---------------- 阶段二：临时名 -> 目标名 ----------------
        for index in moved:
            item = work[index]
            backup = record.items[index]
            temp = Path(backup.temp)

            if path_exists(item.target) and not same_file(item.source, item.target):
                restored, rollback_error = self._rollback(temp, item.source)
                backup.status = STATUS_FAILED
                backup.error = "目标名称已存在"
                if not restored:
                    backup.error += f"；{rollback_error}"
                else:
                    backup.temp = ""
                done += 1
                self._notify(done, total, "目标冲突，已回滚")
                continue

            try:
                rename_with_retry(
                    temp, item.target, self.retries, self.retry_delay
                )
                backup.status = STATUS_OK
                backup.error = ""
                backup.temp = ""
            except OSError as exc:
                restored, rollback_error = self._rollback(temp, item.source)
                backup.status = STATUS_FAILED
                backup.error = f"改名失败：{exc}"
                if not restored:
                    backup.error += f"；{rollback_error}"
                else:
                    backup.temp = ""
            done += 1
            self._notify(done, total, "正在写入目标名称")

        counts = record.counts
        record.state = (
            STATE_COMPLETED
            if counts.get(STATUS_FAILED, 0) == 0
            else STATE_COMPLETED_WITH_ERRORS
        )
        record.finished_at = now_iso()

    # ------------------------------------------------------------------
    def _temp_path(self, source: Path, batch_id: str, index: int) -> Path:
        candidate = source.with_name(f".~br_{batch_id}-{index}.tmp")
        while path_exists(candidate):
            candidate = source.with_name(
                f".~br_{batch_id}-{index}-{secrets.token_hex(2)}.tmp"
            )
        return candidate

    def _rollback(self, temp: Path, source: Path) -> tuple[bool, str]:
        try:
            rename_with_retry(temp, source, self.retries, self.retry_delay)
            return True, ""
        except OSError as exc:
            return False, f"回滚失败，文件仍暂存于 {temp}：{exc}"

    def _notify(self, done: int, total: int, message: str) -> None:
        if self.progress is None:
            return
        try:
            self.progress(done, total, message)
        except Exception:  # noqa: BLE001 - 进度回调不能影响改名
            pass

    def _cancelled(self) -> bool:
        if self.should_cancel is None:
            return False
        try:
            return bool(self.should_cancel())
        except Exception:  # noqa: BLE001 - 取消判断失败时继续执行
            return False

    @staticmethod
    def _file_size(path: Path) -> int:
        try:
            return os.path.getsize(prepare_fs_path(path))
        except OSError:
            return 0

    @staticmethod
    def _file_mtime(path: Path) -> str:
        try:
            timestamp = os.path.getmtime(prepare_fs_path(path))
        except OSError:
            return ""
        return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _result_from_record(record: BackupRecord) -> BatchResult:
        items = [
            ItemResult(
                source=Path(item.old),
                target=Path(item.new),
                status=item.status,
                error=item.error,
            )
            for item in record.items
        ]
        return BatchResult(
            batch_id=record.batch_id,
            backup_path=record.path,
            state=record.state,
            items=items,
        )
