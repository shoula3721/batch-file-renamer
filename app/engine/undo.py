"""撤销、一键还原与崩溃恢复。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .backup import (
    BackupRecord,
    BackupStore,
    KIND_RENAME,
    KIND_RESTORE,
    STATE_COMPLETED,
    STATE_COMPLETED_WITH_ERRORS,
    STATE_INCOMPLETE,
    STATE_ROLLED_BACK,
    STATUS_FAILED,
    STATUS_OK,
    STATUS_ROLLED_BACK,
    now_iso,
)
from .executor import (
    BatchResult,
    RenameExecutor,
    RenameItem,
    norm_path,
    path_exists,
    rename_with_retry,
    same_file,
)
from .validate import allocate_unique, join_name, split_name

CONFLICT_SKIP = "skip"
CONFLICT_RENAME = "rename"


class UndoError(RuntimeError):
    """没有可还原的记录，或记录状态不允许还原。"""


@dataclass
class RestorePlan:
    items: list[RenameItem] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    ok_items: int = 0


@dataclass
class RestoreOutcome:
    original: BackupRecord
    result: BatchResult
    plan: RestorePlan
    fully_restored: bool


@dataclass
class RecoveryOutcome:
    record: BackupRecord
    restored: int
    errors: list[str] = field(default_factory=list)


def _dir_names(directory: Path) -> set[str]:
    try:
        return {entry.name.casefold() for entry in directory.iterdir()}
    except OSError:
        return set()


def build_reverse_plan(
    record: BackupRecord,
    conflict: str = CONFLICT_SKIP,
) -> RestorePlan:
    """把成功改名的条目反向成 new -> old。"""
    if conflict not in (CONFLICT_SKIP, CONFLICT_RENAME):
        raise ValueError(f"未知的冲突策略：{conflict}")

    plan = RestorePlan()
    taken_by_dir: dict[str, set[str]] = {}

    for item in record.items:
        if item.status != STATUS_OK:
            continue
        plan.ok_items += 1

        new_path = Path(item.new)
        old_path = Path(item.old)

        if not path_exists(new_path):
            plan.missing.append(item.new)
            continue

        if not path_exists(old_path.parent):
            plan.skipped.append((item.new, "原目录不存在"))
            continue

        target = old_path
        if path_exists(old_path) and not same_file(old_path, new_path):
            if conflict == CONFLICT_SKIP:
                plan.skipped.append((item.new, f"原位置已被占用：{old_path}"))
                continue
            directory_key = norm_path(old_path.parent)
            if directory_key not in taken_by_dir:
                taken_by_dir[directory_key] = _dir_names(old_path.parent)
            stem, ext = split_name(old_path.name)
            stem, ext, _resolved = allocate_unique(
                stem, ext, taken_by_dir[directory_key], True
            )
            target = old_path.with_name(join_name(stem, ext))
            taken_by_dir[directory_key].add(target.name.casefold())

        plan.items.append(RenameItem(new_path, target))

    return plan


def latest_restorable(store: BackupStore) -> BackupRecord | None:
    for record in store.list_records():
        if record.kind != KIND_RENAME:
            continue
        if record.state not in (STATE_COMPLETED, STATE_COMPLETED_WITH_ERRORS):
            continue
        if any(item.status == STATUS_OK for item in record.items):
            return record
    return None


def undo_last(
    store: BackupStore,
    conflict: str = CONFLICT_SKIP,
    executor: RenameExecutor | None = None,
) -> RestoreOutcome:
    record = latest_restorable(store)
    if record is None:
        raise UndoError("没有可撤销的重命名记录")
    return restore_batch(store, record.batch_id, conflict=conflict, executor=executor)


def restore_batch(
    store: BackupStore,
    batch_id: str,
    conflict: str = CONFLICT_SKIP,
    executor: RenameExecutor | None = None,
) -> RestoreOutcome:
    record = store.find(batch_id)
    if record is None:
        raise UndoError(f"找不到备份记录：{batch_id}")
    if record.state == STATE_ROLLED_BACK:
        raise UndoError("该批次已经还原过")

    plan = build_reverse_plan(record, conflict=conflict)
    if not plan.items:
        details: list[str] = []
        if plan.missing:
            details.append(f"{len(plan.missing)} 个文件已不存在")
        if plan.skipped:
            details.append(f"{len(plan.skipped)} 个原位置被占用")
        message = "没有可还原的文件"
        if details:
            message += "：" + "，".join(details)
        raise UndoError(message)

    worker = executor or RenameExecutor(store)
    result = worker.execute(plan.items, kind=KIND_RESTORE)

    fully_restored = (
        result.failed == 0 and not plan.skipped and not plan.missing
    )
    if fully_restored:
        record.state = STATE_ROLLED_BACK
        record.finished_at = now_iso()
        record.note = f"已还原（还原批次 {result.batch_id}）"
    else:
        record.note = (
            f"部分还原：成功 {result.success}，失败 {result.failed}，"
            f"跳过 {len(plan.skipped)}，缺失 {len(plan.missing)}"
        )
    store.save(record)

    return RestoreOutcome(
        original=record,
        result=result,
        plan=plan,
        fully_restored=fully_restored,
    )


def recover_incomplete(
    store: BackupStore,
    retries: int = 3,
    retry_delay: float = 0.05,
) -> list[RecoveryOutcome]:
    """启动时调用：把未完成批次里的文件尽量还原到原路径。"""
    outcomes: list[RecoveryOutcome] = []

    for record in store.unfinished():
        restored = 0
        errors: list[str] = []

        for item in record.items:
            old_path = Path(item.old)
            new_path = Path(item.new)
            temp_path = Path(item.temp) if item.temp else None

            if temp_path is not None and path_exists(temp_path):
                if path_exists(old_path):
                    errors.append(f"原位置已被占用，临时文件保留：{temp_path}")
                    item.status = STATUS_FAILED
                    item.error = f"原位置已被占用，临时文件保留：{temp_path}"
                    continue
                try:
                    rename_with_retry(temp_path, old_path, retries, retry_delay)
                    item.status = STATUS_ROLLED_BACK
                    item.error = ""
                    item.temp = ""
                    restored += 1
                except OSError as exc:
                    errors.append(f"还原 {temp_path} 失败：{exc}")
                    item.status = STATUS_FAILED
                    item.error = f"还原失败：{exc}"
                continue

            if path_exists(new_path):
                if path_exists(old_path) and not same_file(old_path, new_path):
                    errors.append(f"原位置已被占用，无法还原：{new_path}")
                    item.status = STATUS_FAILED
                    item.error = "原位置已被占用，无法还原"
                    continue
                try:
                    if str(new_path) != str(old_path):
                        rename_with_retry(new_path, old_path, retries, retry_delay)
                    item.status = STATUS_ROLLED_BACK
                    item.error = ""
                    restored += 1
                except OSError as exc:
                    errors.append(f"还原 {new_path} 失败：{exc}")
                    item.status = STATUS_FAILED
                    item.error = f"还原失败：{exc}"
                continue

            if path_exists(old_path):
                if item.status == STATUS_OK:
                    item.status = STATUS_ROLLED_BACK
                continue

            errors.append(f"文件缺失，无法还原：{item.old}")
            item.status = STATUS_FAILED
            item.error = "文件缺失，无法还原"

        record.state = STATE_ROLLED_BACK if not errors else STATE_INCOMPLETE
        if not errors:
            record.finished_at = now_iso()
        record.note = f"崩溃恢复：已还原 {restored} 个文件"
        if errors:
            record.note += f"，{len(errors)} 个问题"
        store.save(record)

        outcomes.append(RecoveryOutcome(record=record, restored=restored, errors=errors))

    return outcomes
