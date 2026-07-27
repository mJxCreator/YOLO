from pathlib import Path
import random
import shutil
from sklearn.model_selection import train_test_split

def split_dataset(
    images_dir: str = "raw_images",
    labels_dir: str = "raw_labels",
    output_dir: str = "datasets",
    train_ratio: float = 0.8,
    val_ratio: float = 0.2,
    seed: int = 42,
):
    random.seed(seed)
    images_path = Path(images_dir)
    labels_path = Path(labels_dir)

    out_images_train = Path(output_dir) / "images" / "train"
    out_images_val = Path(output_dir) / "images" / "val"
    out_labels_train = Path(output_dir) / "labels" / "train"
    out_labels_val = Path(output_dir) / "labels" / "val"

    for p in [out_images_train, out_images_val, out_labels_train, out_labels_val]:
        p.mkdir(parents=True, exist_ok=True)

    image_files = sorted(images_path.glob("*"))
    print(f"Found {len(image_files)} images")

    train_files, val_files = train_test_split(
        image_files, test_size=val_ratio, random_state=seed
    )
    print(f"Train: {len(train_files)}, Val: {len(val_files)}")

    for img_file in train_files:
        shutil.copy2(img_file, out_images_train / img_file.name)
        label_file = labels_path / f"{img_file.stem}.txt"
        if label_file.exists():
            shutil.copy2(label_file, out_labels_train / label_file.name)

    for img_file in val_files:
        shutil.copy2(img_file, out_images_val / img_file.name)
        label_file = labels_path / f"{img_file.stem}.txt"
        if label_file.exists():
            shutil.copy2(label_file, out_labels_val / label_file.name)

    print("Dataset split complete!")
    print(f"  Train images: {len(list(out_images_train.iterdir()))}")
    print(f"  Val images:   {len(list(out_images_val.iterdir()))}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Split dataset into train/val sets")
    parser.add_argument("--images", type=str, default="raw_images", help="Raw images directory")
    parser.add_argument("--labels", type=str, default="raw_labels", help="Raw labels directory")
    parser.add_argument("--output", type=str, default="datasets", help="Output directory")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Training ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    split_dataset(
        images_dir=args.images,
        labels_dir=args.labels,
        output_dir=args.output,
        train_ratio=args.train_ratio,
        seed=args.seed,
    )
