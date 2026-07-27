from ultralytics import YOLO
import torch

def train_advanced():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    model = YOLO("yolo26n.pt")

    model.train(
        data="data.yaml",
        epochs=300,
        batch=16,
        imgsz=640,
        device=device,
        workers=4,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3,
        warmup_momentum=0.8,
        warmup_bias_lr=0.1,
        box=7.5,
        cls=0.5,
        dfl=1.5,
        augment=True,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        shear=2.0,
        perspective=0.0,
        flipud=0.1,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        copy_paste=0.1,
        auto_augment="randaugment",
        erasing=0.4,
        crop_fraction=1.0,
        patience=50,
        freeze=None,
        save=True,
        save_period=10,
        val=True,
        project="runs/train",
        name="yolo26_defect_advanced",
        exist_ok=True,
        pretrained=True,
        verbose=True,
        seed=42,
        deterministic=True,
        single_cls=False,
        rect=False,
        cos_lr=True,
        close_mosaic=10,
        resume=False,
        amp=True,
        fraction=1.0,
        profile=False,
        overlap_mask=True,
        mask_ratio=4,
        dropout=0.0,
        val_period=1,
    )

    print("Advanced training complete!")

    metrics = model.val()
    print(f"mAP50: {metrics.box.map50:.4f}")
    print(f"mAP50-95: {metrics.box.map:.4f}")

    onnx_path = model.export(format="onnx", imgsz=640, half=True)
    print(f"ONNX exported: {onnx_path}")

    engine_path = model.export(format="engine", imgsz=640, half=True)
    print(f"TensorRT exported: {engine_path}")

if __name__ == "__main__":
    train_advanced()
