import random
import re
import shutil
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class EmittingStream:
    """将 stdout 同时转发到信号，实现 GUI 实时日志"""

    def __init__(self, callback):
        self._callback = callback

    def write(self, text):
        self._callback(text)

    def flush(self):
        pass


class TrainWorker(QThread):
    log_line = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, data_yaml, model_path, params, device, parent=None):
        super().__init__(parent)
        self.data_yaml = data_yaml
        self.model_path = model_path
        self.params = params
        self.device = device
        self._stop = False
        self.model = None

    def run(self):
        original_out = sys.stdout
        original_err = sys.stderr
        sys.stdout = EmittingStream(self.log_line.emit)
        sys.stderr = EmittingStream(self.log_line.emit)
        try:
            from ultralytics import YOLO

            self.model = YOLO(self.model_path)
            self.model.add_callback("on_train_epoch_end", self._check_stop)
            self.model.train(data=self.data_yaml, device=self.device, **self.params)

            if self._stop:
                self.finished_ok.emit("训练已被手动停止")
                return

            metrics = self.model.val(data=self.data_yaml, device=self.device, split="val")
            m = metrics.box
            summary = (
                f"\n===== 验证结果 =====\n"
                f"mAP50:   {m.map50:.4f}\n"
                f"mAP50-95:{m.map:.4f}\n"
                f"Precision: {m.mp:.4f}  Recall: {m.mr:.4f}\n"
                f"最佳权重: {self.model.trainer.best}\n"
            )
            self.log_line.emit(summary)

            if self.params.get("export_onnx"):
                self.log_line.emit("\n正在导出 ONNX 模型...")
                try:
                    self.model.export(format="onnx", imgsz=self.params.get("imgsz", 640), simplify=True)
                except Exception as e:
                    self.log_line.emit(f"ONNX 导出失败: {e}")
            self.finished_ok.emit(str(self.model.trainer.best))
        except Exception as e:
            import traceback
            self.log_line.emit(traceback.format_exc())
            self.failed.emit(str(e))
        finally:
            sys.stdout = original_out
            sys.stderr = original_err

    def _check_stop(self, trainer):
        if self._stop:
            trainer.stop = True

    def stop(self):
        self._stop = True


class TrainPage(QWidget):
    """训练界面：数据划分 + 参数配置 + 训练进度"""

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.worker = None
        self._device = "cpu"
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()

        # ---- 左：数据划分 ----
        left = QGroupBox("数据集划分")
        lf = QFormLayout(left)
        self.split_ratio = QDoubleSpinBox()
        self.split_ratio.setRange(0.5, 0.95)
        self.split_ratio.setValue(0.8)
        self.split_ratio.setSingleStep(0.05)
        self.split_ratio.setSuffix(" 训练 / 验证")
        lf.addRow("训练比例:", self.split_ratio)

        self.btn_split = QPushButton("执行划分")
        self.btn_split.clicked.connect(self.split_dataset)
        lf.addRow(self.btn_split)

        self.lbl_split_result = QLabel("尚未划分")
        lf.addRow(self.lbl_split_result)

        # ---- 右：训练参数 ----
        right = QGroupBox("训练参数")
        rf = QFormLayout(right)

        self.combo_model = QComboBox()
        self.btn_refresh_model = QPushButton("刷新")
        self.btn_refresh_model.clicked.connect(self.refresh_models)
        model_row = QHBoxLayout()
        model_row.addWidget(self.combo_model, 1)
        model_row.addWidget(self.btn_refresh_model)
        rf.addRow("模型:", model_row)

        self.epochs = QSpinBox()
        self.epochs.setRange(1, 2000)
        self.epochs.setValue(100)
        rf.addRow("训练轮数:", self.epochs)

        self.batch = QSpinBox()
        self.batch.setRange(1, 256)
        self.batch.setValue(16)
        rf.addRow("批次大小:", self.batch)

        self.imgsz = QComboBox()
        self.imgsz.addItems(["640", "416", "512", "768", "1024"])
        self.imgsz.setCurrentText("640")
        rf.addRow("图片尺寸:", self.imgsz)

        self.lr = QDoubleSpinBox()
        self.lr.setDecimals(4)
        self.lr.setRange(0.0001, 0.1)
        self.lr.setValue(0.001)
        self.lr.setSingleStep(0.0005)
        rf.addRow("学习率:", self.lr)

        self.pretrained = QCheckBox("使用预训练权重")
        self.pretrained.setChecked(True)
        rf.addRow(self.pretrained)

        self.export_onnx = QCheckBox("训练后导出 ONNX")
        self.export_onnx.setChecked(True)
        rf.addRow(self.export_onnx)

        self.combo_device = QComboBox()
        self.combo_device.addItems(["自动选择", "cpu", "cuda:0"])
        rf.addRow("训练设备:", self.combo_device)

        top.addWidget(left)
        top.addWidget(right, 1)
        root.addLayout(top)

        # ---- 训练控制 ----
        ctrl = QHBoxLayout()
        self.btn_train = QPushButton("开始训练")
        self.btn_train.setStyleSheet("QPushButton { background: #2d8cf0; color: white; padding: 6px 18px; }")
        self.btn_train.clicked.connect(self.start_training)
        self.btn_stop = QPushButton("停止训练")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_training)
        self.btn_open_results = QPushButton("打开结果文件夹")
        self.btn_open_results.clicked.connect(self.open_results)
        self.lbl_device = QLabel("设备: 未检测")
        ctrl.addWidget(self.btn_train)
        ctrl.addWidget(self.btn_stop)
        ctrl.addWidget(self.btn_open_results)
        ctrl.addStretch(1)
        ctrl.addWidget(self.lbl_device)
        root.addLayout(ctrl)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        root.addWidget(self.log_view, 1)

    # ---------- 设备检测 ----------
    def set_config(self, config):
        """读取应用启动时缓存的设备检测结果"""
        device = config.data.get("settings", {}).get("device")
        if device:
            self._on_device_detected(device)
        else:
            self.lbl_device.setText("设备: 检测中...")

    def _on_device_detected(self, device):
        self._device = device
        if device == "cuda:0":
            self.lbl_device.setText("设备: GPU 可用 ✓")
        else:
            self.lbl_device.setText("设备: CPU (未检测到 GPU)")

    # ---------- 项目绑定 ----------
    def set_project(self, project):
        self.project = project
        self.refresh_models()

    def refresh_models(self):
        if self.project is None:
            return
        self.combo_model.clear()
        trained = self.project.get_trained_models()
        pretrained = self.project.get_pretrained_models()
        current = self.combo_model.currentText()
        for p in trained:
            self.combo_model.addItem(f"[训练] {p}", str(p))
        for p in pretrained:
            if p.suffix == ".pt":
                self.combo_model.addItem(f"[预训练] {p.name}", str(p))
        if current:
            idx = self.combo_model.findText(current)
            if idx >= 0:
                self.combo_model.setCurrentIndex(idx)

    # ---------- 数据划分 ----------
    def split_dataset(self):
        if self.project is None:
            QMessageBox.warning(self, "提示", "请先打开项目")
            return
        images = self.project.list_images()
        if not images:
            QMessageBox.warning(self, "提示", "项目中没有图片，请先导入图片并标注")
            return
        classes = self.project.get_classes()
        if not classes:
            QMessageBox.warning(self, "提示", "请先添加至少一个缺陷类别")
            return

        ratio = self.split_ratio.value()
        random.seed(42)
        shuffled = list(images)
        random.shuffle(shuffled)
        split_idx = int(len(shuffled) * ratio)

        dset = self.project.datasets_dir
        for sub in ["images/train", "images/val", "labels/train", "labels/val"]:
            d = dset / sub
            d.mkdir(parents=True, exist_ok=True)
            for f in d.iterdir():
                if f.is_file():
                    f.unlink()

        n_train = n_val = 0
        for i, img in enumerate(shuffled):
            sub = "train" if i < split_idx else "val"
            shutil.copy2(img, dset / "images" / sub / img.name)
            label_path = self.project.get_label_path(img)
            dst_label = dset / "labels" / sub / f"{img.stem}.txt"
            if label_path.exists():
                shutil.copy2(label_path, dst_label)
            else:
                dst_label.write_text("", encoding="utf-8")
            if sub == "train":
                n_train += 1
            else:
                n_val += 1

        data_yaml = self._write_data_yaml()
        self.lbl_split_result.setText(
            f"完成：训练 {n_train} 张 / 验证 {n_val} 张，共 {len(classes)} 类"
        )
        self.status_message.emit(f"数据集划分完成 (train={n_train}, val={n_val})")
        return data_yaml

    def _write_data_yaml(self):
        classes = self.project.get_classes()
        dset = str(self.project.datasets_dir).replace("\\", "/")
        yaml_text = (
            f"path: {dset}\n"
            f"train: images/train\n"
            f"val: images/val\n"
            f"nc: {len(classes)}\n"
            f"names:\n"
        )
        for i, c in enumerate(classes):
            yaml_text += f"  {i}: {c}\n"
        yaml_path = self.project.root / "data.yaml"
        yaml_path.write_text(yaml_text, encoding="utf-8")
        return str(yaml_path)

    # ---------- 训练控制 ----------
    def start_training(self):
        if self.project is None:
            QMessageBox.warning(self, "提示", "请先打开项目")
            return
        data_yaml = self.project.root / "data.yaml"
        if not data_yaml.exists():
            QMessageBox.warning(self, "提示", "请先执行数据集划分")
            return

        model_path = self.combo_model.currentData()
        if not model_path:
            QMessageBox.warning(self, "提示", "请选择训练模型")
            return

        device = self.combo_device.currentText()
        if device == "自动选择":
            device = self._device

        params = dict(
            epochs=self.epochs.value(),
            batch=self.batch.value(),
            imgsz=int(self.imgsz.currentText()),
            lr0=self.lr.value(),
            pretrained=self.pretrained.isChecked(),
            project=str(self.project.runs_dir),
            name="train",
            exist_ok=True,
            verbose=True,
            patience=30,
            export_onnx=self.export_onnx.isChecked(),
        )

        self.log_view.clear()
        self.progress.setValue(0)
        self.btn_train.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_message.emit("开始训练...")

        self.worker = TrainWorker(str(data_yaml), model_path, params, device)
        self.worker.log_line.connect(self._append_log)
        self.worker.finished_ok.connect(self._on_train_done)
        self.worker.failed.connect(self._on_train_failed)
        self.worker.start()

    def stop_training(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.status_message.emit("正在停止训练...")

    def _append_log(self, text):
        self.log_view.appendPlainText(text.rstrip())
        self.log_view.moveCursor(self.log_view.textCursor().End)
        m = re.search(r"^\s*(\d+)/(\d+)\s", text)
        if m:
            cur, total = int(m.group(1)), int(m.group(2))
            self.progress.setMaximum(total)
            self.progress.setValue(cur)

    def _on_train_done(self, message):
        self.btn_train.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setValue(self.progress.maximum())
        self.refresh_models()
        self.status_message.emit("训练完成")
        QMessageBox.information(self, "训练完成", f"训练完成！\n{message}")

    def _on_train_failed(self, error):
        self.btn_train.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_message.emit(f"训练失败: {error}")
        QMessageBox.critical(self, "训练失败", str(error))

    def open_results(self):
        if self.project is not None:
            d = str(self.project.runs_dir)
            if Path(d).exists():
                try:
                    import subprocess
                    subprocess.Popen(["explorer", d])
                except Exception:
                    pass
