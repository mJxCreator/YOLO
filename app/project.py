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

    # ---------- 类别 ----------
    def get_classes(self):
        if self.classes_file.exists():
            return [c.strip() for c in self.classes_file.read_text(encoding="utf-8").splitlines() if c.strip()]
        return []

    def save_classes(self, classes):
        self.classes_file.write_text("\n".join(classes), encoding="utf-8")

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
        cands = list(self.root.glob("*.pt")) + list(Path.cwd().glob("*.pt"))
        bundled = resource_path("yolo26n.pt")
        if bundled.exists() and str(bundled) not in [str(p) for p in cands]:
            cands.append(bundled)
        seen, out = set(), []
        for p in cands:
            if p.name not in seen and p.suffix == ".pt":
                seen.add(p.name)
                out.append(p)
        return out
