# SEM Microcrack Studio v0.1-demo

## Overview

This is the first Python-based demo release of SEM Microcrack Studio.

SEM Microcrack Studio is a desktop tool for SEM microcrack annotation, assisted prediction review, and YOLO segmentation dataset export. This demo does not include real model inference inside the app yet. Real model outputs are imported through the Import Prediction Folder workflow.

## Included Workflows

- Open SEM image folder
- Manual rectangle annotation
- No Defect review workflow
- Import Prediction Folder
- Assisted Review with polygon prediction overlays
- Accept / Reject / Save Review
- Dataset Dashboard
- YOLO-Seg train/val/test export

## Data Flow

- `data/annotations/` stores confirmed manual and operator-reviewed annotations.
- `data/predictions/` stores imported or dummy prediction outputs.
- `data/exports/` stores generated YOLO export datasets.
- Prediction files are not exported directly.
- YOLO export uses confirmed annotations from `data/annotations/`.
- Accepted predictions become annotations only after Save Review.

## Prediction Import Format

Prediction import expects YOLO segmentation txt files:

```text
class_id x1 y1 x2 y2 x3 y3 ... [confidence]
```

Coordinates are normalized between `0` and `1`.

Image and label matching is by filename stem:

```text
10.tif -> 10.txt
```

Default class map:

```text
0 crack
1 scratch
2 pit
3 void
4 uncertain
```

## YOLO-Seg Export

YOLO segmentation export writes this structure:

```text
data/exports/yolo_seg/
  images/train/
  images/val/
  images/test/
  labels/train/
  labels/val/
  labels/test/
  data.yaml
  export_report.json
```

- Rectangle annotations are converted into 4-point polygon labels only during export.
- Polygon annotations are exported directly.
- Source annotation JSON files are not modified.
- No Defect reviewed images are exported as empty-label negative samples by default.
- Unreviewed images are skipped by default.

## Installation

Windows setup:

```powershell
git clone https://github.com/eraytutal/sem-microcrack-studio.git
cd sem-microcrack-studio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Requirements

- Python environment required
- PySide6
- QtAwesome
- No PyTorch, Ultralytics, or CUDA required for this demo

## Validation

- Clean clone test passed.
- App starts from a fresh virtual environment.
- `data/annotations/`, `data/predictions/`, and `data/exports/` are created automatically on first run.
- `v0.1-demo` tag has been pushed.

## Known Limitations

- No real model inference inside the desktop app yet.
- No training inside the app.
- No PyInstaller `.exe` package yet.
- Manual polygon drawing/editing is not implemented yet.
- Real model outputs must be generated externally and imported as YOLO-seg txt files.

## Next Steps

- `demo_data.zip` sample package
- PyInstaller Windows executable
- Real model inference integration
- Manual polygon drawing/editing
- Export option to convert `.tif` images to `.png` if needed for training compatibility
