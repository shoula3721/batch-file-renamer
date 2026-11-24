"""一键构建：单文件 exe、单目录、以及单目录压缩包。

用法（必须使用项目虚拟环境）：
    .venv\\Scripts\\python.exe build\\build.py --target all
    .venv\\Scripts\\python.exe build\\build.py --target onefile
    .venv\\Scripts\\python.exe build\\build.py --target onedir
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "批量文件改名"
ICON = ROOT / "app" / "resources" / "app.ico"
VERSION_FILE = ROOT / "build" / "version_info.txt"
DIST = ROOT / "dist"
WORK = ROOT / "build" / "work"
SPEC = ROOT / "build" / "spec"


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def dir_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def run_pyinstaller(onedir: bool) -> None:
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(ICON),
        "--add-data",
        f"{ROOT / 'app' / 'resources'};app/resources",
        "--collect-submodules",
        "mutagen",
        "--version-file",
        str(VERSION_FILE),
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK),
        "--specpath",
        str(SPEC),
        "--onedir" if onedir else "--onefile",
        str(ROOT / "main.py"),
    ]
    mode = "单目录" if onedir else "单文件"
    print(f"\n=== 构建{mode}版本 ===")
    started = time.perf_counter()
    subprocess.run(args, cwd=ROOT, check=True)
    print(f"=== 构建完成，用时 {time.perf_counter() - started:.1f}s ===")


def make_zip(folder: Path, zip_path: Path) -> None:
    print(f"\n=== 压缩 {folder.name} ===")
    if zip_path.exists():
        zip_path.unlink()
    started = time.perf_counter()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in sorted(folder.rglob("*")):
            if item.is_file():
                archive.write(item, Path(APP_NAME) / item.relative_to(folder))
    print(f"=== 压缩完成，用时 {time.perf_counter() - started:.1f}s ===")


def verify_onefile() -> None:
    exe = DIST / f"{APP_NAME}.exe"
    if not exe.exists():
        raise SystemExit(f"未找到产物：{exe}")
    print(f"产物：{exe}  ({human_size(exe.stat().st_size)})")


def verify_onedir() -> None:
    folder = DIST / APP_NAME
    exe = folder / f"{APP_NAME}.exe"
    if not exe.exists():
        raise SystemExit(f"未找到产物：{exe}")
    print(f"产物：{exe}  (目录 {human_size(dir_size(folder))})")


def main() -> int:
    parser = argparse.ArgumentParser(description="批量文件改名 - 构建脚本")
    parser.add_argument(
        "--target",
        choices=("onefile", "onedir", "all"),
        default="all",
        help="构建目标，默认 all",
    )
    parser.add_argument("--skip-zip", action="store_true", help="单目录版本不生成 zip")
    options = parser.parse_args()

    if not ICON.exists():
        raise SystemExit(f"图标不存在：{ICON}")
    if not VERSION_FILE.exists():
        raise SystemExit(f"版本信息不存在：{VERSION_FILE}")

    DIST.mkdir(parents=True, exist_ok=True)

    if options.target in ("onefile", "all"):
        run_pyinstaller(onedir=False)
        verify_onefile()

    if options.target in ("onedir", "all"):
        run_pyinstaller(onedir=True)
        verify_onedir()
        if not options.skip_zip:
            zip_path = DIST / f"{APP_NAME}.zip"
            make_zip(DIST / APP_NAME, zip_path)
            print(f"产物：{zip_path}  ({human_size(zip_path.stat().st_size)})")

    print("\n全部完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
