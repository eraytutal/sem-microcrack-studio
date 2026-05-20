# SEM Microcrack Studio

SEM Microcrack Studio is a Python desktop tool for SEM microcrack annotation, assisted model prediction review, and YOLO segmentation dataset export.

The current demo is Python-based. It does not include real model inference, training, PyTorch, Ultralytics, CUDA, or PyInstaller packaging.

## Main Workflows

- Manual Annotation: draw and confirm rectangle annotations, edit labels and notes, and save confirmed annotations to JSON.
- No Defect Review: explicitly mark reviewed images with no visible defect.
- Assisted Review: inspect imported or dummy polygon predictions without mixing them with manual annotations.
- Import Prediction Folder: load YOLO-seg label txt files matched to the currently opened image folder by filename stem.
- Accept / Reject / Save Review: review prediction decisions in memory, then persist accepted predictions only when Save Review is clicked.
- Dataset Dashboard: inspect image review status and annotation counts.
- YOLO-Seg Export: export confirmed annotations into train/val/test YOLO segmentation folders.

## Installation On Windows

```powershell
git clone https://github.com/eraytutal/sem-microcrack-studio.git
cd sem-microcrack-studio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Windows One-Click Demo Startup

Python must still be installed on the Windows computer.

First-time setup:

```text
setup_windows.bat
```

The setup script creates `.venv`, installs `requirements.txt`, and creates the local `data/` and `logs/` folders.

Normal no-console startup:

```text
run_app_hidden.vbs
```

Visible-console startup:

```text
run_app.bat
```

Debug startup with console:

```text
run_app_debug.bat
```

Generated annotation, prediction, export, and log files remain local and are ignored by Git.

## Quick Start

1. Open Assisted Review.
2. Click Open Folder and choose a folder of SEM images.
3. Click Import Prediction Folder to load YOLO-seg txt outputs, or Run Dummy Detection for demo predictions.
4. Accept or reject predictions, then click Save Review.
5. Use Manual Annotation to add rectangle annotations or mark images as No Defect.
6. Use Dataset to review status counts and export a YOLO-Seg dataset.

## Project Folders

- `data/annotations/`: confirmed manual and operator-reviewed annotations. Accepted model predictions are written here only after Save Review.
- `data/predictions/`: dummy, imported, or future model prediction outputs and their review statuses.
- `data/exports/`: generated dataset exports, including YOLO segmentation exports.

Generated JSON and export files are ignored by Git. They are local working data, not source files.

## Prediction Import Format

Prediction import expects YOLO segmentation text files with normalized polygon coordinates:

```text
class_id x1 y1 x2 y2 x3 y3 ... [confidence]
```

Coordinates should be normalized between `0` and `1`. The optional final value is interpreted as confidence when present.

Default class map:

```text
0 crack
1 scratch
2 pit
3 void
4 uncertain
```

Example label line:

```text
0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87
```

## YOLO-Seg Export

YOLO segmentation export writes to:

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

Only confirmed annotations from `data/annotations/` are exported. Prediction files in `data/predictions/` are not exported directly. Rectangle annotations are converted to polygon labels only during export; source annotation JSON files are not modified.

By default, no-defect reviewed images are exported as negative samples with empty label files, and unreviewed images are skipped.

## Demo Data

Demo data is not included by default. Prepare local folders such as:

```text
demo_data/images/
demo_data/labels/
```

Image files can use `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, or `.tiff`. Prediction label files should have matching stems, for example:

```text
demo_data/images/11.tif
demo_data/labels/11.txt
```

## Demo Data Package

Demo data is not stored in the repository. If available, download `demo_data_v0.1-demo.zip` from the GitHub Release assets. See `docs/DEMO_DATA_PACKAGE.md` for packaging instructions and the expected `images/` and `prediction_labels/` folder layout.

## Useful Commands

```powershell
python scripts/import_model_predictions.py --image-dir "C:\path\to\images" --label-dir "C:\path\to\labels"
python scripts/export_yolo_seg_dataset.py --image-dir "C:\path\to\images" --output-dir "data\exports\yolo_seg"
```

## Demo Validation

Use `docs/DEMO_CHECKLIST.md` for the full fresh-install and workflow validation checklist.

## Troubleshooting

- If the app does not start, confirm the virtual environment is active and run `pip install -r requirements.txt` again.
- If icons are missing, confirm `QtAwesome` installed successfully in the active virtual environment.
- If prediction import shows no suggestions, check that label txt filenames match image stems and contain YOLO-seg polygon lines.
- Empty label files are valid and mean no predictions were imported for that image.
- If YOLO export creates few or no labels, check that images are annotated or marked No Defect and that annotations are saved.
