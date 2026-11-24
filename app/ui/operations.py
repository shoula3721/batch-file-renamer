"""后台任务线程：把改名 / 撤销 / 还原放到工作线程执行。"""
from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QThread, Signal

ProgressFn = Callable[[int, int, str], None]
CancelFn = Callable[[], bool]
TaskFn = Callable[[ProgressFn, CancelFn], object]


class TaskWorker(QThread):
    """执行一个可取消任务，结果和异常通过信号回到主线程。"""

    progress = Signal(int, int, str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, task: TaskFn, parent=None) -> None:
        super().__init__(parent)
        self._task = task
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self) -> None:  # noqa: D401 - QThread 入口
        try:
            result = self._task(self._emit_progress, self._cancelled.is_set)
        except Exception as exc:  # noqa: BLE001 - 由主线程统一提示
            self.failed.emit(str(exc))
            return
        self.completed.emit(result)

    def _emit_progress(self, done: int, total: int, message: str) -> None:
        self.progress.emit(done, total, message)
