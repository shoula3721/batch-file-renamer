"""安全流程演示：python build/demo_safety.py"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from app.engine import BackupStore, RenameExecutor, RenameItem, undo_last

WORK = Path(__file__).resolve().parent / "demo_work"


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    folder = WORK / "files"
    backups = WORK / "backups"
    folder.mkdir(parents=True)

    sources = [f"{index:02d}.1080P.WEB-DL.mp4" for index in range(1, 6)]
    for name in sources:
        (folder / name).write_text(f"content:{name}", encoding="utf-8")

    items = [
        RenameItem(folder / name, folder / f"视频_{index:03d}.mp4")
        for index, name in enumerate(sources, start=1)
    ]

    result = RenameExecutor(BackupStore(backups)).execute(items)
    print("== 改名完成 ==")
    print(f"成功 {result.success} / 失败 {result.failed} / 未更改 {result.skipped}")
    print(f"备份：{result.backup_path.name}  状态：{result.state}")
    print("目录：", sorted(path.name for path in folder.iterdir()))

    record = json.loads(result.backup_path.read_text(encoding="utf-8"))
    print("\n== 备份内容（首条）==")
    print(json.dumps({k: record[k] for k in ("schema", "state", "kind", "created_at")},
                     ensure_ascii=False, indent=2))
    print(json.dumps(record["items"][0], ensure_ascii=False, indent=2))

    outcome = undo_last(BackupStore(backups))
    print("\n== 撤销完成 ==")
    print(f"还原 {outcome.result.success} 个，完全还原：{outcome.fully_restored}")
    print("目录：", sorted(path.name for path in folder.iterdir()))

    target = folder / sources[0]
    other = folder / "renamed_while_open.mp4"
    handle = open(target, "rb")
    try:
        os.rename(target, other)
        print("\n占用测试：Windows 允许改名打开中的文件")
        os.rename(other, target)
    except OSError as exc:
        print(f"\n占用测试：文件被占用时改名失败（符合预期）-> {exc.__class__.__name__}: {exc}")
    finally:
        handle.close()

    shutil.rmtree(WORK)


if __name__ == "__main__":
    main()
