"""规则模型与 JSON 序列化测试。"""
from __future__ import annotations

import pytest

from app.engine.rules import (
    CASE_OPTIONS,
    SCHEMA_VERSION,
    AddRemoveRule,
    MetadataRule,
    OverallRule,
    ReplaceRule,
    RuleSet,
    RuleSetError,
)


def test_default_rules_are_neutral() -> None:
    rules = RuleSet()
    assert rules.overall.template == ""
    assert rules.replace.enabled is False
    assert rules.overall.case_option == "none"
    assert rules.overall.auto_resolve is True
    assert rules.metadata.date_source == "exif"
    assert rules.metadata.date_format == "date"
    assert rules.metadata.timezone == "original"


def test_case_options_cover_reference_ui() -> None:
    assert len(CASE_OPTIONS) == 7
    assert CASE_OPTIONS["none"] == "不改变"


def test_roundtrip_preserves_values() -> None:
    rules = RuleSet(
        add_remove=AddRemoveRule(
            prefix="P_", suffix="_S", insert_enabled=True, insert_position=3,
            insert_text="X", delete_text="tmp", cut_enabled=True, cut_position=2,
            cut_count=4,
        ),
        replace=ReplaceRule(
            old=r"(IMG)_(\d+)", new="照片_$2", use_regex=True,
            case_sensitive=False, first_only=True, include_extension=True,
        ),
        overall=OverallRule(
            template="A_#", start=10, step=5, digits=3, pad=True,
            letter_mode=True, letter_case="upper", change_extension=True,
            new_extension="mp4", case_option="both_lower", auto_resolve=False,
        ),
        metadata=MetadataRule(
            date_source="ctime",
            date_format="custom",
            custom_format="%Y%m%d_%H%M%S",
            timezone="local",
        ),
    )
    restored = RuleSet.from_dict(rules.to_dict())
    assert restored == rules
    assert restored.metadata.date_source == "ctime"
    assert restored.metadata.custom_format == "%Y%m%d_%H%M%S"


def test_unknown_keys_are_ignored() -> None:
    data = {
        "schema": SCHEMA_VERSION,
        "overall": {"template": "x", "unknown": 1},
        "replace": {"old": "a", "mystery": True},
        "extra_section": {"a": 1},
    }
    rules = RuleSet.from_dict(data)
    assert rules.overall.template == "x"
    assert rules.replace.old == "a"


def test_missing_sections_use_defaults() -> None:
    rules = RuleSet.from_dict({})
    assert rules == RuleSet()


def test_newer_schema_is_rejected() -> None:
    with pytest.raises(RuleSetError):
        RuleSet.from_dict({"schema": SCHEMA_VERSION + 1})


def test_invalid_schema_type_is_rejected() -> None:
    with pytest.raises(RuleSetError):
        RuleSet.from_dict({"schema": "abc"})


def test_non_dict_payload_is_rejected() -> None:
    with pytest.raises(RuleSetError):
        RuleSet.from_dict([])  # type: ignore[arg-type]


def test_json_values_are_coerced() -> None:
    rules = RuleSet.from_dict(
        {
            "overall": {"start": "3", "pad": 0, "template": 123},
            "replace": {"use_regex": "yes"},
            "metadata": {"date_source": 1, "timezone": "local"},
        }
    )
    assert rules.overall.start == 3
    assert rules.overall.pad is False
    assert rules.overall.template == "123"
    assert rules.replace.use_regex is True
    assert rules.metadata.timezone == "local"


def test_old_scheme_without_metadata_uses_defaults() -> None:
    rules = RuleSet.from_dict(
        {"schema": SCHEMA_VERSION, "overall": {"template": "x"}}
    )
    assert rules.metadata == MetadataRule()
