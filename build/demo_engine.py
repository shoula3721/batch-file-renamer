"""引擎手动演示：python build/demo_engine.py"""
from __future__ import annotations

from app.engine import OverallRule, RuleSet, plan_batch


def main() -> None:
    files = [f"{index:02d}.1080P.WEB-DL.mp4" for index in range(1, 6)]
    rules = RuleSet(
        overall=OverallRule(
            template="视频_#",
            start=1,
            digits=3,
            pad=True,
            change_extension=True,
            new_extension="mp4",
        )
    )
    existing = set(files) | {"视频_001.mp4"}
    print(f"{'原文件名':<26} {'预览':<20} 结果")
    print("-" * 58)
    for plan in plan_batch(files, rules, taken_names=existing):
        result = "成功" if plan.ok else f"失败：{plan.error}"
        print(f"{plan.source:<26} {plan.target:<20} {result}")


if __name__ == "__main__":
    main()
