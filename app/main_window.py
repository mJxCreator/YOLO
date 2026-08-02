from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .annotate_page import AnnotatePage
from .appconfig import AppConfig
from .config import APP_NAME, GITHUB_URL
from .detect_page import DetectPage
from .project import Project
from .train_page import TrainPage


class MainWindow(QMainWindow):
    home_requested = Signal()
    open_project_requested = Signal(str)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.project = None
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)

        self._build_menu()
        self._build_sidebar()
        self._build_central()
        self._build_statusbar()

        for p in (self.annotate_page, self.train_page, self.detect_page):
            p.status_message.connect(self.statusBar().showMessage)

    def init_project(self, project):
        """窗口显示后再绑定项目数据，避免启动卡顿"""
        self.project = project
        self.setWindowTitle(f"{APP_NAME} - {project.root.name}")
        self.lbl_project.setText(f"项目: {project.root}")
        self.annotate_page.set_project(project)
        self.annotate_page.set_config(self.config)
        self.train_page.set_project(project)
        self.detect_page.set_project(project)
        self.train_page.set_config(self.config)

    def on_device_ready(self, device):
        """应用启动时的 GPU 检测结果返回后，通知训练页"""
        self.train_page._on_device_detected(device)

    # ---------- 菜单栏 ----------
    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        act_open = QAction("打开其他项目", self)
        act_open.triggered.connect(self.open_other_project)
        file_menu.addAction(act_open)
        act_export = QAction("导出模型 (ONNX/TensorRT)", self)
        act_export.triggered.connect(self.export_model)
        file_menu.addAction(act_export)
        act_export_label = QAction("导出标注数据", self)
        act_export_label.triggered.connect(self.export_labels)
        file_menu.addAction(act_export_label)
        file_menu.addSeparator()
        self.act_auto_save = QAction("自动保存", self)
        self.act_auto_save.setCheckable(True)
        self.act_auto_save.setChecked(self.config.get_auto_save())
        self.act_auto_save.setStatusTip("开启后，切换图片时自动保存上一张图片的标注")
        self.act_auto_save.toggled.connect(self.on_auto_save_toggled)
        file_menu.addAction(self.act_auto_save)

        edit_menu = menubar.addMenu("编辑(&E)")
        act_settings = QAction("个性化设置", self)
        act_settings.triggered.connect(self.show_settings)
        edit_menu.addAction(act_settings)

        help_menu = menubar.addMenu("帮助(&H)")
        act_github = QAction("进入 GitHub", self)
        act_github.triggered.connect(self.open_github)
        help_menu.addAction(act_github)

    # ---------- 侧边栏 ----------
    def _build_sidebar(self):
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(170)
        self.sidebar.setStyleSheet(
            "QWidget { background: #23272f; }"
            "QPushButton { text-align: left; padding: 10px 14px; border: none; color: #ccc; font-size: 14px; }"
            "QPushButton:hover { background: #2f3542; }"
            "QPushButton:checked { background: #2d8cf0; color: white; }"
        )
        sb = QVBoxLayout(self.sidebar)
        sb.setContentsMargins(8, 12, 8, 12)
        sb.setSpacing(4)

        self.btn_annotate = QPushButton("标注")
        self.btn_train = QPushButton("训练")
        self.btn_detect = QPushButton("检测")
        self.btn_annotate.setCheckable(True)
        self.btn_train.setCheckable(True)
        self.btn_detect.setCheckable(True)
        self.btn_annotate.setChecked(True)
        self.btn_annotate.clicked.connect(lambda: self.switch_page(0))
        self.btn_train.clicked.connect(lambda: self.switch_page(1))
        self.btn_detect.clicked.connect(lambda: self.switch_page(2))
        sb.addWidget(self.btn_annotate)
        sb.addWidget(self.btn_train)
        sb.addWidget(self.btn_detect)
        sb.addStretch(1)

        self.sidebar_container = QWidget()
        lay = QHBoxLayout(self.sidebar_container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.sidebar)
        lay.setSpacing(0)
        self.sidebar_container.setVisible(True)

    def _build_central(self):
        self.pages = QStackedWidget()
        self.annotate_page = AnnotatePage()
        self.train_page = TrainPage()
        self.detect_page = DetectPage()
        self.pages.addWidget(self.annotate_page)
        self.pages.addWidget(self.train_page)
        self.pages.addWidget(self.detect_page)

        # 菜单栏 [三] 按钮控制侧边栏
        self.toolbar = self.addToolBar("侧边栏")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(self.toolbar.iconSize() * 1)
        btn_menu = QToolButton()
        btn_menu.setText("☰")
        btn_menu.setCheckable(True)
        btn_menu.setChecked(True)
        btn_menu.toggled.connect(lambda on: self.sidebar_container.setVisible(on))
        self.toolbar.addWidget(btn_menu)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar_container)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)

    def _build_statusbar(self):
        bar = QStatusBar()
        self.setStatusBar(bar)
        self.lbl_project = QLabel("项目: 未打开")
        bar.addWidget(self.lbl_project, 1)

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)
        self.btn_annotate.setChecked(index == 0)
        self.btn_train.setChecked(index == 1)
        self.btn_detect.setChecked(index == 2)

    # ---------- 菜单功能 ----------
    def on_auto_save_toggled(self, enabled):
        """自动保存开关状态变更"""
        self.config.set_auto_save(enabled)
        self.annotate_page.set_auto_save(enabled)
        self.statusBar().showMessage(
            "已开启自动保存：切换图片时自动保存标注" if enabled else "已关闭自动保存"
        )

    def open_other_project(self):
        path = QFileDialog.getExistingDirectory(self, "选择项目文件夹")
        if path:
            self.config.add_recent_project(path)
            self.open_project_requested.emit(path)

    def export_model(self):
        if self.project is None:
            return
        trained = self.project.get_trained_models()
        if not trained:
            QMessageBox.information(self, "提示", "尚未训练出模型")
            return
        from .export_dialog import ExportDialog
        dlg = ExportDialog(trained[0], self)
        dlg.exec()

    def export_labels(self):
        if self.project is None:
            return
        src = self.project.labels_dir
        dst = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not dst:
            return
        import shutil
        count = 0
        for f in src.iterdir():
            if f.suffix == ".txt":
                shutil.copy2(f, Path(dst) / f.name)
                count += 1
        QMessageBox.information(self, "完成", f"已导出 {count} 个标注文件")

    def show_settings(self):
        QMessageBox.information(self, "个性化设置", "主题、快捷键等设置将在后续版本中提供")

    def open_github(self):
        import webbrowser
        webbrowser.open(GITHUB_URL)

    def closeEvent(self, event):
        event.accept()
