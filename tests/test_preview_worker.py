"""后台预览线程测试。"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from app.engine.metadata import CaptureCache
from app.engine.rules import OverallRule, RuleSet
from app.ui.preview_worker import PreviewWorker
from media_helpers import write_jpeg


@pytest.fixture(scope="module", autouse=True)
def qt_core_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def _wait_for_result(worker: PreviewWorker, timeout_ms: int = 5000) -> dict[str, object]:
    loop = QEventLoop()
    outcome: dict[str, object] = {}

    def on_ready(generation: int, infos: object) -> None:
        outcome["generation"] = generation
        outcome["infos"] = infos
        loop.quit()

    def on_failed(generation: int, message: str) -> None:
        outcome["generation"] = generation
        outcome["error"] = message
        loop.quit()

    worker.ready.connect(on_ready)
    worker.failed.connect(on_failed)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    worker.ready.disconnect(on_ready)
    worker.failed.disconnect(on_failed)
    return outcome


def test_worker_generates_previews_in_background(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "photos" / "IMG_0001.JPG")
    worker = PreviewWorker(CaptureCache())
    worker.start()
    try:
        worker.submit(
            7, [photo], RuleSet(overall=OverallRule(template="{date}_*"))
        )
        outcome = _wait_for_result(worker)
    finally:
        worker.stop()

    assert "error" not in outcome
    assert outcome["generation"] == 7
    infos = outcome["infos"]
    assert isinstance(infos, list) and len(infos) == 1
    assert infos[0].target_name == "2026-11-21_IMG_0001.JPG"
    assert infos[0].taken_source == "EXIF 拍摄时间"


def test_worker_reports_empty_result_for_no_files(tmp_path: Path) -> None:
    worker = PreviewWorker(CaptureCache())
    worker.start()
    try:
        worker.submit(1, [], RuleSet())
        outcome = _wait_for_result(worker)
    finally:
        worker.stop()

    assert outcome["infos"] == []
