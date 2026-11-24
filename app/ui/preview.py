"""界面预览：把规则套用到文件列表，生成目标名、状态与拍摄时间信息。

预览不写盘。拍摄时间来自 EXIF / MP4 mvhd，读取结果进入 CaptureCache；
按目录分组生成，避免不同目录的同名文件互相误判冲突。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from app.engine.metadata import (
    CaptureCache,
    CaptureInfo,
    MetadataError,
    build_placeholder_metadata,
    read_capture,
)
from app.engine.namer import plan_batch
from app.engine.rules import RuleSet


class PreviewCancelled(Exception):
    """预览被取消（窗口关闭或列表变化）。"""


@dataclass
class PreviewInfo:
    target_name: str = ""
    status: str = "就绪"
    error: str = ""
    unchanged: bool = False
    conflict_resolved: bool = False
    taken_at: float | None = None
    taken_source: str = ""
    taken_raw: str = ""
    taken_fallback: bool = False
    media_tags: dict[str, str] = field(default_factory=dict)


def _taken_fields(meta: Mapping[str, object]) -> dict[str, object]:
    timestamp = meta.get("capture_timestamp")
    fields: dict[str, object] = {}
    if isinstance(timestamp, (int, float)):
        fields.update(
            {
                "taken_at": float(timestamp),
                "taken_source": str(meta.get("capture_source") or ""),
                "taken_raw": str(meta.get("capture_raw") or ""),
                "taken_fallback": bool(meta.get("capture_fallback")),
            }
        )
    tags = meta.get("media_tags")
    if isinstance(tags, Mapping):
        fields["media_tags"] = {
            str(key): str(value) for key, value in tags.items() if value
        }
    return fields


def load_captures(
    paths: Sequence[Path],
    cache: CaptureCache,
    progress: Callable[[int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, CaptureInfo]:
    """批量读取拍摄时间（后台线程调用），结果写回缓存。"""
    result: dict[str, CaptureInfo] = {}
    total = len(paths)
    for index, path in enumerate(paths):
        if should_stop is not None and should_stop():
            raise PreviewCancelled()
        result[str(path)] = cache.get(path)
        if progress is not None:
            progress(index + 1, total)
    return result


def _directory_names(directory: Path) -> set[str]:
    try:
        return {entry.name for entry in directory.iterdir()}
    except OSError:
        return set()


def build_previews(
    paths: Sequence[Path],
    rules: RuleSet,
    metadata: Mapping[str, Mapping[str, object]] | None = None,
    captures: Mapping[str, CaptureInfo] | None = None,
    cache: CaptureCache | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[PreviewInfo]:
    """按目录分组生成预览。

    metadata 用于测试或调用方直接提供占位符数据；未提供时按 captures/cache
    读取拍摄时间，并套用 rules.metadata 里的日期来源与格式。
    """
    infos = [PreviewInfo() for _ in paths]
    grouped: dict[Path, list[tuple[int, Path]]] = {}
    for index, path in enumerate(paths):
        grouped.setdefault(path.parent, []).append((index, path))

    for directory, members in grouped.items():
        filenames = [path.name for _index, path in members]
        metas: list[Mapping[str, object]] = []
        failures: dict[int, str] = {}
        for index, path in members:
            if should_stop is not None and should_stop():
                raise PreviewCancelled()
            meta: Mapping[str, object] | None = None
            if metadata is not None:
                meta = metadata.get(str(path))
            if meta is None:
                capture = None
                if captures is not None:
                    capture = captures.get(str(path))
                if capture is None and cache is not None:
                    capture = cache.get(path)
                if capture is None:
                    capture = read_capture(path)
                try:
                    meta = build_placeholder_metadata(path, capture, rules.metadata)
                except MetadataError as exc:
                    failures[index] = str(exc)
                    meta = {}
                except OSError as exc:
                    failures[index] = f"无法读取文件属性：{exc}"
                    meta = {}
            metas.append(meta)

        plans = plan_batch(
            filenames,
            rules,
            metadata=metas,
            taken_names=_directory_names(directory),
            indexes=[index for index, _path in members],
        )
        for position, ((index, _path), plan) in enumerate(zip(members, plans)):
            if should_stop is not None and should_stop():
                raise PreviewCancelled()
            if index in failures:
                infos[index] = PreviewInfo(status="错误", error=failures[index])
                continue
            taken = _taken_fields(metas[position])
            if plan.error:
                infos[index] = PreviewInfo(status="错误", error=plan.error, **taken)
            elif plan.unchanged:
                infos[index] = PreviewInfo(
                    target_name=plan.target,
                    status="未更改",
                    unchanged=True,
                    **taken,
                )
            else:
                infos[index] = PreviewInfo(
                    target_name=plan.target,
                    status="冲突已处理" if plan.conflict_resolved else "就绪",
                    conflict_resolved=plan.conflict_resolved,
                    **taken,
                )
    return infos


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    """去重并保持输入顺序。"""
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        absolute = Path(os.path.abspath(str(path)))
        key = os.path.normcase(str(absolute))
        if key in seen:
            continue
        seen.add(key)
        result.append(absolute)
    return result
