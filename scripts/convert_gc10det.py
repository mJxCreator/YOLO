import xml.etree.ElementTree as ET
import shutil
from pathlib import Path
from sklearn.model_selection import train_test_split

GC10_DIR = Path(r"C:\mProgram\YOLO26\GC10-DET")
LABEL_DIR = GC10_DIR / "lable"
OUTPUT_DIR = Path(r"C:\mProgram\YOLO26\datasets")

CLASS_MAPPING = {
    "1_chongkong": 0,
    "2_hanfeng": 1,
    "3_yueyawan": 2,
    "4_shuiban": 3,
    "5_youban": 4,
    "6_siban": 5,
    "7_yiwu": 6,
    "8_yahen": 7,
    "9_zhehen": 8,
    "10_yaozhe": 9,
    "10_yaozhed": 9,
}

CLASS_NAMES = [
    "chongkong",
    "hanfeng",
    "yueyawan",
    "shuiban",
    "youban",
    "siban",
    "yiwu",
    "yahen",
    "zhehen",
    "yaozhe",
]

def convert_xml_to_yolo(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    size = root.find("size")
    img_w = int(size.find("width").text)
    img_h = int(size.find("height").text)

    yolo_lines = []
    for obj in root.findall("object"):
        name = obj.find("name").text
        if name not in CLASS_MAPPING:
            continue
        class_id = CLASS_MAPPING[name]
        bbox = obj.find("bndbox")
        xmin = float(bbox.find("xmin").text)
        ymin = float(bbox.find("ymin").text)
        xmax = float(bbox.find("xmax").text)
        ymax = float(bbox.find("ymax").text)

        x_center = ((xmin + xmax) / 2) / img_w
        y_center = ((ymin + ymax) / 2) / img_h
        width = (xmax - xmin) / img_w
        height = (ymax - ymin) / img_h

        x_center = max(0.0, min(1.0, x_center))
        y_center = max(0.0, min(1.0, y_center))
        width = max(0.0, min(1.0, width))
        height = max(0.0, min(1.0, height))

        yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

    return yolo_lines, img_w, img_h


def find_image_file(filename):
    stem = Path(filename).stem
    for folder_num in range(1, 11):
        candidate = GC10_DIR / str(folder_num) / f"{stem}.jpg"
        if candidate.exists():
            return candidate
    return None


def convert_dataset():
    out_img_train = OUTPUT_DIR / "images" / "train"
    out_img_val = OUTPUT_DIR / "images" / "val"
    out_lbl_train = OUTPUT_DIR / "labels" / "train"
    out_lbl_val = OUTPUT_DIR / "labels" / "val"

    for p in [out_img_train, out_img_val, out_lbl_train, out_lbl_val]:
        p.mkdir(parents=True, exist_ok=True)
        for f in p.iterdir():
            f.unlink()

    xml_files = sorted(LABEL_DIR.glob("*.xml"))
    print(f"Found {len(xml_files)} XML label files")

    valid_samples = []
    missing_images = []

    for xml_file in xml_files:
        img_file = find_image_file(xml_file.name)
        if img_file is None:
            missing_images.append(xml_file.name)
            continue
        valid_samples.append((xml_file, img_file))

    print(f"Valid samples with images: {len(valid_samples)}")
    if missing_images:
        print(f"Missing images for {len(missing_images)} labels")

    train_samples, val_samples = train_test_split(
        valid_samples, test_size=0.2, random_state=42
    )
    print(f"Train: {len(train_samples)}, Val: {len(val_samples)}")

    for xml_file, img_file in train_samples:
        stem = img_file.stem
        yolo_lines, _, _ = convert_xml_to_yolo(xml_file)
        if not yolo_lines:
            continue
        shutil.copy2(img_file, out_img_train / img_file.name)
        with open(out_lbl_train / f"{stem}.txt", "w") as f:
            f.write("\n".join(yolo_lines) + "\n")

    for xml_file, img_file in val_samples:
        stem = img_file.stem
        yolo_lines, _, _ = convert_xml_to_yolo(xml_file)
        if not yolo_lines:
            continue
        shutil.copy2(img_file, out_img_val / img_file.name)
        with open(out_lbl_val / f"{stem}.txt", "w") as f:
            f.write("\n".join(yolo_lines) + "\n")

    train_imgs = len(list(out_img_train.iterdir()))
    val_imgs = len(list(out_img_val.iterdir()))
    train_lbls = len(list(out_lbl_train.iterdir()))
    val_lbls = len(list(out_lbl_val.iterdir()))

    print(f"\n=== Conversion Complete ===")
    print(f"Train images: {train_imgs}, labels: {train_lbls}")
    print(f"Val images:   {val_imgs}, labels: {val_lbls}")
    print(f"Classes: {len(CLASS_NAMES)}")
    for i, name in enumerate(CLASS_NAMES):
        count = 0
        for lbl_dir in [out_lbl_train, out_lbl_val]:
            for f in lbl_dir.glob("*.txt"):
                with open(f) as fh:
                    count += sum(1 for line in fh if line.startswith(f"{i} "))
        print(f"  {i}: {name} - {count} instances")


if __name__ == "__main__":
    convert_dataset()
