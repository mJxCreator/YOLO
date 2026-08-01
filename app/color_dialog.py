from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

SV_SIZE = 260
HUE_W = SV_SIZE
HUE_H = 22


class _SVPanel(QWidget):
    """饱和度(S，水平) × 明度(V，垂直) 色域面板"""

    sv_changed = Signal(int, int)  # s, v (0-255)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SV_SIZE, SV_SIZE)
        self.setMouseTracking(True)
        self._hue = 0
        self._s = 255
        self._v = 255
        self._bg = None

    def set_hue(self, h):
        self._hue = max(0, min(359, h))
        self._bg = None
        self.update()

    def set_sv(self, s, v):
        self._s = max(0, min(255, s))
        self._v = max(0, min(255, v))
        self.update()

    def sv(self):
        return self._s, self._v

    def _render(self):
        pm = QPixmap(SV_SIZE, SV_SIZE)
        p = QPainter(pm)
        # 每列一条垂直渐变：底部黑色 → 顶部当前色相全饱和色
        for x in range(SV_SIZE):
            s = int(x / (SV_SIZE - 1) * 255)
            top = QColor.fromHsv(self._hue, s, 255)
            g = QLinearGradient(0, SV_SIZE, 0, 0)
            g.setColorAt(0, QColor(0, 0, 0))
            g.setColorAt(1, top)
            p.fillRect(x, 0, 1, SV_SIZE, g)
        p.end()
        self._bg = pm

    def paintEvent(self, event):
        if self._bg is None:
            self._render()
        p = QPainter(self)
        p.drawPixmap(0, 0, self._bg)
        # 当前选择点标记
        x = int(self._s / 255 * (SV_SIZE - 1))
        y = int((255 - self._v) / 255 * (SV_SIZE - 1))
        light = (self._v > 128 and self._s < 200)
        p.setPen(QPen(QColor(255, 255, 255) if light else QColor(0, 0, 0), 2))
        p.drawEllipse(x - 5, y - 5, 10, 10)
        p.end()

    def _update_from_pos(self, pos):
        x = max(0, min(SV_SIZE - 1, pos.x()))
        y = max(0, min(SV_SIZE - 1, pos.y()))
        s = int(x / (SV_SIZE - 1) * 255)
        v = int((SV_SIZE - 1 - y) / (SV_SIZE - 1) * 255)
        self._s, self._v = s, v
        self.update()
        self.sv_changed.emit(s, v)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._update_from_pos(event.position())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._update_from_pos(event.position())


class _HueBar(QWidget):
    """色相条（0-360 彩虹渐变）"""

    hue_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(HUE_W, HUE_H)
        self.setMouseTracking(True)
        self._hue = 0

    def set_hue(self, h):
        self._hue = max(0, min(359, h))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        g = QLinearGradient(0, 0, HUE_W, 0)
        for i in range(7):
            g.setColorAt(i / 6, QColor.fromHsv(int(i / 6 * 360), 255, 255))
        p.fillRect(0, 0, HUE_W, HUE_H, g)
        # 当前色相指示
        x = int(self._hue / 359 * (HUE_W - 1))
        p.setPen(QPen(QColor(0, 0, 0), 1))
        p.drawLine(x, 0, x, HUE_H)
        p.drawLine(x - 1, 0, x - 1, HUE_H)
        p.end()

    def _update_from_pos(self, pos):
        x = max(0, min(HUE_W - 1, pos.x()))
        h = int(x / (HUE_W - 1) * 359)
        self._hue = h
        self.update()
        self.hue_changed.emit(h)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._update_from_pos(event.position())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._update_from_pos(event.position())


class SimpleColorDialog(QDialog):
    """极简颜色选择器：一个全色大色盘（SV色域 + 色相条）+ 确定/取消"""

    def __init__(self, initial, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)

        h, s, v, _ = QColor(initial).getHsv()
        self._hue = max(0, h)
        self._s = s
        self._v = v

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        self.sv_panel = _SVPanel()
        self.sv_panel.set_hue(self._hue)
        self.sv_panel.set_sv(self._s, self._v)
        self.sv_panel.sv_changed.connect(self._on_sv_changed)
        lay.addWidget(self.sv_panel, 0, Qt.AlignHCenter)

        self.hue_bar = _HueBar()
        self.hue_bar.set_hue(self._hue)
        self.hue_bar.hue_changed.connect(self._on_hue_changed)
        lay.addWidget(self.hue_bar, 0, Qt.AlignHCenter)

        info = QHBoxLayout()
        self.preview = QLabel()
        self.preview.setFixedSize(48, 26)
        self.preview.setStyleSheet("border: 1px solid #888; border-radius: 3px;")
        self.lbl_hex = QLabel()
        self.lbl_hex.setStyleSheet("color: #666;")
        info.addWidget(self.preview)
        info.addWidget(self.lbl_hex)
        info.addStretch(1)
        lay.addLayout(info)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_ok = QPushButton("确定")
        btn_ok.setStyleSheet("QPushButton { background: #2d8cf0; color: white; min-width: 76px; }")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet("QPushButton { min-width: 76px; }")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        lay.addLayout(btns)

        self._update_preview()

    def _on_hue_changed(self, h):
        self._hue = h
        self.sv_panel.set_hue(h)
        self._update_preview()

    def _on_sv_changed(self, s, v):
        self._s, self._v = s, v
        self._update_preview()

    def _update_preview(self):
        self._color = QColor.fromHsv(self._hue, self._s, self._v)
        self.preview.setStyleSheet(
            f"border: 1px solid #888; border-radius: 3px; background-color: {self._color.name()};"
        )
        self.lbl_hex.setText(self._color.name().upper())

    def get_color(self):
        return QColor(self._color)
