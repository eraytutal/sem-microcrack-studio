# Dataset Status Dashboard Testing

This checklist tests the current Dataset Status Dashboard milestone without adding new features or changing UI design.

## Scope

Relevant code paths:

- `app.py` starts the PySide6 application and opens `MainWindow`.
- `src/main_window.py` opens image folders, tracks the current image list, saves manual annotation JSON, marks images as no defect, and refreshes the dataset page.
- `src/pages/dataset_export_page.py` renders the summary cards and image status table.
- `src/pages/manual_annotation_page.py` exposes save and no-defect actions.
- `src/annotation_io.py` reads and writes annotation JSON files and calculates dataset status counts.
- `src/widgets/image_viewer.py` manages confirmed and pending rectangle annotations.

The dashboard should read annotation JSON from `data/annotations/`. Files matching `data/annotations/*.json` are ignored by Git and should stay uncommitted.

## Preconditions

1. Use a small folder containing supported SEM image files: `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, or `.tiff`.
2. Know the image basenames. Annotation files are matched by image stem, for example `sample.png` reads `data/annotations/sample.json`.
3. Keep temporary JSON changes inside `data/annotations/`, and remove or restore them after testing.
4. Start the app from the project root:

```powershell
python app.py
```

Optional CLI cross-check:

```powershell
python scripts/check_dataset_status.py "C:\Users\User\Desktop\bitirme-veri\datasets\images\test"
```

## Expected Status Rules

- Missing JSON: `Unreviewed`, annotation count `0`.
- Invalid JSON: does not crash the app; treated as `Unreviewed`, annotation count `0`.
- `image_status: "unreviewed"`: `Unreviewed`.
- `image_status: "annotated"`: `Annotated`.
- `image_status: "reviewed_no_defect"`: `No Defect`.
- No `image_status` with one or more annotations: `Annotated`.
- No `image_status` with empty annotations: `Unreviewed`.

## Manual Test Cases

### 1. Opening A Folder

1. Launch the app with `python app.py`.
2. On the Assisted Review page, click the folder open action.
3. Select the SEM image folder.
4. Open the Dataset page from the sidebar.

Expected result:

- The Dataset page shows one table row per supported image in the selected folder.
- Unsupported files are not listed.
- The table is sorted by filename in the same order used by navigation.

### 2. Total Image Count

1. Count supported image files in the selected folder.
2. Compare that number with the `Total Images` card.
3. Optionally run `python scripts/check_dataset_status.py "<image-folder>"`.

Expected result:

- `Total Images` equals the number of supported image files.
- The table row count equals `Total Images`.

### 3. Annotated Count

1. In `data/annotations/`, create or identify JSON files with either:
   - `image_status` set to `"annotated"`, or
   - no `image_status` and a non-empty `annotations` list.
2. Refresh the Dataset page.
3. Compare the `Annotated Images` card with the number of matching images.

Expected result:

- Each matching image appears with status `Annotated`.
- `Annotated Images` equals the number of rows with status `Annotated`.

### 4. No Defect Count

1. In `data/annotations/`, create or identify JSON files with `image_status` set to `"reviewed_no_defect"` and an empty `annotations` list.
2. Refresh the Dataset page.
3. Compare the `No Defect Images` card with the number of matching images.

Expected result:

- Each matching image appears with status `No Defect`.
- `No Defect Images` equals the number of rows with status `No Defect`.

### 5. Unreviewed Count

1. Include at least one image with no matching JSON file.
2. Include at least one image with a JSON file containing an empty `annotations` list and no `image_status`.
3. Refresh the Dataset page.
4. Compare the `Unreviewed Images` card with the number of unreviewed rows.

Expected result:

- Missing JSON images appear as `Unreviewed`.
- Empty annotation JSON with no status appears as `Unreviewed`.
- `Unreviewed Images` equals the number of rows with status `Unreviewed`.

### 6. Annotation Count Per Image

1. Pick an image with a matching JSON file.
2. Count the entries in its `annotations` list.
3. Refresh the Dataset page.
4. Check the image row's `Annotation Count` column.

Expected result:

- The row's annotation count equals the number of items in the JSON `annotations` list.
- A missing, invalid, or non-list `annotations` value is shown as `0`.

### 7. Save Annotation And Refresh Dataset Page

1. Open an image that is currently `Unreviewed`.
2. Go to Manual Annotation.
3. Draw a rectangle.
4. Click `Add Annotation`.
5. Click `Save All to JSON`.
6. Go to Dataset and click `Refresh`.

Expected result:

- A matching JSON file is saved in `data/annotations/`.
- The image row changes to `Annotated`.
- Its annotation count increases to the number of confirmed annotations.
- The `Annotated Images` and `Unreviewed Images` cards update accordingly.

### 8. Mark As No Defect And Refresh Dataset Page

1. Open an image with no confirmed annotations.
2. Go to Manual Annotation.
3. Click `Mark as No Defect`.
4. Click `Save All to JSON`.
5. Go to Dataset and click `Refresh`.

Expected result:

- The image row changes to `No Defect`.
- Its annotation count is `0`.
- The `No Defect Images` card increases by one.
- The image cannot be marked as no defect while it has confirmed or pending annotations.

### 9. Invalid JSON Robustness

1. Choose one image in the test folder.
2. Back up any existing matching JSON file from `data/annotations/`.
3. Replace the matching JSON content with invalid JSON, for example `{ invalid`.
4. Start the app or click `Refresh` on the Dataset page.

Expected result:

- The app does not crash.
- The image row appears as `Unreviewed`.
- The annotation count is `0`.
- Other image rows and summary counts still render.

Cleanup:

- Restore the original JSON file or delete the temporary invalid JSON file.

### 10. Changing Folders

1. Open folder A and note the total, status cards, and table rows.
2. Open folder B with a different image count or different filenames.
3. Return to the Dataset page or click `Refresh`.

Expected result:

- `Total Images` changes to folder B's supported image count.
- Rows from folder A are no longer shown.
- Counts are recalculated from folder B image filenames and matching JSON files in `data/annotations/`.

## Pass Criteria

- The dashboard summary cards always equal the visible table status breakdown.
- The CLI helper and GUI agree for the same image folder.
- Invalid JSON never crashes the GUI or helper.
- No generated annotation JSON files are tracked by Git.
