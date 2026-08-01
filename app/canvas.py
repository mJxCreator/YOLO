from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from .config import class_color


class BoxItem(QGraphicsRectItem):
    """单个标注框：矩形 + 顶部文字标签"""

    def __init__(self, rect: QRectF, label: str, index: int, color: str = None):
        super().__init__(rect)
        self.label = label
        self.index = index
        self.color = color or class_color(index)
        self.is_moving = False

        pen = QPen(QColor(self.color), 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)

        self.text_item = QGraphicsSimpleTextItem(label, self)
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        self.text_item.setFont(f)
        self.text_item.setBrush(QColor(self.color))
        self._update_text_pos()

    def _update_text_pos(self):
        bg = self.boundingRect()
        self.text_item.setPos(bg.left() + 1, bg.top() - 18 if bg.top() - 18 > 0 else bg.top() + 1)

    def set_label(self, label):
        self.label = label
        self.text_item.setText(label)
        color = class_color(self.index)
        self.color = color
        pen = QPen(QColor(color), 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.text_item.setBrush(QColor(color))
        self._update_text_pos()

    def get_rect(self) -> QRectF:
        return self.rect()

    def set_color_index(self, index):
        self.index = index
        color = class_color(index)
        self.color = color
        pen = QPen(QColor(color), 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.text_item.setBrush(QColor(color))


class AnnotationCanvas(QGraphicsView):
    """标注画布：支持画框、移动、删除、缩放、平移"""

    new_box_created = Signal(object, str)      # (QRectF, label)
    box_selected = Signal(int)                  # index
    boxes_changed = Signal()                    # 框被移动/删除后
    image_loaded = Signal()
    current_label_changed = Signal(str)
    draw_mode_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor(30, 30, 30))
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        self._pixmap_item = None
        self._boxes = []
        self.image_path = None
        self.image_pixmap = None

        self._draw_mode = False
        self._start_point = None
        self._current_rect_item = None
        self._panning = False
        self._pan_start = QPointF()
        self._moving_box = None
        self._move_start = QPointF()
        self._orig_rect = QRectF()

        self._class_names = []
        self._current_label = ""

    # ---------- 模式 ----------
    @property
    def draw_mode(self):
        return self._draw_mode

    def set_draw_mode(self, enabled):
        self._draw_mode = enabled
        self.unsetCursor()
        if enabled:
            self.setCursor(Qt.CrossCursor)
        self.draw_mode_changed.emit(enabled)

    def set_current_label(self, label):
        self._current_label = label
        self.current_label_changed.emit(label)

    def set_class_names(self, names):
        self._class_names = list(names)
        if self._class_names and self._current_label not in self._class_names:
            self.set_current_label(self._class_names[0])

    def current_label(self):
        return self._current_label

    # ---------- 图片 ----------
    def load_image(self, path):
        self.scene.clear()
        self._boxes = []
        self.image_path = str(path)
        self.image_pixmap = QPixmap(path)
        if self.image_pixmap.isNull():
            self.image_path = None
            self.image_pixmap = None
            return False
        self._pixmap_item = self.scene.addPixmap(self.image_pixmap)
        self.setSceneRect(self.scene.itemsBoundingRect())
        self.fit_to_view()
        self.image_loaded.emit()
        return True

    def fit_to_view(self):
        if self._pixmap_item is not None:
            self.fitInView(self._pixmap_item.boundingRect(), Qt.KeepAspectRatio)

    def image_size(self):
        if self.image_pixmap is not None:
            return self.image_pixmap.width(), self.image_pixmap.height()
        return None

    # ---------- 标注框 ----------
    def set_boxes(self, boxes):
        """boxes: list of (QRectF, label)"""
        for b in self._boxes:
            self.scene.removeItem(b)
        self._boxes = []
        for rect, label in boxes:
            item = BoxItem(rect, label, len(self._boxes))
            self.scene.addItem(item)
            self._boxes.append(item)

    def get_boxes(self):
        return [(b.get_rect(), b.label) for b in self._boxes]

    def add_box_item(self, rect, label):
        item = BoxItem(rect, label, len(self._boxes))
        self.scene.addItem(item)
        self._boxes.append(item)
        return item

    def delete_selected(self):
        for b in list(self._boxes):
            if b.isSelected():
                self.scene.removeItem(b)
                self._boxes.remove(b)
                self.boxes_changed.emit()
                return True
        return False

    def change_selected_label(self, label):
        for b in self._boxes:
            if b.isSelected():
                b.set_label(label)
                self.boxes_changed.emit()
                return True
        return False

    def select_box_at(self, scene_pos):
        selected = None
        for b in self._boxes:
            if b.rect().contains(scene_pos):
                selected = b
        for b in self._boxes:
            b.setSelected(b is selected)
        if selected is not None:
            self.box_selected.emit(self._boxes.index(selected))
        return selected

    def select_none(self):
        for b in self._boxes:
            b.setSelected(False)

    # ---------- 事件 ----------
    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if self.image_path is None:
            return
        pos = self.mapToScene(event.position().toPoint())

        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space_panning()):
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            return

        if self._draw_mode and event.button() == Qt.LeftButton:
            self._start_point = pos
            self._current_rect_item = QGraphicsRectItem(QRectF(pos, pos))
            pen = QPen(QColor(class_color(len(self._boxes))))
            pen.setCosmetic(True)
            pen.setWidth(2)
            self._current_rect_item.setPen(pen)
            self.scene.addItem(self._current_rect_item)
            return

        if event.button() == Qt.LeftButton:
            box = self.select_box_at(pos)
            if box is not None:
                self._moving_box = box
                self._move_start = pos
                self._orig_rect = QRectF(box.get_rect())
            else:
                self.select_none()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            return

        pos = self.mapToScene(event.position().toPoint())

        if self._draw_mode and self._current_rect_item is not None and self._start_point is not None:
            rect = QRectF(self._start_point, pos).normalized()
            self._current_rect_item.setRect(rect)
            return

        if self._moving_box is not None:
            delta = pos - self._move_start
            self._move_start = pos
            self._moving_box.moveBy(delta.x(), delta.y())
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.unsetCursor()
            return

        if self._draw_mode and self._current_rect_item is not None:
            rect = self._current_rect_item.rect()
            self.scene.removeItem(self._current_rect_item)
            self._current_rect_item = None
            self._start_point = None
            if rect.width() > 3 and rect.height() > 3:
                self.add_box_item(rect, self._current_label)
                self.new_box_created.emit(rect, self._current_label)
            return

        if self._moving_box is not None:
            moved = self._moving_box.get_rect() != self._orig_rect
            self._moving_box = None
            if moved:
                self.boxes_changed.emit()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            self.delete_selected()
            return
        if event.key() == Qt.Key_W:
            self.set_draw_mode(not self._draw_mode)
            return
        super().keyPressEvent(event)

    def _space_panning(self):
        return False

    def keyReleaseEvent(self, event):
        super().keyReleaseEvent(event)

    # ---------- 视图 ----------
    def has_image(self):
        return self.image_path is not None
