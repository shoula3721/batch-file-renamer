"""路径工具：兼容开发环境与 PyInstaller 单文件/单目录打包。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "批量文件改名"


def resource_path(relative: str) -> Path:
    """返回打包后仍可访问的资源路径。

    onefile 模式下资源被解压到 sys._MEIPASS；
    onedir / 开发模式下相对于项目根目录。
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def app_data_dir() -> Path:
    """用户数据目录：%APPDATA%\\批量文件改名（onefile 每次解压，不能写 exe 旁边）。"""
    root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(root) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_dir() -> Path:
    path = app_data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path
