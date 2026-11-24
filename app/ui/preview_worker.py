"""后台预览线程：读取拍摄时间并生成预览，避免大列表卡住界面。"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QThread, Signal

from app.engine.metadata import CaptureCache
from app.engine.rules import RuleSet
from app.ui.preview import (
    PreviewCancelled,
    PreviewInfo,
    build_previews,
    load_captures,
)


class PreviewWorker(QThread):
    """常驻工作线程，只处理最近一次请求；旧结果由主线程按 generation 丢弃。"""

    ready = Signal(int, object)  # generation, list[PreviewInfo]
    progress = Signal(int, int)  # done, total
    failed = Signal(int, str)  # generation, message

    def __init__(self, cache: CaptureCache, parent=None) -> None:
        super().__init__(parent)
        self._cache = cache
        self._condition = threading.Condition()
        self._request: tuple[int, list[Path], RuleSet] | None = None
        self._stopped = False
        self._last_progress = 0.0

    # ------------------------------------------------------------------
    # 主线程接口
    # ------------------------------------------------------------------
    def submit(self, generation: int, paths: Sequence[Path], rules: RuleSet) -> None:
        with self._condition:
            self._request = (generation, list(paths), rules)
            self._condition.notify()

    def stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._request = None
            self._condition.notify()
        if not self.wait(5000):
            self.terminate()
            self.wait(1000)

    # ------------------------------------------------------------------
    # 线程体
    # ------------------------------------------------------------------
    def run(self) -> None:  # noqa: D401 - Qt 线程入口
        while True:
            with self._condition:
                while self._request is None and not self._stopped:
                    self._condition.wait()
                if self._stopped:
                    return
                generation, paths, rules = self._request
                self._request = None
            try:
                captures = load_captures(
                    paths,
                    self._cache,
                    progress=self._on_progress,
                    should_stop=self._is_stopped,
                )
                infos: list[PreviewInfo] = build_previews(
                    paths,
                    rules,
                    captures=captures,
                    cache=self._cache,
                    should_stop=self._is_stopped,
                )
            except PreviewCancelled:
                continue
            except Exception as exc:  # noqa: BLE001 - 预览失败不应终止线程
                self.failed.emit(generation, str(exc))
                continue
            with self._condition:
                if self._stopped:
                    return
                stale = self._request is not None
            if stale:
                continue
            self.ready.emit(generation, infos)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _is_stopped(self) -> bool:
        with self._condition:
            return self._stopped

    def _on_progress(self, done: int, total: int) -> None:
        if not total:
            return
        now = time.monotonic()
        if done < total and now - self._last_progress < 0.1:
            return
        self._last_progress = now
        self.progress.emit(done, total)
