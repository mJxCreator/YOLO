from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .canvas import AnnotationCanvas
from .color_dialog import SimpleColorDialog
from .config import IMAGE_EXTS, class_color
from .yolo_format import load_yolo_labels, save_yolo_labels


class TagRowWidget(QWidget):
    """标签列表行：左侧标签名（点击选中），右侧色盘按钮（点击选颜色）"""

    selected = Signal(str)        # 标签名
    color_requested = Signal(str) # 标签名

    def __init__(self, name, color, parent=None):
        super().__init__(parent)
        self.name = name
        self._selected = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(6)

        self.lbl = QLabel(name)
        self.lbl.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.lbl, 1)

        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(22, 22)
        self.btn_color.setCursor(Qt.PointingHandCursor)
        self.btn_color.setToolTip(f"点击选择「{name}」的颜色")
        self.set_swatch(color)
        self.btn_color.clicked.connect(lambda: self.color_requested.emit(self.name))
        lay.addWidget(self.btn_color)

    def set_swatch(self, color):
        self.btn_color.setStyleSheet(
            f"QPushButton {{ background-color: {color}; "
            "border: 1px solid #888; border-radius: 3px; }}"
        )

    def set_selected(self, selected):
        self._selected = selected
        if selected:
            self.lbl.setStyleSheet(
                "font-weight: bold; color: #2d8cf0; background-color: rgba(45, 140, 240, 0.12);"
            )
        else:
            self.lbl.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.name)
        super().mousePressEvent(event)


class AnnotatePage(QWidget):
    """标注界面：模仿 LabelImg"""

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.image_list = []
        self.current_index = -1
        self.current_boxes = []      # list of (QRectF, class_id)
        self._dirty = False
        self._auto_save = False
        self._current_tag = None
        self._tag_rows = {}

        self.setAcceptDrops(True)
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        root = QHBoxLayout(self)

        # 左侧：图片列表
        left = QWidget()
        left.setFixedWidth(240)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(6, 6, 6, 6)

        self.btn_import = QPushButton("导入图片")
        self.btn_import.clicked.connect(self.import_images)
        lv.addWidget(self.btn_import)

        hint = QLabel("提示：可直接把图片文件或整个文件夹拖入窗口")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        lv.addWidget(hint)

        self.file_list = QListWidget()
        self.file_list.currentRowChanged.connect(self._on_select_file)
        self.file_list.setAcceptDrops(False)
        lv.addWidget(self.file_list, 1)

        self.lbl_index = QLabel("无图片")
        lv.addWidget(self.lbl_index)

        nav = QHBoxLayout()
        self.btn_prev = QPushButton("上一张 (A)")
        self.btn_next = QPushButton("下一张 (D)")
        self.btn_prev.clicked.connect(self.prev_image)
        self.btn_next.clicked.connect(self.next_image)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        lv.addLayout(nav)

        # 标签导航栏：显示所有已添加的标签，点击即可选择
        lbl_tag = QLabel("标签列表（点击选择）")
        lbl_tag.setStyleSheet("font-weight: bold; margin-top: 6px;")
        lv.addWidget(lbl_tag)

        self.tag_list = QListWidget()
        self.tag_list.setFixedHeight(150)
        self.tag_list.setAcceptDrops(False)
        self.tag_list.setSelectionMode(QListWidget.NoSelection)
        lv.addWidget(self.tag_list)

        tag_btns = QHBoxLayout()
        self.btn_add_tag = QPushButton("新增")
        self.btn_add_tag.clicked.connect(self.add_class)
        self.btn_rename_tag = QPushButton("重命名")
        self.btn_rename_tag.clicked.connect(self.rename_class)
        self.btn_del_tag = QPushButton("删除")
        self.btn_del_tag.clicked.connect(self.delete_class)
        tag_btns.addWidget(self.btn_add_tag)
        tag_btns.addWidget(self.btn_rename_tag)
        tag_btns.addWidget(self.btn_del_tag)
        lv.addLayout(tag_btns)

        # 右侧：画布 + 底部工具栏
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(6, 6, 6, 6)

        self.canvas = AnnotationCanvas()
        self.canvas.new_box_created.connect(self._on_new_box)
        self.canvas.annotation_created.connect(self._mark_dirty)
        self.canvas.boxes_changed.connect(self._mark_dirty)
        self.canvas.image_loaded.connect(self._on_image_loaded)
        self.canvas.setAcceptDrops(False)
        rv.addWidget(self.canvas, 1)

        toolbar = QHBoxLayout()
        self.btn_draw = QPushButton("框选 (W)")
        self.btn_draw.setCheckable(True)
        self.btn_draw.toggled.connect(self.canvas.set_draw_mode)
        self.canvas.draw_mode_changed.connect(self.btn_draw.setChecked)

        self.btn_polygon = QPushButton("描边 (S)")
        self.btn_polygon.setCheckable(True)
        self.btn_polygon.toggled.connect(self.canvas.set_polygon_mode)
        self.canvas.polygon_mode_changed.connect(self.btn_polygon.setChecked)

        self.btn_undo = QPushButton("撤销")
        self.btn_undo.clicked.connect(self.undo)

        self.btn_delete_box = QPushButton("删除框 (Del)")
        self.btn_delete_box.clicked.connect(self.delete_box)

        self.btn_save = QPushButton("保存")
        self.btn_save.setStyleSheet("QPushButton { background: #2d8cf0; color: white; }")
        self.btn_save.clicked.connect(self.save_labels)

        toolbar.addWidget(self.btn_draw)
        toolbar.addWidget(self.btn_polygon)
        toolbar.addWidget(self.btn_undo)
        toolbar.addWidget(self.btn_delete_box)
        toolbar.addWidget(self.btn_save)
        rv.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        # 窗口级快捷键（不依赖焦点，任何控件聚焦时都生效）
        QShortcut(QKeySequence("A"), self, activated=self.prev_image)
        QShortcut(QKeySequence("D"), self, activated=self.next_image)
        QShortcut(QKeySequence("W"), self, activated=self.toggle_draw_mode)
        QShortcut(QKeySequence("S"), self, activated=self.toggle_polygon_mode)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_box)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_labels)

    def toggle_draw_mode(self):
        self.canvas.set_draw_mode(not self.canvas.draw_mode)

    def toggle_polygon_mode(self):
        self.canvas.set_polygon_mode(not self.canvas.polygon_mode)

    # ---------- 项目绑定 ----------
    def set_project(self, project):
        self.project = project
        self._load_images()
        self._update_classes()

    def set_config(self, config):
        self.config = config
        self._auto_save = config.get_auto_save()

    def _full_class_colors(self):
        """所有标签的完整颜色映射：已自定义的保留，未定义的按类别序号分配默认色"""
        classes = self.project.get_classes()
        saved = self.project.get_class_colors()
        return {name: saved.get(name, class_color(i)) for i, name in enumerate(classes)}

    def _update_classes(self):
        classes = self.project.get_classes()
        colors = self._full_class_colors()
        self.canvas.set_class_names(classes)
        self.canvas.set_label_colors(colors)
        current = self.canvas.current_label()

        self.tag_list.clear()
        self._tag_rows = {}
        for i, name in enumerate(classes):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, name)
            item.setSizeHint(self._tag_row_size())
            self.tag_list.addItem(item)
            row = TagRowWidget(name, colors[name])
            row.selected.connect(self._on_pick_tag)
            row.color_requested.connect(self._pick_tag_color)
            self.tag_list.setItemWidget(item, row)
            self._tag_rows[name] = row

        # 高亮当前标签
        if current and current in self._tag_rows:
            self._current_tag = current
            self._set_tag_highlight(current)
        elif classes:
            self._current_tag = classes[0]
            self.canvas.set_current_label(classes[0])
            self._set_tag_highlight(classes[0])
        else:
            self._current_tag = None

    @staticmethod
    def _tag_row_size():
        return QSize(0, 32)

    def _set_tag_highlight(self, name):
        for n, row in self._tag_rows.items():
            row.set_selected(n == name)

    def _on_pick_tag(self, name):
        """点击左侧标签列表行，选择当前要画的标签"""
        self._current_tag = name
        self.canvas.set_current_label(name)
        self._set_tag_highlight(name)
        self.status_message.emit(f"当前标签: {name}")

    def _pick_tag_color(self, name):
        """点击标签行末端的色盘，选择该标签的颜色"""
        colors = self._full_class_colors()
        dlg = SimpleColorDialog(
            QColor(colors.get(name, "#e6194B")),
            f"选择「{name}」的颜色",
            self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        color = dlg.get_color()
        self.project.save_class_color(name, color.name())
        colors = self._full_class_colors()
        self.canvas.set_label_colors(colors)
        self._tag_rows[name].set_swatch(colors[name])
        self.status_message.emit(f"标签「{name}」颜色已更新")

    # ---------- 图片加载 ----------
    def _load_images(self):
        self.image_list = self.project.list_images()
        self.file_list.clear()
        for img in self.image_list:
            self.file_list.addItem(QListWidgetItem(img.name))
        self.current_index = -1
        self._dirty = False
        if self.image_list:
            self.file_list.setCurrentRow(0)
            self.lbl_index.setText(f"1 / {len(self.image_list)}")
        else:
            self.lbl_index.setText("无图片")

    def _on_select_file(self, row):
        if row < 0 or row >= len(self.image_list):
            return
        # 切换图片前，自动保存上一张图片的标注
        if self._auto_save and self._dirty and self.current_index >= 0:
            self.save_labels()
        if self._dirty:
            self.save_labels()
        self.current_index = row
        path = self.image_list[row]
        self.canvas.load_image(str(path))
        self.lbl_index.setText(f"{row + 1} / {len(self.image_list)}")
        self._load_current_labels()

    def _on_image_loaded(self):
        self._dirty = False

    def _load_current_labels(self):
        if self.current_index < 0:
            return
        img_path = self.image_list[self.current_index]
        size = self.canvas.image_size()
        if size is None:
            return
        w, h = size
        label_path = self.project.get_label_path(img_path)
        items = load_yolo_labels(label_path, w, h)
        classes = self.project.get_classes()
        labeled = []
        for kind, cls_id, data in items:
            label = classes[cls_id] if cls_id < len(classes) else f"cls_{cls_id}"
            labeled.append((kind, data, label))
        self.canvas.set_annotations(labeled)

    def _on_new_box(self, rect, label):
        self._mark_dirty()

    def _mark_dirty(self):
        self._dirty = True

    def set_auto_save(self, enabled):
        """设置自动保存：开启后切换图片时自动保存上一张标注"""
        self._auto_save = bool(enabled)

    # ---------- 保存 ----------
    def save_labels(self):
        if self.project is None or self.current_index < 0:
            return
        if not self.canvas.has_image():
            return
        size = self.canvas.image_size()
        if size is None:
            return
        w, h = size
        classes = self.project.get_classes()
        class_to_id = {c: i for i, c in enumerate(classes)}
        items = []
        for kind, geom, label in self.canvas.get_annotations():
            cls_id = class_to_id.get(label, 0)
            items.append((kind, cls_id, geom))
        img_path = self.image_list[self.current_index]
        label_path = self.project.get_label_path(img_path)
        save_yolo_labels(label_path, items, w, h)
        self._dirty = False
        self.status_message.emit(f"已保存 {len(items)} 个标注 → {label_path.name}")

    # ---------- 导航 ----------
    def prev_image(self):
        if self.current_index > 0:
            self.file_list.setCurrentRow(self.current_index - 1)

    def next_image(self):
        if self.current_index < len(self.image_list) - 1:
            self.file_list.setCurrentRow(self.current_index + 1)

    # ---------- 类别 ----------
    def add_class(self):
        name, ok = QInputDialog.getText(self, "添加标签", "输入新标签名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        classes = self.project.get_classes()
        if name in classes:
            QMessageBox.information(self, "提示", "标签已存在")
            return
        classes.append(name)
        self.project.save_classes(classes)
        self._update_classes()
        # 自动选中新标签
        self._current_tag = name
        self.canvas.set_current_label(name)
        self._set_tag_highlight(name)
        self.status_message.emit(f"已添加标签「{name}」")

    def delete_class(self):
        if self.project is None:
            return
        name = self._current_tag
        if name is None:
            QMessageBox.information(self, "提示", "请先在左侧标签列表中选择要删除的标签")
            return
        ret = QMessageBox.question(
            self, "删除标签",
            f"确定删除标签「{name}」？\n当前图片中该标签的标注框也会被删除。",
        )
        if ret != QMessageBox.Yes:
            return
        classes = self.project.get_classes()
        classes = [c for c in classes if c != name]
        self.project.save_classes(classes)
        self.project.remove_class_color(name)
        # 删除当前图片中该标签的标注（框或多边形）
        if self.canvas.has_image():
            anns = self.canvas.get_annotations()
            kept = [a for a in anns if a[2] != name]
            if len(kept) != len(anns):
                self.canvas.set_annotations(kept)
                self._mark_dirty()
        self._current_tag = None
        self._update_classes()
        self.status_message.emit(f"已删除标签「{name}」")

    def rename_class(self):
        """重命名左侧标签列表中选中的标签，保留其在类别列表中的位置（类ID不变）"""
        if self.project is None:
            return
        old_name = self._current_tag
        if old_name is None:
            QMessageBox.information(self, "提示", "请先在左侧标签列表中选择要重命名的标签")
            return
        new_name, ok = QInputDialog.getText(self, "重命名标签", "输入新名称:", text=old_name)
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if new_name == old_name:
            return
        classes = self.project.get_classes()
        if new_name in classes:
            QMessageBox.information(self, "提示", "该名称已存在")
            return
        idx = classes.index(old_name)
        classes[idx] = new_name
        self.project.save_classes(classes)
        self.project.rename_class_color(old_name, new_name)
        # 同步更新画布上该标签的标注（框或多边形）
        if self.canvas.has_image():
            anns = self.canvas.get_annotations()
            changed = False
            updated = []
            for a in anns:
                if a[2] == old_name:
                    updated.append((a[0], a[1], new_name))
                    changed = True
                else:
                    updated.append(a)
            if changed:
                self.canvas.set_annotations(updated)
                self._mark_dirty()
        self._current_tag = new_name
        self._update_classes()
        self.status_message.emit(f"已重命名「{old_name}」→「{new_name}」")

    def delete_box(self):
        self.canvas.delete_selected()

    def undo(self):
        """撤销上一步标注操作（画框/删除框/移动框）"""
        if not self.canvas.has_image():
            return
        if self.canvas.undo():
            self._mark_dirty()
            self.status_message.emit("已撤销上一步操作")
        else:
            self.status_message.emit("没有可撤销的操作")

    # ---------- 导入 ----------
    def import_images(self):
        if self.project is None:
            return

        # 先选择文件夹（支持整个文件夹导入）
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹（或取消后选择文件）")
        if folder:
            self._import_from_folder(folder)
            return

        # 取消文件夹后改为选择单个/多个文件
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择要导入的图片",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp)",
        )
        if not paths:
            return
        self._import_from_paths(paths)

    def _import_from_folder(self, folder):
        folder_path = Path(folder)
        paths = self._collect_images([folder_path])
        if not paths:
            self.status_message.emit("该文件夹内没有图片文件")
            return
        self._import_from_paths(paths)

    def _import_from_paths(self, paths):
        imported = self.project.import_images(paths)
        if imported:
            self._load_images()
            self.status_message.emit(f"已导入 {len(imported)} 张图片")
        else:
            self.status_message.emit("没有新图片可导入")

    @staticmethod
    def _collect_images(items):
        """从文件/文件夹列表中递归收集图片文件"""
        collected = []
        for item in items:
            p = Path(item)
            if p.is_dir():
                collected.extend(
                    f for f in p.rglob("*")
                    if f.is_file() and f.suffix.lower() in IMAGE_EXTS
                )
            elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                collected.append(p)
        return [str(f) for f in collected]

    # ---------- 拖放导入 ----------
    def dragEnterEvent(self, event):
        if self.project is None:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self.project is None:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if self.project is None:
            event.ignore()
            return
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        images = self._collect_images(paths)
        if not images:
            self.status_message.emit("拖入的内容中没有图片文件")
            return
        self._import_from_paths(images)
