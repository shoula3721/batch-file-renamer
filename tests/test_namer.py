"""命名流水线测试：添加删除、替换、编号、占位符、大小写、冲突。"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.engine.namer import (
    RuleError,
    apply_add_remove,
    apply_case,
    apply_replace,
    build_full_target,
    build_target_name,
    format_counter,
    plan_batch,
    to_letters,
)
from app.engine.rules import AddRemoveRule, OverallRule, ReplaceRule, RuleSet


# ---------------------------------------------------------------------------
# 添加 / 删除
# ---------------------------------------------------------------------------
def test_prefix_and_suffix() -> None:
    rule = AddRemoveRule(prefix="PRE_", suffix="_SUF")
    assert apply_add_remove("abc", rule) == "PRE_abc_SUF"


def test_insert_position() -> None:
    rule = AddRemoveRule(insert_enabled=True, insert_position=2, insert_text="X")
    assert apply_add_remove("abc", rule) == "aXbc"


def test_insert_clamps_position() -> None:
    rule = AddRemoveRule(insert_enabled=True, insert_position=0, insert_text="X")
    assert apply_add_remove("abc", rule) == "Xabc"
    rule.insert_position = 99
    assert apply_add_remove("abc", rule) == "abcX"


def test_delete_all_occurrences() -> None:
    rule = AddRemoveRule(delete_text="ab")
    assert apply_add_remove("abab", rule) == ""


def test_cut_characters() -> None:
    rule = AddRemoveRule(cut_enabled=True, cut_position=2, cut_count=3)
    assert apply_add_remove("abcdef", rule) == "aef"


def test_cut_clamps_to_length() -> None:
    rule = AddRemoveRule(cut_enabled=True, cut_position=99, cut_count=99)
    assert apply_add_remove("abc", rule) == "ab"


def test_cut_disabled_or_zero_count_is_noop() -> None:
    assert apply_add_remove("abc", AddRemoveRule(cut_enabled=False, cut_count=2)) == "abc"
    assert apply_add_remove("abc", AddRemoveRule(cut_enabled=True, cut_count=0)) == "abc"


def test_add_remove_pipeline_order() -> None:
    rule = AddRemoveRule(
        prefix="P",
        suffix="S",
        insert_enabled=True,
        insert_position=2,
        insert_text="X",
        delete_text="X",
        cut_enabled=True,
        cut_position=1,
        cut_count=1,
    )
    assert apply_add_remove("abc", rule) == "abcS"


# ---------------------------------------------------------------------------
# 替换
# ---------------------------------------------------------------------------
def test_plain_replace_keeps_extension() -> None:
    stem, ext = apply_replace("IMG_001", "JPG", ReplaceRule(old="IMG_", new="照片_"))
    assert (stem, ext) == ("照片_001", "JPG")


def test_plain_replace_case_sensitive() -> None:
    stem, _ = apply_replace("ABCabc", "txt", ReplaceRule(old="abc", new="X"))
    assert stem == "ABCX"


def test_plain_replace_case_insensitive() -> None:
    stem, _ = apply_replace(
        "ABCabc", "txt", ReplaceRule(old="abc", new="X", case_sensitive=False)
    )
    assert stem == "XX"


def test_plain_replace_first_only() -> None:
    stem, _ = apply_replace(
        "aaa", "txt", ReplaceRule(old="a", new="b", first_only=True)
    )
    assert stem == "baa"


def test_replace_include_extension() -> None:
    stem, ext = apply_replace(
        "a", "txt", ReplaceRule(old="txt", new="md", include_extension=True)
    )
    assert (stem, ext) == ("a", "md")


def test_replace_empty_old_is_noop() -> None:
    stem, ext = apply_replace("a", "txt", ReplaceRule(old="", new="x"))
    assert (stem, ext) == ("a", "txt")


def test_regex_numbered_group() -> None:
    stem, _ = apply_replace(
        "IMG_001", "JPG",
        ReplaceRule(old=r"IMG_(\d+)", new="照片_$1", use_regex=True),
    )
    assert stem == "照片_001"


def test_regex_named_group() -> None:
    stem, _ = apply_replace(
        "IMG_123", "JPG",
        ReplaceRule(old=r"IMG_(?P<num>\d+)", new="No${num}", use_regex=True),
    )
    assert stem == "No123"


def test_regex_backslash_group_reference() -> None:
    stem, _ = apply_replace(
        "123", "JPG", ReplaceRule(old=r"(\d+)", new=r"\1号", use_regex=True)
    )
    assert stem == "123号"


def test_regex_whole_match_reference() -> None:
    stem, _ = apply_replace(
        "abc", "txt", ReplaceRule(old=r"b", new="[$0]", use_regex=True)
    )
    assert stem == "a[b]c"


def test_regex_dollar_escape() -> None:
    stem, _ = apply_replace(
        "a", "txt", ReplaceRule(old="a", new="$$", use_regex=True)
    )
    assert stem == "$"


def test_regex_case_insensitive() -> None:
    stem, _ = apply_replace(
        "ABCabc", "txt",
        ReplaceRule(old="abc", new="X", use_regex=True, case_sensitive=False),
    )
    assert stem == "XX"


def test_regex_invalid_pattern_raises() -> None:
    with pytest.raises(RuleError, match="正则表达式无效"):
        apply_replace("a", "txt", ReplaceRule(old="(", new="x", use_regex=True))


def test_regex_invalid_group_raises() -> None:
    with pytest.raises(RuleError, match="正则替换失败"):
        apply_replace("a", "txt", ReplaceRule(old="(a)", new="$9", use_regex=True))


# ---------------------------------------------------------------------------
# 编号
# ---------------------------------------------------------------------------
def test_numeric_counter_with_padding() -> None:
    rule = OverallRule(start=1, step=1, digits=3, pad=True)
    assert format_counter(1, rule) == "001"
    assert format_counter(20, rule) == "020"


def test_numeric_counter_without_padding() -> None:
    rule = OverallRule(digits=3, pad=False)
    assert format_counter(7, rule) == "7"


def test_numeric_counter_negative() -> None:
    rule = OverallRule(digits=3, pad=True)
    assert format_counter(-2, rule) == "-02"


def test_letter_counter_sequence() -> None:
    assert to_letters(1) == "A"
    assert to_letters(26) == "Z"
    assert to_letters(27) == "AA"
    assert to_letters(52) == "AZ"
    assert to_letters(53) == "BA"


def test_letter_counter_case_and_padding() -> None:
    lower = OverallRule(letter_mode=True, letter_case="lower", digits=3, pad=True)
    assert format_counter(1, lower) == "aaa"
    upper = OverallRule(letter_mode=True, letter_case="upper", digits=1, pad=False)
    assert format_counter(28, upper) == "AB"


def test_letter_counter_requires_positive_start() -> None:
    rule = OverallRule(letter_mode=True, start=0)
    with pytest.raises(RuleError, match="字母编号"):
        format_counter(0, rule)


# ---------------------------------------------------------------------------
# 命名规则模板
# ---------------------------------------------------------------------------
def test_empty_template_keeps_stem() -> None:
    rules = RuleSet(overall=OverallRule(template=""))
    assert build_full_target("a.txt", rules, 0) == "a.txt"


def test_star_inserts_current_stem() -> None:
    rules = RuleSet(overall=OverallRule(template="A_*"))
    assert build_full_target("photo.jpg", rules, 0) == "A_photo.jpg"


def test_template_without_star_replaces_stem() -> None:
    rules = RuleSet(overall=OverallRule(template="new"))
    assert build_full_target("photo.jpg", rules, 0) == "new.jpg"


def test_counter_uses_index_start_and_step() -> None:
    rules = RuleSet(overall=OverallRule(template="A_#", start=10, step=5, digits=2))
    assert build_full_target("x.txt", rules, 0) == "A_10.txt"
    assert build_full_target("x.txt", rules, 2) == "A_20.txt"


def test_multiple_hashes_share_counter() -> None:
    rules = RuleSet(overall=OverallRule(template="#-#", digits=2, pad=True))
    assert build_full_target("x.txt", rules, 0) == "01-01.txt"


def test_template_escapes() -> None:
    rules = RuleSet(overall=OverallRule(template=r"\#\*\{x\}"))
    assert build_full_target("a.txt", rules, 0) == "#*{x}.txt"


def test_unclosed_brace_is_literal() -> None:
    rules = RuleSet(overall=OverallRule(template="a{b"))
    assert build_full_target("x.txt", rules, 0) == "a{b.txt"


def test_placeholders_with_metadata() -> None:
    metadata = {
        "date": datetime(2026, 11, 21, 21, 40, 5),
        "camera": "D850",
        "size": 1234,
    }
    rules = RuleSet(overall=OverallRule(template="{date:%Y%m%d}_{camera}_{size:05d}"))
    assert build_full_target("a.jpg", rules, 0, metadata) == "20261121_D850_01234.jpg"


def test_default_datetime_placeholder_format() -> None:
    metadata = {"date": datetime(2026, 11, 21, 21, 40, 5)}
    rules = RuleSet(overall=OverallRule(template="{date}"))
    assert build_full_target("a.jpg", rules, 0, metadata) == "2026-11-21_214005.jpg"


def test_date_placeholder() -> None:
    metadata = {"date": date(2026, 11, 21)}
    rules = RuleSet(overall=OverallRule(template="{date}"))
    assert build_full_target("a.jpg", rules, 0, metadata) == "2026-11-21.jpg"


def test_name_ext_and_n_placeholders() -> None:
    rules = RuleSet(overall=OverallRule(template="{name}_{n}.{ext}", digits=2, pad=True))
    assert build_full_target("photo.JPG", rules, 0) == "photo_01.JPG"


def test_ext_placeholder_in_middle_is_not_deduplicated() -> None:
    rules = RuleSet(overall=OverallRule(template="{ext}_{name}"))
    assert build_full_target("photo.JPG", rules, 0) == "JPG_photo.JPG"


def test_ext_placeholder_dedup_with_extension_change() -> None:
    rules = RuleSet(
        overall=OverallRule(
            template="{name}.{ext}", change_extension=True, new_extension="png"
        )
    )
    assert build_full_target("photo.JPG", rules, 0) == "photo.png"


def test_missing_placeholder_becomes_empty() -> None:
    rules = RuleSet(overall=OverallRule(template="a{missing}b"))
    assert build_full_target("x.txt", rules, 0) == "ab.txt"


# ---------------------------------------------------------------------------
# 大小写与扩展名
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("option", "expected"),
    [
        ("none", ("AbC", "TxT")),
        ("stem_lower", ("abc", "TxT")),
        ("ext_lower", ("AbC", "txt")),
        ("both_lower", ("abc", "txt")),
        ("stem_upper", ("ABC", "TxT")),
        ("ext_upper", ("AbC", "TXT")),
        ("both_upper", ("ABC", "TXT")),
    ],
)
def test_case_options(option: str, expected: tuple[str, str]) -> None:
    assert apply_case("AbC", "TxT", option) == expected


def test_change_extension() -> None:
    rules = RuleSet(overall=OverallRule(change_extension=True, new_extension=".MP4"))
    assert build_full_target("a.mkv", rules, 0) == "a.MP4"


def test_empty_new_extension_keeps_original() -> None:
    rules = RuleSet(overall=OverallRule(change_extension=True, new_extension="   "))
    assert build_full_target("a.mkv", rules, 0) == "a.mkv"


def test_extension_change_then_case() -> None:
    rules = RuleSet(
        overall=OverallRule(
            change_extension=True, new_extension=".MP4", case_option="both_lower"
        )
    )
    assert build_full_target("A.MKV", rules, 0) == "a.mp4"


# ---------------------------------------------------------------------------
# 完整流水线
# ---------------------------------------------------------------------------
def test_full_pipeline_order() -> None:
    rules = RuleSet(
        add_remove=AddRemoveRule(prefix="P_"),
        replace=ReplaceRule(old="IMG", new="PIC"),
        overall=OverallRule(
            template="X_*", change_extension=True, new_extension="png",
            case_option="both_lower",
        ),
    )
    stem, ext = build_target_name("IMG_001.JPG", rules, 0)
    assert (stem, ext) == ("x_p_pic_001", "png")


# ---------------------------------------------------------------------------
# 批量规划与冲突
# ---------------------------------------------------------------------------
def test_plan_unchanged() -> None:
    plans = plan_batch(["a.txt", "b.txt"], RuleSet())
    assert [plan.target for plan in plans] == ["a.txt", "b.txt"]
    assert all(plan.unchanged and plan.ok for plan in plans)


def test_plan_duplicate_targets_auto_resolved() -> None:
    rules = RuleSet(overall=OverallRule(template="same"))
    plans = plan_batch(["1.txt", "2.txt"], rules)
    assert plans[0].target == "same.txt"
    assert plans[1].target == "same (1).txt"
    assert plans[1].conflict_resolved is True
    assert all(plan.ok for plan in plans)


def test_plan_duplicate_targets_without_auto_resolve() -> None:
    rules = RuleSet(overall=OverallRule(template="same", auto_resolve=False))
    plans = plan_batch(["1.txt", "2.txt"], rules)
    assert plans[0].ok
    assert plans[1].error == "目标名称已存在"


def test_plan_conflict_with_existing_file() -> None:
    rules = RuleSet(overall=OverallRule(template="b"))
    plans = plan_batch(["a.txt"], rules, taken_names={"a.txt", "b.txt"})
    assert plans[0].target == "b (1).txt"
    assert plans[0].conflict_resolved is True


def test_plan_case_only_rename_is_not_conflict() -> None:
    rules = RuleSet(overall=OverallRule(case_option="stem_upper"))
    plans = plan_batch(["a.txt"], rules, taken_names={"a.txt"})
    assert plans[0].ok
    assert plans[0].target == "A.txt"
    assert plans[0].unchanged is False


def test_plan_invalid_target_reports_error() -> None:
    rules = RuleSet(overall=OverallRule(template="bad|name"))
    plans = plan_batch(["a.txt"], rules)
    assert plans[0].error is not None
    assert "非法字符" in plans[0].error


def test_plan_regex_error_reports_error() -> None:
    rules = RuleSet(replace=ReplaceRule(old="(", new="x", use_regex=True))
    plans = plan_batch(["a.txt"], rules)
    assert plans[0].error is not None
    assert "正则表达式无效" in plans[0].error


def test_plan_metadata_length_must_match() -> None:
    with pytest.raises(ValueError):
        plan_batch(["a.txt"], RuleSet(), metadata=[{}, {}])


def test_plan_uses_metadata_per_row() -> None:
    rules = RuleSet(overall=OverallRule(template="{date}"))
    metadata = [
        {"date": "2026-01-01"},
        {"date": "2026-02-02"},
    ]
    plans = plan_batch(["a.jpg", "b.jpg"], rules, metadata=metadata)
    assert [plan.target for plan in plans] == ["2026-01-01.jpg", "2026-02-02.jpg"]


def test_plan_accepts_global_indexes() -> None:
    rules = RuleSet(overall=OverallRule(template="文件_#"))
    plans = plan_batch(["b.txt"], rules, indexes=[4])
    assert plans[0].target == "文件_5.txt"


def test_plan_indexes_length_must_match() -> None:
    with pytest.raises(ValueError):
        plan_batch(["a.txt"], RuleSet(), indexes=[0, 1])
