from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from .config import class_color

BOX_PEN_WIDTH = 2           # 标注框/多边形线宽
CLOSE_POLY_PX = 12          # 多边形点击起点闭合的判定距离（视图像素）


class BoxItem(QGraphicsRectItem):
    """矩形标注项：矩形 + 顶部文字标签"""

    def __init__(self, rect: QRectF, label: str, index: int, color: str = None):
        super().__init__(rect)
        self.label = label
        self.index = index
        self.color = color or class_color(index)
        self.is_moving = False

        pen = QPen(QColor(self.color), BOX_PEN_WIDTH)
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
        self._update_text_pos()

    def set_color(self, color):
        self.color = color
        pen = QPen(QColor(color), BOX_PEN_WIDTH)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.text_item.setBrush(QColor(color))

    def get_rect(self) -> QRectF:
        return self.rect()


class PolygonItem(QGraphicsPolygonItem):
    """多边形标注项：封闭多边形 + 顶点圆点 + 顶部文字标签"""

    def __init__(self, points, label: str, index: int, color: str = None):
        super().__init__(QPolygonF(points))
        self.label = label
        self.index = index
        self.color = color or class_color(index)
        self.points = [QPointF(p) for p in points]
        self.is_moving = False

        pen = QPen(QColor(self.color), BOX_PEN_WIDTH)
        pen.setCosmetic(True)
        self.setPen(pen)
        fill = QColor(self.color)
        fill.setAlpha(40)
        self.setBrush(fill)
        self.setFlag(QGraphicsPolygonItem.ItemIsSelectable, True)

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
        self._update_text_pos()

    def set_color(self, color):
        self.color = color
        pen = QPen(QColor(color), BOX_PEN_WIDTH)
        pen.setCosmetic(True)
        self.setPen(pen)
        fill = QColor(color)
        fill.setAlpha(40)
        self.setBrush(fill)
        self.text_item.setBrush(QColor(color))

    def set_points(self, points):
        self.points = [QPointF(p) for p in points]
        self.setPolygon(QPolygonF(self.points))
        self._update_text_pos()

    def get_points(self):
        return list(self.points)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.save()
        painter.setPen(QPen(QColor(self.color), 1))
        painter.setBrush(QColor(self.color))
        r = 3.0
        for p in self.points:
            painter.drawEllipse(p, r, r)
        painter.restore()


class PolygonPreviewItem(QGraphicsPathItem):
    """多边形绘制中的实时预览：顶点圆点 + 依次连线（实线）"""

    def __init__(self, color):
        super().__init__()
        self.color = color
        self.points = []
        self.setAcceptedMouseButtons(Qt.NoButton)
        pen = QPen(QColor(color), BOX_PEN_WIDTH)
        pen.setCosmetic(True)
        self.setPen(pen)

    def set_points(self, points):
        self.points = list(points)
        path = QPainterPath()
        if points:
            path.moveTo(points[0])
            for p in points[1:]:
                path.lineTo(p)
        self.setPath(path)
        self.update()

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.save()
        painter.setPen(QPen(QColor(self.color), 1))
        painter.setBrush(QColor(self.color))
        r = 3.0
        for p in self.points:
            painter.drawEllipse(p, r, r)
        painter.restore()


class AnnotationCanvas(QGraphicsView):
    """标注画布：支持框选、描边（多边形）、移动、删除、缩放、平移、撤销"""

    new_box_created = Signal(object, str)      # (QRectF, label)  兼容旧信号
    annotation_created = Signal()              # 新标注完成（框或多边形）
    box_selected = Signal(int)                 # index
    boxes_changed = Signal()                   # 标注被移动/删除后
    image_loaded = Signal()
    current_label_changed = Signal(str)
    draw_mode_changed = Signal(bool)
    polygon_mode_changed = Signal(bool)

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
        self._items = []               # 统一标注列表：BoxItem / PolygonItem
        self.image_path = None
        self.image_pixmap = None

        self._draw_mode = False
        self._polygon_mode = False
        self._start_point = None
        self._current_rect_item = None
        self._panning = False
        self._pan_start = QPointF()
        self._moving_item = None
        self._move_start = QPointF()
        self._orig_geom = None

        # 多边形绘制状态
        self._poly_points = []
        self._poly_preview = None

        self._class_names = []
        self._current_label = ""
        self._label_colors = {}          # 标签名 -> 颜色

        self._undo_stack = []            # 撤销历史（每次记录变更前的标注快照）
        self._undo_limit = 100

    # ---------- 标签颜色 ----------
    def set_label_colors(self, colors: dict):
        self._label_colors = dict(colors)
        self.refresh_box_colors()

    def label_color(self, label, index=0):
        if label in self._label_colors:
            return self._label_colors[label]
        return class_color(index)

    def refresh_box_colors(self):
        for it in self._items:
            it.set_color(self.label_color(it.label, it.index))

    # ---------- 模式 ----------
    @property
    def draw_mode(self):
        return self._draw_mode

    @property
    def polygon_mode(self):
        return self._polygon_mode

    def set_draw_mode(self, enabled):
        if enabled and self._polygon_mode:
            self._polygon_mode = False
            self._cancel_polygon_draw()
            self.polygon_mode_changed.emit(False)
        self._draw_mode = enabled
        self.unsetCursor()
        if enabled:
            self.setCursor(Qt.CrossCursor)
        self.draw_mode_changed.emit(enabled)

    def set_polygon_mode(self, enabled):
        if enabled and self._draw_mode:
            self._draw_mode = False
            self.draw_mode_changed.emit(False)
        self._polygon_mode = enabled
        if not enabled:
            self._cancel_polygon_draw()
        self.unsetCursor()
        if enabled:
            self.setCursor(Qt.CrossCursor)
        self.polygon_mode_changed.emit(enabled)

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
        self._items = []
        self.clear_undo()
        self._cancel_polygon_draw()
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

    # ---------- 标注项 ----------
    def get_annotations(self):
        """统一标注列表：[("box", QRectF, label) | ("poly", [QPointF...], label)]"""
        anns = []
        for it in self._items:
            if isinstance(it, PolygonItem):
                anns.append(("poly", it.get_points(), it.label))
            else:
                anns.append(("box", it.get_rect(), it.label))
        return anns

    def set_annotations(self, annotations):
        for it in self._items:
            self.scene.removeItem(it)
        self._items = []
        for kind, geom, label in annotations:
            if kind == "poly":
                self._add_polygon(geom, label)
            else:
                self._add_box(geom, label)

    def set_boxes(self, boxes):
        """兼容接口：仅设置矩形框"""
        self.set_annotations([("box", r, l) for r, l in boxes])

    def get_boxes(self):
        """兼容接口：仅返回矩形框"""
        return [(it.get_rect(), it.label) for it in self._items if not isinstance(it, PolygonItem)]

    def _add_box(self, rect, label):
        item = BoxItem(rect, label, len(self._items))
        item.set_color(self.label_color(label, len(self._items)))
        self.scene.addItem(item)
        self._items.append(item)
        return item

    def _add_polygon(self, points, label):
        item = PolygonItem(points, label, len(self._items))
        item.set_color(self.label_color(label, len(self._items)))
        self.scene.addItem(item)
        self._items.append(item)
        return item

    def add_box_item(self, rect, label):
        self._record_undo()
        item = self._add_box(rect, label)
        self.new_box_created.emit(rect, label)
        self.annotation_created.emit()
        return item

    def add_polygon_item(self, points, label):
        if len(points) < 3:
            return None
        self._record_undo()
        item = self._add_polygon(points, label)
        self.annotation_created.emit()
        return item

    def delete_selected(self):
        sel = [it for it in self._items if it.isSelected()]
        if not sel:
            return False
        self._record_undo()
        for it in sel:
            self.scene.removeItem(it)
            self._items.remove(it)
        self.boxes_changed.emit()
        return True

    def select_at(self, scene_pos):
        """选中包含场景坐标的标注项（最上层优先），同时清除其他选中"""
        selected = None
        for it in reversed(self._items):
            if isinstance(it, PolygonItem):
                if QPolygonF(it.get_points()).containsPoint(scene_pos, Qt.OddEvenFill):
                    selected = it
                    break
            else:
                if it.rect().contains(scene_pos):
                    selected = it
                    break
        for it in self._items:
            it.setSelected(it is selected)
        if selected is not None:
            self.box_selected.emit(self._items.index(selected))
        return selected

    def select_box_at(self, scene_pos):
        return self.select_at(scene_pos)

    def select_none(self):
        for it in self._items:
            it.setSelected(False)

    # ---------- 撤销 ----------
    def clear_undo(self):
        self._undo_stack.clear()

    def can_undo(self):
        return bool(self._undo_stack)

    def _record_undo(self):
        snapshot = self.get_annotations()
        if len(self._undo_stack) >= self._undo_limit:
            self._undo_stack.pop(0)
        self._undo_stack.append(snapshot)

    def undo(self):
        """撤销上一步操作，返回是否执行了撤销"""
        if not self._undo_stack:
            return False
        snapshot = self._undo_stack.pop()
        self.set_annotations(snapshot)
        self.boxes_changed.emit()
        return True

    # ---------- 多边形绘制 ----------
    def _polygon_click(self, scene_pos, view_pos):
        pts = self._poly_points
        if pts and len(pts) >= 3:
            first = self.mapFromScene(pts[0])
            if (QPointF(first) - view_pos).manhattanLength() <= CLOSE_POLY_PX:
                self._finish_polygon()
                return
        if len(pts) < 500:
            self._poly_points.append(QPointF(scene_pos))
            self._update_polygon_preview(scene_pos)

    def _finish_polygon(self):
        pts = self._poly_points
        self._cancel_polygon_draw()
        if len(pts) >= 3:
            self.add_polygon_item(pts, self._current_label)

    def _cancel_polygon_draw(self):
        self._poly_points = []
        if self._poly_preview is not None:
            self.scene.removeItem(self._poly_preview)
            self._poly_preview = None

    def _update_polygon_preview(self, cursor_pos=None):
        pts = list(self._poly_points)
        if cursor_pos is not None:
            pts.append(cursor_pos)
        if self._poly_preview is None:
            self._poly_preview = PolygonPreviewItem(
                self.label_color(self._current_label, len(self._items))
            )
            self.scene.addItem(self._poly_preview)
        self._poly_preview.set_points(pts)

    # ---------- 几何辅助 ----------
    def _item_geom(self, item):
        if isinstance(item, PolygonItem):
            return item.get_points()
        return item.get_rect()

    def _set_item_geom(self, item, geom):
        if isinstance(item, PolygonItem):
            item.set_points(geom)
        else:
            item.setRect(geom)

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

        if self._polygon_mode:
            if event.button() == Qt.RightButton:
                self._cancel_polygon_draw()
            elif event.button() == Qt.LeftButton:
                self._polygon_click(pos, event.position())
            return

        if self._draw_mode and event.button() == Qt.LeftButton:
            self._start_point = pos
            self._current_rect_item = QGraphicsRectItem(QRectF(pos, pos))
            pen = QPen(QColor(self.label_color(self._current_label, len(self._items))))
            pen.setCosmetic(True)
            pen.setWidth(BOX_PEN_WIDTH)
            self._current_rect_item.setPen(pen)
            self.scene.addItem(self._current_rect_item)
            return

        if event.button() == Qt.LeftButton:
            item = self.select_at(pos)
            if item is not None:
                self._moving_item = item
                self._move_start = pos
                self._orig_geom = self._item_geom(item)
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

        if self._polygon_mode and self._poly_points:
            self._update_polygon_preview(pos)
            return

        if self._draw_mode and self._current_rect_item is not None and self._start_point is not None:
            rect = QRectF(self._start_point, pos).normalized()
            self._current_rect_item.setRect(rect)
            return

        if self._moving_item is not None:
            delta = pos - self._move_start
            self._move_start = pos
            self._moving_item.moveBy(delta.x(), delta.y())
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.unsetCursor()
            return

        if self._polygon_mode:
            return

        if self._draw_mode and self._current_rect_item is not None:
            rect = self._current_rect_item.rect()
            self.scene.removeItem(self._current_rect_item)
            self._current_rect_item = None
            self._start_point = None
            if rect.width() > 3 and rect.height() > 3:
                self.add_box_item(rect, self._current_label)
            return

        if self._moving_item is not None:
            current_geom = self._item_geom(self._moving_item)
            moved = current_geom != self._orig_geom
            if moved:
                # 先恢复移动前几何生成快照，再移回当前位置
                self._set_item_geom(self._moving_item, self._orig_geom)
                self._record_undo()
                self._set_item_geom(self._moving_item, current_geom)
            self._moving_item = None
            if moved:
                self.boxes_changed.emit()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._cancel_polygon_draw()
        super().keyPressEvent(event)

    def _space_panning(self):
        return False

    def keyReleaseEvent(self, event):
        super().keyReleaseEvent(event)

    # ---------- 视图 ----------
    def has_image(self):
        return self.image_path is not None
