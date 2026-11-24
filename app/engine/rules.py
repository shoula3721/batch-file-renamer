"""规则数据模型与 JSON 序列化。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

SCHEMA_VERSION = 1

# 界面下拉项：key -> 中文标签
CASE_OPTIONS: dict[str, str] = {
    "none": "不改变",
    "stem_lower": "改变文件名为小写",
    "ext_lower": "改变扩展名为小写",
    "both_lower": "改变文件名和扩展名为小写",
    "stem_upper": "改变文件名为大写",
    "ext_upper": "改变扩展名为大写",
    "both_upper": "改变文件名和扩展名为大写",
}

LETTER_CASE_OPTIONS: dict[str, str] = {
    "lower": "小写",
    "upper": "大写",
}


class RuleSetError(ValueError):
    """规则数据非法或版本过新。"""


@dataclass
class AddRemoveRule:
    """添加/删除标签页。"""

    prefix: str = ""
    suffix: str = ""
    insert_enabled: bool = False
    insert_position: int = 1
    insert_text: str = ""
    delete_text: str = ""
    cut_enabled: bool = False
    cut_position: int = 1
    cut_count: int = 1


@dataclass
class ReplaceRule:
    """替换标签页。"""

    old: str = ""
    new: str = ""
    use_regex: bool = False
    case_sensitive: bool = True
    first_only: bool = False
    include_extension: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.old)


@dataclass
class OverallRule:
    """整体标签页。"""

    template: str = ""
    start: int = 1
    step: int = 1
    digits: int = 1
    pad: bool = True
    letter_mode: bool = False
    letter_case: str = "lower"
    change_extension: bool = False
    new_extension: str = ""
    case_option: str = "none"
    auto_resolve: bool = True


def _coerce_fields(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    """按默认值类型做宽松转换，容忍手工编辑过的 JSON。"""
    if not isinstance(data, dict):
        return {}
    result: dict[str, Any] = {}
    for item in fields(cls):
        if item.name not in data:
            continue
        value = data[item.name]
        default = item.default
        try:
            if isinstance(default, bool):
                value = bool(value)
            elif isinstance(default, int):
                value = int(value)
            elif isinstance(default, str):
                value = str(value)
        except (TypeError, ValueError):
            value = default
        result[item.name] = value
    return result


@dataclass
class MetadataRule:
    """元数据标签页：拍摄时间的来源、格式与时区。"""

    date_source: str = "exif"  # exif / mtime / ctime
    date_format: str = "date"  # date / compact / datetime / custom
    custom_format: str = ""
    timezone: str = "original"  # original / local


@dataclass
class RuleSet:
    """一次改名任务的全部规则。"""

    add_remove: AddRemoveRule = field(default_factory=AddRemoveRule)
    replace: ReplaceRule = field(default_factory=ReplaceRule)
    overall: OverallRule = field(default_factory=OverallRule)
    metadata: MetadataRule = field(default_factory=MetadataRule)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "add_remove": asdict(self.add_remove),
            "replace": asdict(self.replace),
            "overall": asdict(self.overall),
            "metadata": asdict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuleSet":
        if not isinstance(data, dict):
            raise RuleSetError("方案数据格式不正确")
        raw_version = data.get("schema", SCHEMA_VERSION)
        try:
            version = int(raw_version)
        except (TypeError, ValueError) as exc:
            raise RuleSetError("方案版本号无效") from exc
        if version > SCHEMA_VERSION:
            raise RuleSetError(
                f"方案版本（{version}）高于当前程序支持的版本（{SCHEMA_VERSION}），请升级程序"
            )
        return cls(
            add_remove=AddRemoveRule(**_coerce_fields(AddRemoveRule, data.get("add_remove", {}))),
            replace=ReplaceRule(**_coerce_fields(ReplaceRule, data.get("replace", {}))),
            overall=OverallRule(**_coerce_fields(OverallRule, data.get("overall", {}))),
            metadata=MetadataRule(**_coerce_fields(MetadataRule, data.get("metadata", {}))),
        )
