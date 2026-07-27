from ultralytics import YOLO
from pathlib import Path
import cv2
import numpy as np
from typing import Optional

def detect_image(
    model_path: str = "runs/train/yolo26_defect/weights/best.pt",
    source: str = "datasets/images/val",
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    save_dir: str = "runs/detect",
    imgsz: int = 640,
    device: str = "cpu",
):
    model = YOLO(model_path)

    results = model.predict(
        source=source,
        conf=conf_threshold,
        iou=iou_threshold,
        imgsz=imgsz,
        device=device,
        save=True,
        save_txt=True,
        save_conf=True,
        project=save_dir,
        name="defect_results",
        exist_ok=True,
        show_labels=True,
        show_conf=True,
    )

    print(f"Processed {len(results)} images")
    for r in results:
        path = Path(r.path)
        boxes = r.boxes
        if boxes is not None and len(boxes) > 0:
            print(f"  {path.name}: {len(boxes)} defects found")
        else:
            print(f"  {path.name}: no defects")

def detect_video(
    model_path: str = "runs/train/yolo26_defect/weights/best.pt",
    video_path: str = "demo.mp4",
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    save_dir: str = "runs/detect",
    imgsz: int = 640,
    device: str = "cpu",
    output_path: Optional[str] = None,
):
    model = YOLO(model_path)
    cap = cv2.VideoCapture(video_path)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if output_path is None:
        output_path = str(Path(save_dir) / "defect_video_result.mp4")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model.predict(
            frame, conf=conf_threshold, iou=iou_threshold, imgsz=imgsz, device=device
        )

        annotated_frame = results[0].plot()
        out.write(annotated_frame)
        frame_idx += 1

        if frame_idx % 30 == 0:
            print(f"Processing frame {frame_idx}/{total_frames}")

    cap.release()
    out.release()
    print(f"Video result saved to: {output_path}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YOLO26 Material Defect Detection")
    parser.add_argument("--model", type=str, default="runs/train/yolo26_defect/weights/best.pt")
    parser.add_argument("--source", type=str, default="datasets/images/val")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--save-dir", type=str, default="runs/detect")
    parser.add_argument("--video", action="store_true", help="Video detection mode")

    args = parser.parse_args()

    if args.video:
        detect_video(
            model_path=args.model,
            video_path=args.source,
            conf_threshold=args.conf,
            iou_threshold=args.iou,
            save_dir=args.save_dir,
            imgsz=args.imgsz,
            device=args.device,
        )
    else:
        detect_image(
            model_path=args.model,
            source=args.source,
            conf_threshold=args.conf,
            iou_threshold=args.iou,
            save_dir=args.save_dir,
            imgsz=args.imgsz,
            device=args.device,
        )
