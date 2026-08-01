from pathlib import Path
import time

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .appconfig import AppConfig
from .config import APP_NAME, GITHUB_URL
from .project import Project


class HomeWindow(QWidget):
    """启动界面：历史项目 / 新建项目 / 打开项目"""

    project_opened = Signal(object)   # Project

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._last_open_time = 0.0
        self.setWindowTitle(APP_NAME)
        self.resize(900, 560)
        self._build_ui()
        self.refresh_recent()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # 标题
        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold; padding: 24px; color: #2d8cf0;")
        root.addWidget(title)

        body = QHBoxLayout()
        body.setContentsMargins(40, 8, 40, 24)
        body.setSpacing(24)

        # 左：历史项目
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel("历史项目"))
        self.recent_list = QListWidget()
        self.recent_list.itemClicked.connect(self._open_recent)
        self.recent_list.itemDoubleClicked.connect(self._open_recent)
        lv.addWidget(self.recent_list, 1)
        body.addWidget(left, 3)

        # 右：操作按钮
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setSpacing(12)
        rv.addStretch(1)

        self.btn_new = QPushButton("新建项目")
        self.btn_new.setStyleSheet(
            "QPushButton { background: #2d8cf0; color: white; padding: 12px; font-size: 15px; border-radius: 6px; }"
            "QPushButton:hover { background: #1f73c7; }"
        )
        self.btn_new.clicked.connect(self.new_project)
        rv.addWidget(self.btn_new)

        self.btn_open = QPushButton("打开项目")
        self.btn_open.setStyleSheet(
            "QPushButton { background: #f0f0f0; padding: 12px; font-size: 15px; border-radius: 6px; }"
            "QPushButton:hover { background: #dcdcdc; }"
        )
        self.btn_open.clicked.connect(self.open_project)
        rv.addWidget(self.btn_open)

        self.btn_github = QPushButton("GitHub 仓库")
        self.btn_github.setFlat(True)
        self.btn_github.clicked.connect(self.open_github)
        rv.addWidget(self.btn_github)

        rv.addStretch(2)
        body.addWidget(right, 2)

        root.addLayout(body, 1)

    # ---------- 历史项目 ----------
    def refresh_recent(self):
        self.recent_list.clear()
        for path in self.config.get_recent_projects():
            item = QListWidgetItem(path)
            item.setToolTip(path)
            self.recent_list.addItem(item)

    def _open_recent(self, item):
        path = item.text()
        self._open_project(Path(path))

    # ---------- 新建 / 打开 ----------
    def new_project(self):
        base = QFileDialog.getExistingDirectory(self, "选择项目存放位置")
        if not base:
            return
        name, ok = QInputDialog.getText(self, "新建项目", "项目名称:", text="defect_project")
        if not ok or not name.strip():
            return
        name = name.strip()
        root = Path(base) / name
        if root.exists():
            QMessageBox.warning(self, "提示", f"项目 {name} 已存在")
            return
        project = Project.create(root)
        self.config.add_recent_project(root)
        self.project_opened.emit(project)

    def open_project(self):
        path = QFileDialog.getExistingDirectory(self, "选择项目文件夹")
        if not path:
            return
        self._open_project(Path(path))

    def _open_project(self, root: Path):
        # 防抖：单击+双击会连续触发，500ms 内忽略重复打开
        now = time.time()
        if now - self._last_open_time < 0.5:
            return
        self._last_open_time = now
        try:
            project = Project.open(root)
            self.config.add_recent_project(root)
            self.project_opened.emit(project)
        except Exception as e:
            QMessageBox.critical(self, "打开项目失败", str(e))

    def open_github(self):
        QDesktopServices.openUrl(QUrl(GITHUB_URL))
