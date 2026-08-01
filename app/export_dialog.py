import threading
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class ExportWorker(QThread):
    log = Signal(str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, model_path, fmt, imgsz, half, parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.fmt = fmt
        self.imgsz = imgsz
        self.half = half

    def run(self):
        try:
            from ultralytics import YOLO
            self.log.emit("加载模型...")
            model = YOLO(self.model_path)
            self.log.emit(f"导出 {self.fmt.upper()} ...")
            out = model.export(format=self.fmt, imgsz=self.imgsz, half=self.half, simplify=True)
            self.done.emit(str(out))
        except Exception as e:
            self.failed.emit(str(e))


class ExportDialog(QDialog):
    def __init__(self, model_path, parent=None):
        super().__init__(parent)
        self.model_path = str(model_path)
        self.worker = None
        self.setWindowTitle("导出模型")
        self.setMinimumWidth(420)

        form = QFormLayout()
        self.lbl_model = QLabel(self.model_path)
        self.lbl_model.setWordWrap(True)
        form.addRow("模型:", self.lbl_model)

        self.combo_fmt = QComboBox()
        self.combo_fmt.addItems(["onnx", "engine", "tflite"])
        form.addRow("格式:", self.combo_fmt)

        self.combo_imgsz = QComboBox()
        self.combo_imgsz.addItems(["640", "416", "512", "768"])
        form.addRow("图片尺寸:", self.combo_imgsz)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        form.addRow(self.progress)

        self.lbl_log = QLabel("")
        form.addRow(self.lbl_log)

        btn_row = QHBoxLayout()
        self.btn_export = QPushButton("导出")
        self.btn_export.clicked.connect(self.start_export)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.close)
        btn_row.addWidget(self.btn_export)
        btn_row.addWidget(self.btn_close)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_row)

    def start_export(self):
        fmt = self.combo_fmt.currentText()
        imgsz = int(self.combo_imgsz.currentText())
        half = fmt == "engine"
        self.btn_export.setEnabled(False)
        self.progress.setVisible(True)
        self.worker = ExportWorker(self.model_path, fmt, imgsz, half)
        self.worker.log.connect(self.lbl_log.setText)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _done(self, out):
        self.btn_export.setEnabled(True)
        self.progress.setVisible(False)
        QMessageBox.information(self, "导出完成", f"已导出到:\n{out}")

    def _failed(self, err):
        self.btn_export.setEnabled(True)
        self.progress.setVisible(False)
        QMessageBox.critical(self, "导出失败", str(err))
