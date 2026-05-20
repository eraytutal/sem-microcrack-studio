# Demo Checklist

Use this checklist to verify a fresh Windows demo install of SEM Microcrack Studio.

## Fresh Clone Setup

1. Clone the repository.
2. Open PowerShell in the project folder.
3. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

4. Install dependencies:

```powershell
pip install -r requirements.txt
```

5. Start the app:

```powershell
python app.py
```

Expected result: the SEM Microcrack Studio main window opens on Assisted Review.

## Windows Launcher Test

1. Start from a fresh clone.
2. Double-click `setup_windows.bat`.
3. Confirm `.venv` is created.
4. Confirm dependencies install without errors.
5. Confirm these folders are created:

```text
data/
data/annotations/
data/predictions/
data/exports/
logs/
```

6. Double-click `run_app_hidden.vbs`.
7. Confirm the app opens without a visible cmd window.
8. Confirm no Traceback appears.
9. Double-click `run_app.bat` if a visible-console launcher needs to be checked.
10. If the app does not open, run `run_app_debug.bat` or check `logs/app_run.log`.

## Demo Data

Prepare local demo folders. Do not add large SEM datasets to the repository.

For demo data package preparation, see `docs/DEMO_DATA_PACKAGE.md`.

```text
demo_data/images/
demo_data/labels/
```

Use matching stems for images and YOLO-seg label txt files:

```text
demo_data/images/1.tif
demo_data/labels/1.txt
```

Example label line:

```text
0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87
```

## Assisted Review

1. Click Open Folder and select `demo_data/images/`.
2. Confirm the first image appears in the viewer.
3. Click Import Prediction Folder and select `demo_data/labels/`.
4. Confirm matching prediction overlays and Model Suggestions appear for images with valid labels.
5. Confirm empty or missing label files do not crash the app.
6. Select a prediction and click Accept.
7. Select another prediction and click Reject.
8. Confirm Unsaved review changes appears.
9. Click Save Review.
10. Confirm the review state changes to All review changes saved.

Expected generated files:

```text
data/predictions/<image_stem>.json
data/annotations/<image_stem>.json
```

Accepted predictions should appear in `data/annotations/` only after Save Review.

## Manual Annotation

1. Switch to Manual Annotation.
2. Confirm accepted polygon annotations load for the current image.
3. Select Rectangle and draw a rectangle.
4. Confirm the rectangle appears as a pending annotation.
5. Set a label and click Add Annotation.
6. Edit the label, exportable flag, or notes for a selected annotation.
7. Confirm Unsaved changes appears.
8. Click Save.
9. Navigate away and back to confirm saved annotations reload.

## No Defect Review

1. Open an image with no confirmed annotations.
2. In Manual Annotation, click Mark as No Defect.
3. Confirm Save becomes available.
4. Click Save.
5. Confirm the JSON contains `image_status: "reviewed_no_defect"` and an empty `annotations` array.
6. Click Clear No Defect, save again, and confirm the image returns to unreviewed unless annotations are added.

## Dataset Dashboard

1. Open an image folder.
2. Switch to Dataset.
3. Confirm Total Images matches the supported images in the loaded folder.
4. Confirm Annotated, No Defect, and Unreviewed counts match saved JSON in `data/annotations/`.
5. Save a new annotation or No Defect state, then return to Dataset and confirm counts update.

## YOLO-Seg Export

1. Switch to Dataset.
2. Confirm or choose the output folder, usually `data/exports/yolo_seg`.
3. Keep default split settings unless testing a specific split:

```text
Train 70
Val 20
Test 10
Seed 42
```

4. Click Export YOLO-Seg Dataset.
5. Confirm the export folder is created:

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

6. Confirm source files in `data/annotations/` and `data/predictions/` were not modified by export.

## Generated Data

The app creates these folders on first run if needed:

```text
data/
data/annotations/
data/predictions/
data/exports/
```

Generated annotation, prediction, and export files are ignored by Git.

## Common Troubleshooting

- App does not start: activate `.venv` and reinstall with `pip install -r requirements.txt`.
- Missing QtAwesome icons: reinstall dependencies in the active virtual environment.
- Prediction import is empty: check filename stems and confirm labels use YOLO-seg polygon format, not bbox-only YOLO format.
- Empty label txt files: this is valid and means no predictions for that image.
- Save Review did not create annotations: make sure at least one prediction is accepted before clicking Save Review.
- YOLO export skipped images: unreviewed images are excluded by default; save annotations or mark images as No Defect first.
- Wrong Python opens: run `where python` in PowerShell and confirm it points to the virtual environment while activated.
