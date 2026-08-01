# YOLO26 目标检测一体化平台

基于 [Ultralytics YOLO26](https://docs.ultralytics.com/models/yolo26) 的一站式目标检测平台，内置**数据标注 → 数据集划分 → 模型训练 → 推理检测**全流程。类别体系完全开放自定义，适用于缺陷检测、工业质检、安全监控、物体识别等任意目标检测场景，不局限于特定领域。

## 特性

- **YOLO26 架构**：端到端无 NMS 目标检测，速度更快、部署更轻量
- **开放类别体系**：标签可视化管理系统，可任意新增/重命名/删除类别，并为每个类别自定义颜色，适用于任意目标检测任务
- **支持多种输入**：单张图片、批量图片、视频流、摄像头
- **模型导出**：支持导出为 ONNX / TensorRT 格式，方便边缘端部署
- **轻量启动**：默认使用 yolo26n（Nano）模型，快速上手

> 💡 虽然项目最初面向材料缺陷检测，但核心能力（标注、训练、推理）与具体类别完全解耦，只需在 [data.yaml](file:///c:/mProgram/YOLO26/data.yaml) 中替换类别名即可用于其他领域，如 PCB 缺陷、农作物病害、车辆/行人识别等。

## 环境要求

- Python >= 3.10
- 推荐使用 [uv](https://docs.astral.sh/uv/) 管理项目依赖

## 使用方式

系统提供两种使用方式：

### 方式一：图形界面应用（推荐）

集成了**人工标注 → 数据集划分 → 模型训练 → 推理检测**全流程的一站式桌面应用：

```bash
uv run python main.py
```

进入应用后可完成以下操作：

1. **启动界面**：新建项目 / 打开历史项目
2. **标注界面**：导入图片（支持整个文件夹批量导入，也可直接拖拽文件/文件夹）→ 管理自定义标签（新增/重命名/删除，每个标签独立配色）→ 画框标注（快捷键 W 画框、A/D 切换图片、Ctrl+S 保存）
3. **训练界面**：一键划分数据集（默认 80/20）→ 配置参数 → 开始训练（后台运行，实时日志，自动检测 GPU/CPU）
4. **检测界面**：图片/文件夹/视频/摄像头检测，结果可视化

打包为可执行程序（无需安装 Python）：

```bash
build.bat
```

打包产物在 `dist/` 目录，将整个目录分发给其他电脑即可使用。

### 方式二：命令行脚本

#### 1. 安装依赖

```bash
uv sync
```

#### 2. 下载预训练模型

首次运行时会自动下载 `yolo26n.pt`，也可以手动下载：

```bash
uv run python -c "from ultralytics import YOLO; YOLO('yolo26n.pt')"
```

#### 3. 验证安装

```bash
uv run python -c "from ultralytics import YOLO; model = YOLO('yolo26n.pt'); print('YOLO26 ready')"
```

## 数据集准备

### 数据集结构

将你的数据集按照 YOLO 格式组织：

```
raw_images/          # 原始图片
  ├── img_001.jpg
  ├── img_002.jpg
  └── ...
raw_labels/          # 原始标签 (YOLO格式)
  ├── img_001.txt
  ├── img_002.txt
  └── ...
```

标签文件为 YOLO 格式的纯文本文件，每行格式：

```
<class_id> <x_center> <y_center> <width> <height>
```

坐标值为归一化到 [0, 1] 的浮点数。

### 数据集划分

```bash
uv run scripts/split_data.py --images raw_images --labels raw_labels
```

默认按 80% / 20% 划分训练集和验证集。

### 配置数据

根据你的目标类别修改 [data.yaml](file:///c:/mProgram/YOLO26/data.yaml)：

```yaml
path: ./datasets
train: images/train
val: images/val

nc: 4                              # 类别数量
names:                             # 类别名称
  0: crack
  1: scratch
  2: hole
  3: dent
```

## 训练

### 基础训练

```bash
uv run scripts/train.py
```

### 高级训练

```bash
uv run scripts/train_advanced.py
```

### 训练参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `epochs` | 200/300 | 训练轮数 |
| `batch` | 16 | 批次大小 |
| `imgsz` | 640 | 输入图片尺寸 |
| `optimizer` | AdamW | 优化器 |
| `lr0` | 0.001 | 初始学习率 |
| `patience` | 50 | 早停等待轮数 |

训练完成后，最佳模型保存在 `runs/train/yolo26_defect/weights/best.pt`。

## 推理检测

### 图片检测

```bash
# 检测单张图片
uv run scripts/detect.py --source path/to/image.jpg

# 检测整个目录
uv run scripts/detect.py --source datasets/images/val

# 指定模型和置信度阈值
uv run scripts/detect.py --model runs/train/yolo26_defect/weights/best.pt --source test.jpg --conf 0.3
```

### 视频检测

```bash
uv run scripts/detect.py --source demo.mp4 --video
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model` | `runs/train/yolo26_defect/weights/best.pt` | 模型路径 |
| `--source` | `datasets/images/val` | 输入源（图片/目录/视频） |
| `--conf` | 0.25 | 置信度阈值 |
| `--iou` | 0.45 | NMS IoU 阈值 |
| `--imgsz` | 640 | 推理图片尺寸 |
| `--device` | cpu | 推理设备（cpu / cuda:0） |
| `--video` | - | 启用视频模式 |

## 模型导出

训练完成后会自动导出 ONNX 格式，也可手动导出：

```python
from ultralytics import YOLO
model = YOLO("runs/train/yolo26_defect/weights/best.pt")

# 导出 ONNX
model.export(format="onnx", imgsz=640)

# 导出 TensorRT（需要 GPU）
model.export(format="engine", imgsz=640, half=True)
```

## 项目结构

```
├── main.py                   # GUI 应用入口（推荐使用）
├── app/                      # GUI 应用代码
│   ├── home_window.py        # 启动界面
│   ├── main_window.py        # 主窗口
│   ├── annotate_page.py      # 标注界面
│   ├── canvas.py             # 标注画布
│   ├── color_dialog.py       # 极简颜色选择器
│   ├── project.py            # 项目管理（图片/标签/类别颜色）
│   ├── train_page.py         # 训练界面
│   ├── detect_page.py        # 检测界面
│   └── ...
├── scripts/
│   ├── train.py              # 训练脚本
│   ├── train_advanced.py     # 高级训练脚本
│   ├── detect.py             # 推理脚本
│   ├── split_data.py         # 数据集划分工具
│   └── convert_gc10det.py    # GC10-DET 数据转换工具
├── docs/
│   └── 需求分析.md            # 需求文档
├── data.yaml                 # 数据集配置
├── pyproject.toml            # 项目依赖配置
├── build.spec                # PyInstaller 打包配置
├── build.bat                 # 一键打包脚本
├── datasets/                 # 数据集目录（不纳入版本控制）
│   ├── images/
│   │   ├── train/            # 训练图片
│   │   └── val/              # 验证图片
│   └── labels/
│       ├── train/            # 训练标签
│       └── val/              # 验证标签
└── runs/                     # 训练和推理输出（不纳入版本控制）
```

## 常见问题

### 如何适配我的目标类别？

编辑 [data.yaml](file:///c:/mProgram/YOLO26/data.yaml) 中的 `nc` 和 `names` 字段，修改为你实际的类别名称和数量即可，无需改动任何代码。GUI 标注界面中也可直接通过「新增/重命名/删除」按钮实时管理类别。

### 训练时显存不足怎么办？

- 降低 `batch` 大小（如从 16 改为 8）
- 降低 `imgsz`（如从 640 改为 416）
- 使用更小的模型版本（默认 yolo26n 已是最小版本）

### 如何提升检测精度？

- 增加训练数据量和多样性
- 使用数据增强（训练脚本已内置 mosaic、mixup、copy-paste 等）
- 调大 `epochs` 训练轮数
- 收集更多代表性目标样本

### 提示 86 80 错误

如果遇到 WinError 86 或 80 报错，请检查数据集路径中是否存在无效文件（如系统隐藏文件 `desktop.ini`），清理后再运行。

## 参考

- [Ultralytics YOLO26 文档](https://docs.ultralytics.com/models/yolo26)
- [Ultralytics GitHub](https://github.com/ultralytics/ultralytics)
- [YOLO26 Industrial Vision](https://github.com/sjsr-0401/yolo26-industrial-vision)
