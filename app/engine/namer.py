"""命名流水线：把原始文件名和规则转换为目标文件名。

顺序（与开发方案一致）：
    添加/删除 -> 替换 -> 命名规则(* / # / {占位符}) -> 扩展名 -> 大小写 -> 冲突处理
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from .rules import AddRemoveRule, OverallRule, ReplaceRule, RuleSet
from .validate import (
    NameConflictError,
    allocate_unique,
    join_name,
    normalize_extension,
    split_name,
    validate_filename,
)


class RuleError(ValueError):
    """规则本身不合法（正则错误、字母编号起点错误等）。"""


# ---------------------------------------------------------------------------
# 添加 / 删除
# ---------------------------------------------------------------------------
def apply_add_remove(stem: str, rule: AddRemoveRule) -> str:
    if rule.prefix:
        stem = rule.prefix + stem
    if rule.suffix:
        stem = stem + rule.suffix

    if rule.insert_enabled and rule.insert_text:
        position = min(max(rule.insert_position, 1), len(stem) + 1)
        stem = stem[: position - 1] + rule.insert_text + stem[position - 1 :]

    if rule.delete_text:
        stem = stem.replace(rule.delete_text, "")

    if rule.cut_enabled and rule.cut_count > 0 and stem:
        start = min(max(rule.cut_position, 1), len(stem))
        stem = stem[: start - 1] + stem[start - 1 + rule.cut_count :]

    return stem


# ---------------------------------------------------------------------------
# 替换（普通 / 正则）
# ---------------------------------------------------------------------------
def _convert_dollar_refs(replacement: str) -> str:
    """把用户习惯的 $1 / ${name} / $name 转成 re.sub 的 \\g<...>。"""
    result: list[str] = []
    index = 0
    length = len(replacement)
    while index < length:
        char = replacement[index]
        if char != "$":
            result.append(char)
            index += 1
            continue

        if index + 1 < length and replacement[index + 1] == "$":
            result.append("$")
            index += 2
            continue

        if index + 1 < length and replacement[index + 1] == "{":
            end = replacement.find("}", index + 2)
            if end != -1:
                name = replacement[index + 2 : end]
                if name:
                    result.append(rf"\g<{name}>")
                    index = end + 1
                    continue

        if index + 1 < length and replacement[index + 1].isdigit():
            end = index + 1
            while end < length and replacement[end].isdigit():
                end += 1
            result.append(rf"\g<{replacement[index + 1 : end]}>")
            index = end
            continue

        if index + 1 < length and (
            replacement[index + 1].isalpha() or replacement[index + 1] == "_"
        ):
            end = index + 1
            while end < length and (
                replacement[end].isalnum() or replacement[end] == "_"
            ):
                end += 1
            result.append(rf"\g<{replacement[index + 1 : end]}>")
            index = end
            continue

        result.append("$")
        index += 1

    return "".join(result)


def _replace_text(text: str, rule: ReplaceRule) -> str:
    count = 1 if rule.first_only else 0

    if rule.use_regex:
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(rule.old, flags)
        except re.error as exc:
            raise RuleError(f"正则表达式无效：{exc}") from exc

        replacement = _convert_dollar_refs(rule.new)
        try:
            return pattern.sub(replacement, text, count=count)
        except (re.error, IndexError) as exc:
            raise RuleError(f"正则替换失败：{exc}") from exc

    if rule.case_sensitive:
        return text.replace(rule.old, rule.new, count if rule.first_only else -1)

    pattern = re.compile(re.escape(rule.old), re.IGNORECASE)
    return pattern.sub(lambda _match: rule.new, text, count=count)


def apply_replace(stem: str, ext: str, rule: ReplaceRule) -> tuple[str, str]:
    if not rule.enabled:
        return stem, ext
    if rule.include_extension:
        return split_name(_replace_text(join_name(stem, ext), rule))
    return _replace_text(stem, rule), ext


# ---------------------------------------------------------------------------
# 编号与命名规则
# ---------------------------------------------------------------------------
def to_letters(number: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA（Excel 列名规则）。"""
    if number < 1:
        raise RuleError("字母编号的开始值必须大于等于 1")
    chars: list[str] = []
    value = number
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        chars.append(chr(ord("A") + remainder))
    return "".join(reversed(chars))


def format_counter(number: int, overall: OverallRule) -> str:
    if overall.letter_mode:
        text = to_letters(number)
        if overall.pad and overall.digits > len(text):
            text = "A" * (overall.digits - len(text)) + text
        return text.upper() if overall.letter_case == "upper" else text.lower()

    if overall.pad:
        return f"{number:0{max(1, overall.digits)}d}"
    return str(number)


def resolve_placeholder(
    token: str,
    stem: str,
    ext: str,
    counter: str,
    metadata: Mapping[str, Any],
) -> str:
    name, _, fmt = token.partition(":")
    name = name.strip()
    fmt = fmt.strip()

    if name in ("name", "*"):
        return stem
    if name in ("n", "#", "index"):
        return counter
    if name == "ext":
        return ext
    if name not in metadata:
        return ""

    value = metadata[name]
    if value is None:
        return ""
    if isinstance(value, datetime):
        pattern = fmt
        if not pattern:
            if name == "date":
                pattern = str(metadata.get("date_format") or "%Y-%m-%d_%H%M%S")
            elif name == "datetime":
                pattern = str(metadata.get("datetime_format") or "%Y-%m-%d_%H%M%S")
            else:
                pattern = "%Y-%m-%d_%H%M%S"
        return value.strftime(pattern)
    if isinstance(value, date):
        return value.strftime(fmt or "%Y-%m-%d")
    if fmt and isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return format(value, fmt)
        except (ValueError, TypeError):
            return str(value)
    return str(value)


def expand_template(
    template: str,
    stem: str,
    ext: str,
    overall: OverallRule,
    index: int,
    metadata: Mapping[str, Any],
) -> str:
    """展开 *、#、{占位符}；支持 \\* \\# \\{ \\\\ 转义。"""
    if template == "":
        return stem

    number = overall.start + index * overall.step
    counter = format_counter(number, overall)

    result: list[str] = []
    position = 0
    length = len(template)
    while position < length:
        char = template[position]

        if char == "\\" and position + 1 < length and template[position + 1] in "*#{}\\":
            result.append(template[position + 1])
            position += 2
            continue

        if char == "*":
            result.append(stem)
            position += 1
            continue

        if char == "#":
            result.append(counter)
            position += 1
            continue

        if char == "{":
            end = template.find("}", position + 1)
            if end != -1:
                token = template[position + 1 : end]
                result.append(resolve_placeholder(token, stem, ext, counter, metadata))
                position = end + 1
                continue

        result.append(char)
        position += 1

    return "".join(result)


# ---------------------------------------------------------------------------
# 大小写
# ---------------------------------------------------------------------------
def apply_case(stem: str, ext: str, option: str) -> tuple[str, str]:
    if option in ("stem_lower", "both_lower"):
        stem = stem.lower()
    if option in ("ext_lower", "both_lower"):
        ext = ext.lower()
    if option in ("stem_upper", "both_upper"):
        stem = stem.upper()
    if option in ("ext_upper", "both_upper"):
        ext = ext.upper()
    return stem, ext


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def build_target_name(
    filename: str,
    rules: RuleSet,
    index: int,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """返回 (目标主体, 目标扩展名)，不做磁盘访问。"""
    stem, ext = split_name(filename)

    stem = apply_add_remove(stem, rules.add_remove)
    stem, ext = apply_replace(stem, ext, rules.replace)
    stem = expand_template(
        rules.overall.template, stem, ext, rules.overall, index, metadata or {}
    )

    # 模板里显式写了 .{ext} 时，避免再追加一次扩展名
    if ext and "{ext}" in rules.overall.template:
        suffix = "." + ext
        if stem.casefold().endswith(suffix.casefold()):
            stem = stem[: -len(suffix)]

    if rules.overall.change_extension:
        new_extension = normalize_extension(rules.overall.new_extension)
        if new_extension:
            ext = new_extension

    return apply_case(stem, ext, rules.overall.case_option)


def build_full_target(
    filename: str,
    rules: RuleSet,
    index: int,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    stem, ext = build_target_name(filename, rules, index, metadata)
    return join_name(stem, ext)


@dataclass
class PlannedName:
    source: str
    target: str
    error: str | None = None
    unchanged: bool = False
    conflict_resolved: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None


def plan_batch(
    filenames: Sequence[str],
    rules: RuleSet,
    metadata: Sequence[Mapping[str, Any]] | None = None,
    taken_names: set[str] | None = None,
    indexes: Sequence[int] | None = None,
) -> list[PlannedName]:
    """为一整批文件名生成目标名并处理冲突。

    taken_names 应包含目标目录中已有的全部名称（含本批源文件名）；
    未提供时只考虑本批文件。函数会自动扣除“改名后会被腾空”的源名称，
    因此 1.txt <-> 2.txt 这类互换不会被误判为冲突。

    indexes 可选，用于多目录分组时保持全局编号顺序；默认 0..n-1。
    """
    metas: list[Mapping[str, Any]]
    if metadata is None:
        metas = [{} for _ in filenames]
    else:
        metas = list(metadata)
        if len(metas) != len(filenames):
            raise ValueError("metadata 数量必须与 filenames 一致")

    if indexes is None:
        index_list = list(range(len(filenames)))
    else:
        index_list = list(indexes)
        if len(index_list) != len(filenames):
            raise ValueError("indexes 数量必须与 filenames 一致")

    preliminary: list[tuple[str, str, str | None, str, str]] = []
    for position, (filename, meta) in enumerate(zip(filenames, metas)):
        index = index_list[position]
        try:
            stem, ext = build_target_name(filename, rules, index, meta)
            target = join_name(stem, ext)
            errors = validate_filename(target)
            error = "；".join(errors) if errors else None
        except RuleError as exc:
            stem, ext, target, error = "", "", "", str(exc)
        preliminary.append((filename, target, error, stem, ext))

    taken = {name.casefold() for name in (taken_names or filenames)}
    taken |= {name.casefold() for name in filenames}
    vacated = {
        source.casefold()
        for source, target, error, _stem, _ext in preliminary
        if error is None and target != source
    }
    occupied = taken - vacated

    plans: list[PlannedName] = []
    for source, target, error, stem, ext in preliminary:
        if error is not None:
            plans.append(PlannedName(source=source, target=target, error=error))
            continue

        unchanged = target == source
        resolved = False

        if not unchanged and target.casefold() in occupied:
            if not rules.overall.auto_resolve:
                plans.append(
                    PlannedName(source=source, target=target, error="目标名称已存在")
                )
                continue
            try:
                stem, ext, resolved = allocate_unique(stem, ext, occupied, True)
            except NameConflictError as exc:
                plans.append(PlannedName(source=source, target=target, error=str(exc)))
                continue
            target = join_name(stem, ext)
            errors = validate_filename(target)
            if errors:
                plans.append(
                    PlannedName(source=source, target=target, error="；".join(errors))
                )
                continue
            unchanged = target == source

        occupied.add(target.casefold())
        plans.append(
            PlannedName(
                source=source,
                target=target,
                error=None,
                unchanged=unchanged,
                conflict_resolved=resolved,
            )
        )

    return plans
