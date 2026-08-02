import json
import shutil
from pathlib import Path

from .config import get_image_files, resource_path


class Project:
    """管理单个项目文件夹的结构与数据"""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.images_dir = self.root / "images"
        self.labels_dir = self.root / "labels"
        self.datasets_dir = self.root / "datasets"
        self.runs_dir = self.root / "runs"
        self.classes_file = self.root / "classes.txt"
        self.meta_file = self.root / "project.json"

    # ---------- 创建 / 打开 ----------
    @classmethod
    def create(cls, root: Path):
        p = cls(root)
        p._ensure_structure()
        if not p.meta_file.exists():
            p.meta_file.write_text(
                json.dumps({"name": p.root.name, "created_at": ""}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return p

    @classmethod
    def open(cls, root: Path):
        p = cls(root)
        p._ensure_structure()
        return p

    def _ensure_structure(self):
        self.root.mkdir(parents=True, exist_ok=True)
        for d in [
            self.images_dir,
            self.labels_dir,
            self.datasets_dir,
            self.datasets_dir / "images" / "train",
            self.datasets_dir / "images" / "val",
            self.datasets_dir / "labels" / "train",
            self.datasets_dir / "labels" / "val",
            self.runs_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
        if not self.classes_file.exists():
            self.classes_file.write_text("", encoding="utf-8")

    # ---------- 图片 ----------
    def list_images(self):
        return get_image_files(self.images_dir)

    def import_images(self, paths):
        imported = []
        for p in paths:
            dst = self.images_dir / Path(p).name
            if dst.exists():
                continue
            shutil.copy2(p, dst)
            imported.append(dst)
        return imported

    def delete_image(self, image_path):
        """删除图片及其标签文件，同时清理训练集/验证集中的副本。返回是否删除成功"""
        image_path = Path(image_path)
        removed = False
        if image_path.exists():
            image_path.unlink()
            removed = True
        label = self.get_label_path(image_path)
        if label.exists():
            label.unlink()
        # 清理 datasets 中训练/验证副本
        name = image_path.name
        for sub in ["train", "val"]:
            img = self.datasets_dir / "images" / sub / name
            if img.exists():
                img.unlink()
            lab = self.datasets_dir / "labels" / sub / name.replace(image_path.suffix, ".txt")
            if lab.exists():
                lab.unlink()
        return removed

    # ---------- 类别 ----------
    def get_classes(self):
        if self.classes_file.exists():
            return [c.strip() for c in self.classes_file.read_text(encoding="utf-8").splitlines() if c.strip()]
        return []

    def save_classes(self, classes):
        self.classes_file.write_text("\n".join(classes), encoding="utf-8")

    # ---------- 类别颜色 ----------
    def get_class_colors(self):
        """返回 {类别名: 颜色字符串} 映射"""
        if self.meta_file.exists():
            try:
                meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
                return meta.get("class_colors", {})
            except Exception:
                return {}
        return {}

    def save_class_color(self, name, color):
        colors = self.get_class_colors()
        colors[name] = color
        self._save_meta({"class_colors": colors})

    def remove_class_color(self, name):
        colors = self.get_class_colors()
        if name in colors:
            del colors[name]
            self._save_meta({"class_colors": colors})

    def rename_class_color(self, old_name, new_name):
        colors = self.get_class_colors()
        if old_name in colors:
            colors[new_name] = colors.pop(old_name)
            self._save_meta({"class_colors": colors})

    def _save_meta(self, update: dict):
        meta = {}
        if self.meta_file.exists():
            try:
                meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        meta.update(update)
        self.meta_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---------- 标签 ----------
    def get_label_path(self, image_path):
        return self.labels_dir / (Path(image_path).stem + ".txt")

    # ---------- 模型 ----------
    def get_trained_models(self):
        models = []
        if self.runs_dir.exists():
            for w in self.runs_dir.rglob("best.pt"):
                models.append(w)
        return sorted(models, key=lambda p: p.stat().st_mtime, reverse=True)

    def get_pretrained_models(self):
        cands = [p.resolve() for p in (list(self.root.glob("*.pt")) + list(Path.cwd().glob("*.pt")))]
        bundled = resource_path("yolo26n.pt")
        if bundled.exists() and str(bundled) not in [str(p) for p in cands]:
            cands.append(bundled)
        seen, out = set(), []
        for p in cands:
            if p.name not in seen and p.suffix == ".pt":
                seen.add(p.name)
                out.append(p)
        return out
