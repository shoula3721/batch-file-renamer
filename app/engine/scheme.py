"""重命名方案（.bfr.json）的导入与导出。

只保存规则与界面偏好，不保存文件列表，避免路径失效后在别的机器上误改文件。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from app import __version__

from .rules import RuleSet, RuleSetError

SCHEME_SCHEMA = 1
SORT_KEYS = (
    "natural",
    "name",
    "preview",
    "result",
    "status",
    "mtime",
    "taken",
    "size",
    "ext",
)
DEFAULT_SORT_KEY = "natural"


class SchemeError(ValueError):
    """方案文件格式不正确或版本过新。"""


def normalize_extensions(values: Iterable[object]) -> list[str]:
    """把 "mp4;.MKV"、列表等整理成去重、去点、小写的扩展名列表。"""
    result: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        if not isinstance(value, str):
            continue
        for part in value.replace(";", ",").split(","):
            extension = part.strip().lower().lstrip(".")
            if extension and extension not in seen:
                seen.add(extension)
                result.append(extension)
    return sorted(result)


@dataclass
class Scheme:
    rules: RuleSet = field(default_factory=RuleSet)
    filter_extensions: list[str] = field(default_factory=list)
    sort_key: str = DEFAULT_SORT_KEY
    sort_ascending: bool = True
    app_version: str = __version__
    exported_at: str = ""
    schema: int = SCHEME_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        exported_at = self.exported_at or datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
        return {
            "schema": SCHEME_SCHEMA,
            "app": "批量文件改名",
            "app_version": self.app_version,
            "exported_at": exported_at,
            "rules": self.rules.to_dict(),
            "filters": {"extensions": normalize_extensions(self.filter_extensions)},
            "sort": {
                "key": self.sort_key,
                "ascending": bool(self.sort_ascending),
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scheme":
        if not isinstance(data, dict):
            raise SchemeError("方案数据必须是 JSON 对象")
        try:
            version = int(data.get("schema", SCHEME_SCHEMA))
        except (TypeError, ValueError) as exc:
            raise SchemeError("方案版本号无效") from exc
        if version > SCHEME_SCHEMA:
            raise SchemeError(
                f"方案版本（{version}）高于当前程序支持的版本（{SCHEME_SCHEMA}），请升级程序"
            )
        rules_data = data.get("rules", {})
        if not isinstance(rules_data, dict):
            raise SchemeError("方案中的规则数据格式不正确")
        try:
            rules = RuleSet.from_dict(rules_data)
        except RuleSetError as exc:
            raise SchemeError(f"规则数据无效：{exc}") from exc

        filters = data.get("filters", {})
        if not isinstance(filters, dict):
            filters = {}
        raw_extensions = filters.get("extensions", [])
        if isinstance(raw_extensions, str):
            raw_extensions = [raw_extensions]
        if not isinstance(raw_extensions, list):
            raw_extensions = []

        sort = data.get("sort", {})
        if not isinstance(sort, dict):
            sort = {}
        sort_key = str(sort.get("key", DEFAULT_SORT_KEY))
        if sort_key not in SORT_KEYS:
            sort_key = DEFAULT_SORT_KEY
        ascending = bool(sort.get("ascending", True))

        return cls(
            rules=rules,
            filter_extensions=normalize_extensions(raw_extensions),
            sort_key=sort_key,
            sort_ascending=ascending,
            app_version=str(data.get("app_version", "")),
            exported_at=str(data.get("exported_at", "")),
            schema=version,
        )

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path) -> "Scheme":
        file_path = Path(path)
        text = file_path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SchemeError(f"方案文件不是有效的 JSON：{exc}") from exc
        return cls.from_dict(data)

    def save(self, path: str | Path) -> Path:
        file_path = Path(path)
        text = json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"
        temp = file_path.with_name(file_path.name + ".tmp")
        try:
            temp.write_text(text, encoding="utf-8")
            os.replace(temp, file_path)
        finally:
            if temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass
        return file_path
