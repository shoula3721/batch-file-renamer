"""批量文件改名 — 程序入口。

v37.21.beta3：规则编辑、媒体标签、后台预览、安全改名、撤销 / 一键还原、方案与多语言。
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.paths import resource_path

APP_NAME = "批量文件改名"
APP_VERSION = "37.21.beta3"


def _install_auto_quit(app: QApplication, window: MainWindow) -> None:
    """用于打包冒烟测试：--smoke-test 启动后自动退出；--screenshot 另存界面截图。"""
    argv = sys.argv
    if "--screenshot" in argv:
        index = argv.index("--screenshot")
        if index + 1 < len(argv):
            target = argv[index + 1]

            def capture() -> None:
                window.grab().save(target)
                window.close()
                app.quit()

            QTimer.singleShot(1500, capture)
            return
    if "--smoke-test" in argv:
        def finish() -> None:
            window.close()
            app.quit()

        QTimer.singleShot(1200, finish)


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setWindowIcon(QIcon(str(resource_path("app/resources/app.ico"))))

    window = MainWindow()
    window.show()
    _install_auto_quit(app, window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
