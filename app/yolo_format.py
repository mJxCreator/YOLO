from PySide6.QtCore import QPointF, QRectF


def rect_to_yolo(rect: QRectF, img_w: float, img_h: float, class_id: int) -> str:
    xc = (rect.x() + rect.width() / 2) / img_w
    yc = (rect.y() + rect.height() / 2) / img_h
    w = rect.width() / img_w
    h = rect.height() / img_h
    return f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}"


def yolo_to_rect(line: str, img_w: float, img_h: float):
    """解析 YOLO 框格式（class cx cy w h），非框格式返回 None"""
    parts = line.split()
    if len(parts) != 5:
        return None
    class_id = int(float(parts[0]))
    xc = float(parts[1]) * img_w
    yc = float(parts[2]) * img_h
    w = float(parts[3]) * img_w
    h = float(parts[4]) * img_h
    rect = QRectF(xc - w / 2, yc - h / 2, w, h)
    return class_id, rect


def poly_to_yolo(points, img_w: float, img_h: float, class_id: int) -> str:
    parts = []
    for p in points:
        x = max(0.0, min(1.0, p.x() / img_w))
        y = max(0.0, min(1.0, p.y() / img_h))
        parts.append(f"{x:.6f} {y:.6f}")
    return f"{class_id} " + " ".join(parts)


def yolo_to_poly(line: str, img_w: float, img_h: float):
    """解析 YOLO 分割格式（class x1 y1 x2 y2 ...），非多边形格式返回 None"""
    parts = line.split()
    if len(parts) < 7:
        return None
    rest = parts[1:]
    if len(rest) % 2 != 0:
        return None
    class_id = int(float(parts[0]))
    points = []
    for i in range(0, len(rest), 2):
        points.append(QPointF(float(rest[i]) * img_w, float(rest[i + 1]) * img_h))
    return class_id, points


def load_yolo_labels(label_path, img_w: float, img_h: float):
    """读取标签文件，返回 list of ("box", class_id, QRectF) 或 ("poly", class_id, [QPointF])"""
    items = []
    if not label_path or not label_path.exists():
        return items
    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = yolo_to_rect(line, img_w, img_h)
        if parsed is not None:
            items.append(("box", parsed[0], parsed[1]))
            continue
        parsed = yolo_to_poly(line, img_w, img_h)
        if parsed is not None:
            items.append(("poly", parsed[0], parsed[1]))
    return items


def save_yolo_labels(label_path, items, img_w: float, img_h: float):
    """写入标签文件；items: list of ("box", class_id, QRectF) 或 ("poly", class_id, [QPointF])"""
    lines = []
    for kind, class_id, data in items:
        if kind == "poly":
            lines.append(poly_to_yolo(data, img_w, img_h, class_id))
        else:
            lines.append(rect_to_yolo(data, img_w, img_h, class_id))
    label_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
