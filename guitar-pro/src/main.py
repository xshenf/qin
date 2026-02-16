"""
Guitar Pro — 专业吉他练习应用入口

启动 PySide6 GUI 应用。
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def main():
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Guitar Pro")
    app.setOrganizationName("Qin")

    # 延迟导入避免循环依赖
    from src.ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
