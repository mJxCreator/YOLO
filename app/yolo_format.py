from PySide6.QtCore import QRectF


def rect_to_yolo(rect: QRectF, img_w: float, img_h: float, class_id: int) -> str:
    xc = (rect.x() + rect.width() / 2) / img_w
    yc = (rect.y() + rect.height() / 2) / img_h
    w = rect.width() / img_w
    h = rect.height() / img_h
    xc = max(0.0, min(1.0, xc))
    yc = max(0.0, min(1.0, yc))
    w = max(0.0, min(1.0, w))
    h = max(0.0, min(1.0, h))
    return f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}"


def yolo_to_rect(line: str, img_w: float, img_h: float):
    parts = line.split()
    if len(parts) < 5:
        return None
    class_id = int(float(parts[0]))
    xc = float(parts[1]) * img_w
    yc = float(parts[2]) * img_h
    w = float(parts[3]) * img_w
    h = float(parts[4]) * img_h
    rect = QRectF(xc - w / 2, yc - h / 2, w, h)
    return class_id, rect


def load_yolo_labels(label_path, img_w, img_h):
    boxes = []
    if not label_path or not label_path.exists():
        return boxes
    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = yolo_to_rect(line, img_w, img_h)
        if parsed:
            class_id, rect = parsed
            boxes.append((rect, class_id))
    return boxes


def save_yolo_labels(label_path, boxes, img_w, img_h):
    lines = []
    for rect, class_id in boxes:
        lines.append(rect_to_yolo(rect, img_w, img_h, class_id))
    label_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
