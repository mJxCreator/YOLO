from ultralytics import YOLO
from pathlib import Path
import torch

def train():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    model = YOLO("yolo26n.pt")

    results = model.train(
        data="data.yaml",
        epochs=200,
        batch=16,
        imgsz=640,
        device=device,
        workers=4,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        weight_decay=0.0005,
        warmup_epochs=3,
        augment=True,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        shear=2.0,
        flipud=0.1,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        copy_paste=0.1,
        patience=50,
        save=True,
        save_period=10,
        project="runs/train",
        name="yolo26_defect",
        exist_ok=True,
        pretrained=True,
        verbose=True,
        val=True,
    )

    print("Training complete!")
    print(f"Best model saved at: {results.save_dir}")

    metrics = model.val()
    print(f"mAP50: {metrics.box.map50:.4f}")
    print(f"mAP50-95: {metrics.box.map:.4f}")

    path = model.export(format="onnx", imgsz=640)
    print(f"Model exported to ONNX: {path}")

if __name__ == "__main__":
    train()
