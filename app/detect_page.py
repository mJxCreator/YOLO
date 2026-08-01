import time
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .config import VIDEO_EXTS


def ndarray_to_pixmap(arr):
    if arr is None:
        return None
    h, w, ch = arr.shape
    if ch == 3:
        img = QImage(arr.data, w, h, 3 * w, QImage.Format_RGB888).rgbSwapped()
    else:
        img = QImage(arr.data, w, h, ch * w, QImage.Format_Grayscale8)
    return QPixmap.fromImage(img)


class DetectWorker(QThread):
    frame_ready = Signal(object)        # ndarray 标注帧
    progress = Signal(int, int)         # 当前, 总数
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, model_path, mode, source, params, parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.mode = mode
        self.source = source
        self.params = params
        self._stop = False
        self._cap = None
        self._writer = None

    def run(self):
        try:
            from ultralytics import YOLO
            model = YOLO(self.model_path)
            conf = self.params["conf"]
            iou = self.params["iou"]
            imgsz = self.params["imgsz"]
            device = self.params["device"]

            if self.mode == "camera":
                self._run_camera(model, conf, iou, imgsz, device)
            elif self.mode == "video":
                self._run_video(model, conf, iou, imgsz, device)
            else:
                self._run_images(model, conf, iou, imgsz, device)
        except Exception as e:
            import traceback
            self.failed.emit(f"{e}\n{traceback.format_exc()}")

    def _predict_frame(self, model, frame, conf, iou, imgsz, device):
        results = model.predict(frame, conf=conf, iou=iou, imgsz=imgsz, device=device, verbose=False)
        return results[0].plot()

    def _run_camera(self, model, conf, iou, imgsz, device):
        import cv2
        cap = cv2.VideoCapture(int(self.source))
        if not cap.isOpened():
            self.failed.emit("无法打开摄像头")
            return
        while not self._stop:
            ret, frame = cap.read()
            if not ret:
                break
            annotated = self._predict_frame(model, frame, conf, iou, imgsz, device)
            self.frame_ready.emit(annotated)
            if self._stop:
                break
        cap.release()
        if self._stop:
            self.finished_ok.emit("摄像头检测已停止")
        else:
            self.finished_ok.emit("摄像头检测结束")

    def _run_video(self, model, conf, iou, imgsz, device):
        import cv2
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.failed.emit("无法打开视频文件")
            return
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        out_dir = Path(self.params["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(out_dir / f"detect_{int(time.time())}.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

        idx = 0
        while not self._stop:
            ret, frame = cap.read()
            if not ret:
                break
            annotated = self._predict_frame(model, frame, conf, iou, imgsz, device)
            writer.write(annotated)
            idx += 1
            if idx % 5 == 0 or idx == total:
                self.progress.emit(idx, total)
                self.frame_ready.emit(annotated)
        cap.release()
        writer.release()
        if self._stop:
            self.finished_ok.emit(f"视频检测已停止，部分结果保存在: {out_path}")
        else:
            self.finished_ok.emit(f"视频检测完成: {out_path}")

    def _run_images(self, model, conf, iou, imgsz, device):
        out_dir = str(Path(self.params["out_dir"]))
        results = model.predict(
            source=self.source,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            device=device,
            save=True,
            project=out_dir,
            name="results",
            exist_ok=True,
            verbose=False,
        )
        self.finished_ok.emit(f"共检测 {len(results)} 个目标文件")

    def stop(self):
        self._stop = True


class DetectPage(QWidget):
    """检测界面：图片/文件夹/视频/摄像头"""

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.worker = None
        self.result_files = []
        self.result_index = -1
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ---- 配置区 ----
        cfg = QGroupBox("检测配置")
        row1 = QHBoxLayout()

        row1.addWidget(QLabel("模型:"))
        self.combo_model = QComboBox()
        self.combo_model.setMinimumWidth(320)
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh_models)
        row1.addWidget(self.combo_model, 1)
        row1.addWidget(self.btn_refresh)

        row1.addWidget(QLabel("设备:"))
        self.combo_device = QComboBox()
        self.combo_device.addItems(["cpu", "cuda:0"])
        self.combo_device.setCurrentText("cpu")
        row1.addWidget(self.combo_device)

        row1.addWidget(QLabel("置信度:"))
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.01, 0.99)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(0.25)
        row1.addWidget(self.spin_conf)

        row1.addWidget(QLabel("IoU:"))
        self.spin_iou = QDoubleSpinBox()
        self.spin_iou.setRange(0.01, 0.99)
        self.spin_iou.setSingleStep(0.05)
        self.spin_iou.setValue(0.45)
        row1.addWidget(self.spin_iou)
        cfg_layout = QVBoxLayout(cfg)
        cfg_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.radio_image = QRadioButton("图片/文件夹")
        self.radio_video = QRadioButton("视频")
        self.radio_camera = QRadioButton("摄像头")
        self.radio_image.setChecked(True)
        self.radio_image.toggled.connect(lambda: self._sync_source_edit())
        self.radio_video.toggled.connect(lambda: self._sync_source_edit())
        self.radio_camera.toggled.connect(lambda: self._sync_source_edit())
        row2.addWidget(self.radio_image)
        row2.addWidget(self.radio_video)
        row2.addWidget(self.radio_camera)

        self.edit_source = QLineEdit()
        self.edit_source.setPlaceholderText("图片路径 / 文件夹路径 / 视频路径，摄像头请输入 0")
        row2.addWidget(self.edit_source, 1)

        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self.browse_source)
        row2.addWidget(self.btn_browse)
        cfg_layout.addLayout(row2)
        root.addWidget(cfg)

        # ---- 控制区 ----
        ctrl = QHBoxLayout()
        self.btn_detect = QPushButton("开始检测")
        self.btn_detect.setStyleSheet("QPushButton { background: #2d8cf0; color: white; padding: 6px 18px; }")
        self.btn_detect.clicked.connect(self.start_detect)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_detect)
        self.btn_open = QPushButton("打开结果文件夹")
        self.btn_open.clicked.connect(self.open_results)
        ctrl.addWidget(self.btn_detect)
        ctrl.addWidget(self.btn_stop)
        ctrl.addWidget(self.btn_open)
        ctrl.addStretch(1)
        root.addLayout(ctrl)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # ---- 结果区 ----
        splitter = QSplitter(Qt.Horizontal)
        self.preview = QLabel("选择来源后点击开始检测\n检测结果将在此显示")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(400)
        self.preview.setStyleSheet("QLabel { background: #1e1e1e; color: #aaa; }")

        self.result_list = QListWidget()
        self.result_list.setFixedWidth(220)
        self.result_list.currentRowChanged.connect(self._show_result)

        splitter.addWidget(self.preview)
        splitter.addWidget(self.result_list)
        root.addWidget(splitter, 1)

    # ---------- 项目绑定 ----------
    def set_project(self, project):
        self.project = project
        self.refresh_models()

    def refresh_models(self):
        if self.project is None:
            return
        self.combo_model.clear()
        for p in self.project.get_trained_models():
            self.combo_model.addItem(f"[best] {p}", str(p))

    # ---------- 来源 ----------
    def _sync_source_edit(self):
        if self.radio_camera.isChecked():
            self.edit_source.setText("0")
            self.edit_source.setPlaceholderText("摄像头索引，默认 0")
        else:
            self.edit_source.setPlaceholderText("图片路径 / 文件夹路径 / 视频路径")

    def browse_source(self):
        if self.radio_camera.isChecked():
            return
        if self.radio_video.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, "选择视频", "", "视频 (*.mp4 *.avi *.mov *.mkv)")
        else:
            path = QFileDialog.getExistingDirectory(self, "选择图片文件夹") or ""
        if path:
            self.edit_source.setText(path)

    # ---------- 检测 ----------
    def start_detect(self):
        if self.project is None:
            QMessageBox.warning(self, "提示", "请先打开项目")
            return
        model_path = self.combo_model.currentData()
        if not model_path:
            QMessageBox.warning(self, "提示", "请先训练模型或刷新模型列表")
            return
        source = self.edit_source.text().strip()
        if not source:
            QMessageBox.warning(self, "提示", "请输入检测来源")
            return

        if self.radio_image.isChecked():
            mode = "image"
        elif self.radio_video.isChecked():
            mode = "video"
        else:
            mode = "camera"

        params = {
            "conf": self.spin_conf.value(),
            "iou": self.spin_iou.value(),
            "imgsz": 640,
            "device": self.combo_device.currentText(),
            "out_dir": str(self.project.runs_dir / "detect"),
        }

        self.result_list.clear()
        self.result_files = []
        self.result_index = -1
        self.progress.setVisible(mode != "image")
        self.progress.setValue(0)
        self.btn_detect.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_message.emit(f"开始检测: {source}")

        self.worker = DetectWorker(model_path, mode, source, params)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_detect_done)
        self.worker.failed.connect(self._on_detect_failed)
        self.worker.start()

    def stop_detect(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.status_message.emit("正在停止检测...")

    def _on_frame(self, arr):
        pm = ndarray_to_pixmap(arr)
        if pm:
            self.preview.setPixmap(pm.scaled(
                self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_progress(self, cur, total):
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(cur)

    def _load_result_list(self):
        base = Path(self.project.runs_dir) / "detect" / "results"
        if base.exists():
            files = sorted([f for f in base.rglob("*") if f.suffix.lower() in (".jpg", ".png", ".jpeg")])
        else:
            files = []
        self.result_files = files
        self.result_list.clear()
        for f in files:
            self.result_list.addItem(f.name)
        if files:
            self.result_list.setCurrentRow(0)

    def _show_result(self, row):
        if 0 <= row < len(self.result_files):
            pm = QPixmap(str(self.result_files[row]))
            if not pm.isNull():
                self.preview.setPixmap(pm.scaled(
                    self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_detect_done(self, message):
        self.btn_detect.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setVisible(False)
        self._load_result_list()
        self.status_message.emit(message)
        QMessageBox.information(self, "检测完成", message)

    def _on_detect_failed(self, error):
        self.btn_detect.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setVisible(False)
        self.status_message.emit(f"检测失败: {error}")
        QMessageBox.critical(self, "检测失败", str(error))

    def open_results(self):
        if self.project is not None:
            import subprocess
            d = str(self.project.runs_dir / "detect")
            if Path(d).exists():
                subprocess.Popen(["explorer", d])
