from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
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
from .config import IMAGE_EXTS, class_color
from .yolo_format import load_yolo_labels, save_yolo_labels


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
        self.tag_list.setFixedHeight(110)
        self.tag_list.setAcceptDrops(False)
        self.tag_list.itemClicked.connect(self._on_pick_tag)
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
        self.canvas.boxes_changed.connect(self._mark_dirty)
        self.canvas.image_loaded.connect(self._on_image_loaded)
        self.canvas.setAcceptDrops(False)
        rv.addWidget(self.canvas, 1)

        toolbar = QHBoxLayout()
        self.btn_draw = QPushButton("画框 (W)")
        self.btn_draw.setCheckable(True)
        self.btn_draw.toggled.connect(self.canvas.set_draw_mode)
        self.canvas.draw_mode_changed.connect(self.btn_draw.setChecked)

        self.btn_delete_box = QPushButton("删除框 (Del)")
        self.btn_delete_box.clicked.connect(self.delete_box)

        self.btn_save = QPushButton("保存 (Ctrl+S)")
        self.btn_save.setStyleSheet("QPushButton { background: #2d8cf0; color: white; }")
        self.btn_save.clicked.connect(self.save_labels)

        toolbar.addWidget(self.btn_draw)
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
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_box)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_labels)

    def toggle_draw_mode(self):
        self.canvas.set_draw_mode(not self.canvas.draw_mode)

    # ---------- 项目绑定 ----------
    def set_project(self, project):
        self.project = project
        self._load_images()
        self._update_classes()

    def _update_classes(self):
        classes = self.project.get_classes()
        self.canvas.set_class_names(classes)
        current = self.canvas.current_label()
        self.tag_list.clear()
        for name in classes:
            self.tag_list.addItem(QListWidgetItem(name))
        if current and current in classes:
            rows = self.tag_list.findItems(current, Qt.MatchExactly)
            if rows:
                self.tag_list.setCurrentItem(rows[0])
        elif classes:
            self.tag_list.setCurrentRow(0)
            self.canvas.set_current_label(classes[0])

    def _on_pick_tag(self, item):
        """点击左侧标签列表，选择当前要画的标签"""
        self.canvas.set_current_label(item.text())
        self.status_message.emit(f"当前标签: {item.text()}")

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
        boxes = load_yolo_labels(label_path, w, h)
        classes = self.project.get_classes()
        labeled = []
        for rect, cls_id in boxes:
            label = classes[cls_id] if cls_id < len(classes) else f"cls_{cls_id}"
            labeled.append((rect, label))
        self.canvas.set_boxes(labeled)

    def _on_new_box(self, rect, label):
        self._mark_dirty()

    def _mark_dirty(self):
        self._dirty = True

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
        boxes = []
        for rect, label in self.canvas.get_boxes():
            cls_id = class_to_id.get(label, 0)
            boxes.append((rect, cls_id))
        img_path = self.image_list[self.current_index]
        label_path = self.project.get_label_path(img_path)
        save_yolo_labels(label_path, boxes, w, h)
        self._dirty = False
        self.status_message.emit(f"已保存 {len(boxes)} 个标注 → {label_path.name}")

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
        self.canvas.set_current_label(name)
        rows = self.tag_list.findItems(name, Qt.MatchExactly)
        if rows:
            self.tag_list.setCurrentItem(rows[0])
        self.status_message.emit(f"已添加标签「{name}」")

    def delete_class(self):
        if self.project is None:
            return
        item = self.tag_list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先在左侧标签列表中选择要删除的标签")
            return
        name = item.text()
        ret = QMessageBox.question(
            self, "删除标签",
            f"确定删除标签「{name}」？\n当前图片中该标签的标注框也会被删除。",
        )
        if ret != QMessageBox.Yes:
            return
        classes = self.project.get_classes()
        classes = [c for c in classes if c != name]
        self.project.save_classes(classes)
        # 删除当前图片中该标签的标注框
        if self.canvas.has_image():
            boxes = self.canvas.get_boxes()
            kept = [(r, l) for r, l in boxes if l != name]
            if len(kept) != len(boxes):
                self.canvas.set_boxes(kept)
                self._mark_dirty()
        self._update_classes()
        self.status_message.emit(f"已删除标签「{name}」")

    def rename_class(self):
        """重命名左侧标签列表中选中的标签，保留其在类别列表中的位置（类ID不变）"""
        if self.project is None:
            return
        item = self.tag_list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先在左侧标签列表中选择要重命名的标签")
            return
        old_name = item.text()
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
        # 同步更新画布上该标签的标注框
        if self.canvas.has_image():
            boxes = self.canvas.get_boxes()
            changed = False
            updated = []
            for rect, label in boxes:
                if label == old_name:
                    updated.append((rect, new_name))
                    changed = True
                else:
                    updated.append((rect, label))
            if changed:
                self.canvas.set_boxes(updated)
                self._mark_dirty()
        self._update_classes()
        self.status_message.emit(f"已重命名「{old_name}」→「{new_name}」")

    def delete_box(self):
        self.canvas.delete_selected()

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
