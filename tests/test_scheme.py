"""方案文件（.bfr.json）序列化与导入校验测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.engine.rules import MetadataRule, OverallRule, RuleSet
from app.engine.scheme import (
    SCHEME_SCHEMA,
    Scheme,
    SchemeError,
    normalize_extensions,
)


def test_normalize_extensions_variants() -> None:
    assert normalize_extensions(["MP4", ".mkv", " mp4 ", "", None, 3]) == ["mkv", "mp4"]
    assert normalize_extensions(["mp4;mkv", "jpg,mkv"]) == ["jpg", "mkv", "mp4"]
    assert normalize_extensions([]) == []


def test_scheme_roundtrip() -> None:
    rules = RuleSet(
        overall=OverallRule(template="{date}_*", digits=2, pad=True),
        metadata=MetadataRule(date_format="compact"),
    )
    scheme = Scheme(
        rules=rules,
        filter_extensions=["mp4", ".JPG"],
        sort_key="taken",
        sort_ascending=False,
    )

    restored = Scheme.from_dict(scheme.to_dict())

    assert restored.rules == rules
    assert restored.filter_extensions == ["jpg", "mp4"]
    assert restored.sort_key == "taken"
    assert restored.sort_ascending is False
    assert restored.schema == SCHEME_SCHEMA


def test_scheme_to_dict_shape() -> None:
    data = Scheme().to_dict()

    assert data["schema"] == SCHEME_SCHEMA
    assert data["app"] == "批量文件改名"
    assert data["filters"] == {"extensions": []}
    assert data["sort"] == {"key": "natural", "ascending": True}
    assert "rules" in data


def test_scheme_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "方案.bfr.json"
    scheme = Scheme(
        rules=RuleSet(overall=OverallRule(template="测试_#")),
        filter_extensions=["mp4"],
    )

    scheme.save(path)
    restored = Scheme.load(path)

    assert restored.rules.overall.template == "测试_#"
    assert restored.filter_extensions == ["mp4"]
    assert not path.with_name(path.name + ".tmp").exists()


def test_newer_schema_is_rejected() -> None:
    data = Scheme().to_dict()
    data["schema"] = SCHEME_SCHEMA + 1

    with pytest.raises(SchemeError, match="高于当前程序"):
        Scheme.from_dict(data)


def test_invalid_rules_are_reported() -> None:
    data = Scheme().to_dict()
    data["rules"] = "not-a-dict"

    with pytest.raises(SchemeError, match="规则数据格式"):
        Scheme.from_dict(data)


def test_invalid_filter_and_sort_values_fall_back() -> None:
    data = Scheme().to_dict()
    data["filters"] = {"extensions": "mp4;mkv"}
    data["sort"] = {"key": "unknown", "ascending": "yes"}

    scheme = Scheme.from_dict(data)

    assert scheme.filter_extensions == ["mkv", "mp4"]
    assert scheme.sort_key == "natural"
    assert scheme.sort_ascending is True


def test_invalid_json_raises_scheme_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.bfr.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(SchemeError, match="有效的 JSON"):
        Scheme.load(path)


def test_json_content_is_readable(tmp_path: Path) -> None:
    path = tmp_path / "a.bfr.json"
    Scheme(rules=RuleSet(overall=OverallRule(template="x"))).save(path)

    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["rules"]["overall"]["template"] == "x"
    assert data["app_version"] == Scheme().app_version
