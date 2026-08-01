import os
import sys
from pathlib import Path

APP_NAME = "材料缺陷检测一体化平台"
APP_VERSION = "0.1.0"
GITHUB_URL = "https://github.com/mJxCreator/YOLO"


def resource_path(rel: str) -> Path:
    """兼容 PyInstaller 打包：返回资源文件的真实路径"""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = Path(__file__).resolve().parent.parent
    return Path(base) / rel

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

COLORS = [
    "#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
    "#dcbeff", "#9A6324", "#fffac8", "#800000", "#aaffc3",
    "#808000", "#ffd8b1", "#000075", "#a9a9a9", "#ffffff",
]


def class_color(index: int) -> str:
    return COLORS[index % len(COLORS)]


def get_image_files(folder: Path):
    if not folder.exists():
        return []
    return sorted(
        [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS],
        key=lambda p: p.name,
    )
