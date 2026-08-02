import multiprocessing
import os
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("YOLO_OFFLINE", "1")

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

from app.appconfig import AppConfig
from app.home_window import HomeWindow
from app.main_window import MainWindow
from app.project import Project


class DeviceDetectThread(QThread):
    """应用启动时后台检测一次 GPU，结果缓存到配置，避免每次进项目重复 import torch"""

    result = Signal(str)

    def run(self):
        try:
            import torch
            if torch.cuda.is_available():
                self.result.emit("cuda:0")
            else:
                self.result.emit("cpu")
        except Exception:
            self.result.emit("cpu")


class Application:
    def __init__(self):
        self.config = AppConfig()
        self.home = HomeWindow(self.config)
        self.main = None
        self._device_thread = None

        self.home.project_opened.connect(self.open_main)
        self.home.show()

        self._start_device_detect()

    def _start_device_detect(self):
        self._device_thread = DeviceDetectThread()
        self._device_thread.result.connect(self._on_device_detected)
        self._device_thread.start()

    def _on_device_detected(self, device):
        self.config.data.setdefault("settings", {})["device"] = device
        self.config.save()
        if self.main is not None:
            self.main.on_device_ready(device)

    def shutdown_threads(self):
        """应用退出前等待后台线程结束，避免 QThread 在运行中被销毁导致崩溃"""
        t = self._device_thread
        if t is not None and t.isRunning():
            t.wait()

    def open_main(self, project):
        # 防重入：已有主窗口则先清理，避免双击产生多个窗口
        if self.main is not None:
            self.main.close()
            self.main.deleteLater()
            self.main = None

        self.main = MainWindow(self.config)
        self.main.home_requested.connect(self.back_home)
        self.main.open_project_requested.connect(self.switch_project)
        self.home.hide()
        self.main.show()
        self.main.init_project(project)

    def switch_project(self, path):
        """文件菜单中「打开其他项目」：直接切换到新项目，不经过首页"""
        try:
            project = Project.open(path)
        except Exception as e:
            self.main.statusBar().showMessage(f"打开项目失败: {e}")
            return
        self.open_main(project)

    def back_home(self):
        if self.main is not None:
            self.main.close()
            self.main.deleteLater()
            self.main = None
        self.home.refresh_recent()
        self.home.show()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("YOLO26 缺陷检测一体化平台")
    window = Application()
    app.aboutToQuit.connect(window.shutdown_threads)
    sys.exit(app.exec())


if __name__ == "__main__":
    # 打包版必需：让 PyTorch DataLoader 的多进程工作子进程正确退出，
    # 否则子进程会重新启动整个 GUI 导致训练挂起、关窗时 Qt 崩溃 (0xc0000409)
    multiprocessing.freeze_support()
    main()
