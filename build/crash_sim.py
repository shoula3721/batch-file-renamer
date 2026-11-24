"""故障注入脚本：改名进行到一半时直接终止进程，用于验证崩溃恢复。

环境变量：
    BFR_FOLDER       测试文件目录
    BFR_BACKUP       备份目录
    BFR_CRASH_AFTER  第 N 次 os.rename 之后强制退出（默认 3）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.engine import BackupStore, RenameExecutor, RenameItem  # noqa: E402
import app.engine.executor as executor_module  # noqa: E402


def main() -> None:
    folder = Path(os.environ["BFR_FOLDER"])
    backups = Path(os.environ["BFR_BACKUP"])
    crash_after = int(os.environ.get("BFR_CRASH_AFTER", "3"))

    folder.mkdir(parents=True, exist_ok=True)
    sources = [f"{index}.txt" for index in range(1, 6)]
    for name in sources:
        (folder / name).write_text(f"content:{name}", encoding="utf-8")

    real_rename = os.rename
    calls = {"count": 0}

    def crash_rename(source, target):
        calls["count"] += 1
        if calls["count"] > crash_after:
            os._exit(9)
        return real_rename(source, target)

    executor_module.os.rename = crash_rename

    items = [
        RenameItem(folder / name, folder / f"new_{index}.txt")
        for index, name in enumerate(sources, start=1)
    ]
    RenameExecutor(BackupStore(backups), retry_delay=0).execute(items)


if __name__ == "__main__":
    main()
