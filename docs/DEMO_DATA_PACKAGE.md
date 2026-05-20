# Demo Data Package

SEM Microcrack Studio demo data is distributed separately from the repository. The repository should not include real SEM images, prediction label txt files, or generated zip archives unless that is explicitly decided later.

Suggested archive name:

```text
demo_data_v0.1-demo.zip
```

Suggested archive structure:

```text
demo_data_v0.1-demo/
  images/
  prediction_labels/
  README_DEMO_DATA.md
```

## Local Source Mapping

Local source folders:

```text
C:\Users\User\Desktop\Demo-dataset\test
C:\Users\User\Desktop\Demo-dataset\app_import_labels_baseline_50ep_test_16
```

Package target folders:

```text
demo_data_v0.1-demo/images
demo_data_v0.1-demo/prediction_labels
```

Mapping:

```text
test -> images
app_import_labels_baseline_50ep_test_16 -> prediction_labels
```

## Manual Package Build

Build the package outside the repository, for example on the Desktop:

1. Create a folder named `demo_data_v0.1-demo`.
2. Copy SEM image files from `C:\Users\User\Desktop\Demo-dataset\test` into `demo_data_v0.1-demo\images`.
3. Copy prediction txt files from `C:\Users\User\Desktop\Demo-dataset\app_import_labels_baseline_50ep_test_16` into `demo_data_v0.1-demo\prediction_labels`.
4. Add `README_DEMO_DATA.md` using the template below.
5. Zip the folder as `demo_data_v0.1-demo.zip`.
6. Attach the zip to a GitHub Release asset if it should be shared.

Do not copy the package folder or zip into Git tracking.

## README_DEMO_DATA.md Template

Suggested contents for `demo_data_v0.1-demo/README_DEMO_DATA.md`:

~~~markdown
# SEM Microcrack Studio Demo Data

This package contains SEM demo images and prediction label txt files for SEM Microcrack Studio.

## Folders

- `images/`: SEM image files.
- `prediction_labels/`: YOLO-seg normalized polygon prediction txt files.

## How To Use

1. Open SEM Microcrack Studio.
2. In Assisted Review, click Open Folder and select `images/`.
3. Click Import Prediction Folder and select `prediction_labels/`.
4. Empty label files are valid and mean no predictions for that image.
5. Missing label files are valid and do not block the demo.
6. Extra label files are ignored when they do not match a loaded image stem.
7. Accept or reject predictions.
8. Click Save Review.
9. Use Dataset -> YOLO-Seg Export to create a train/val/test export.

## Prediction Label Format

Prediction labels use YOLO-seg normalized polygon txt format:

`class_id x1 y1 x2 y2 x3 y3 ... [confidence]`

Coordinates are normalized between `0` and `1`.
~~~

## Prediction Label Format

Demo prediction labels are YOLO-seg normalized polygon txt files:

```text
class_id x1 y1 x2 y2 x3 y3 ... [confidence]
```

Coordinates are normalized between `0` and `1`.

Image and label matching is by filename stem. For example:

```text
images/10.tif -> prediction_labels/10.txt
```

Empty label files are valid. Missing label files are valid. Extra label files are ignored.

## Demo Validation Checklist

- `images/` folder selected successfully in Assisted Review.
- `prediction_labels/` imported successfully.
- Polygon overlays appear for matching files with valid labels.
- Empty label files do not crash the app.
- Missing label files do not crash the app.
- Accepted predictions save into `data/annotations/` only after Save Review.
- YOLO-Seg export works from the Dataset page.

## Git Safety

Keep demo data package outputs out of Git:

- `demo_data/`
- `demo_data_*/`
- `*.zip`

Generated app data also remains local:

- `data/annotations/*.json`
- `data/predictions/*.json`
- `data/exports/`
