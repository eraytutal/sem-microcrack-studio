import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.export_unet import ANNOTATIONS_DIR, DATA_DIR


METADATA_EXPORT_DIR = DATA_DIR / "exports" / "metadata"
METADATA_CSV_PATH = METADATA_EXPORT_DIR / "metadata.csv"
ANNOTATIONS_CSV_PATH = METADATA_EXPORT_DIR / "annotations.csv"
MISSING_VALUE = "(missing)"

METADATA_COLUMNS = [
    "filename",
    "original_filename",
    "width",
    "height",
    "material",
    "magnification",
    "scale_value",
    "scale_unit",
    "sem_mode",
    "image_quality",
    "notes",
    "saved_at",
    "image_sha256",
    "annotation_count",
    "classes_present",
]

ANNOTATION_COLUMNS = [
    "filename",
    "annotation_index",
    "class_name",
    "confidence",
    "status",
    "annotation_type",
    "exportable_to_mask",
    "bbox_x",
    "bbox_y",
    "bbox_width",
    "bbox_height",
    "point_count",
]


@dataclass
class MetadataExportResult:
    metadata_csv_path: Path
    annotations_csv_path: Path
    metadata_rows: int
    annotation_rows: int
    skipped: list[str]


@dataclass
class DatasetStatistics:
    total_images: int
    total_annotations: int
    annotations_by_class_name: dict[str, int]
    annotations_by_status: dict[str, int]
    annotations_by_confidence: dict[str, int]
    annotations_by_annotation_type: dict[str, int]
    images_with_zero_annotations: int
    skipped: list[str]


def load_master_records(annotations_dir: Path = ANNOTATIONS_DIR) -> tuple[list[dict[str, Any]], list[str]]:
    records = []
    skipped = []

    for annotation_path in sorted(annotations_dir.glob("*.json")):
        try:
            record = json.loads(annotation_path.read_text(encoding="utf-8"))
            record["_annotation_json_path"] = annotation_path.as_posix()
            records.append(record)
        except Exception as exc:
            skipped.append(f"{annotation_path.name}: {exc}")

    return records, skipped


def metadata_row(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata", {})
    annotations = record.get("annotations", [])
    classes_present = sorted(
        {
            annotation.get("class_name", "")
            for annotation in annotations
            if annotation.get("class_name")
        }
    )

    return {
        "filename": record.get("filename", ""),
        "original_filename": metadata.get("original_filename", ""),
        "width": record.get("width", ""),
        "height": record.get("height", ""),
        "material": metadata.get("material", ""),
        "magnification": metadata.get("magnification", ""),
        "scale_value": metadata.get("scale_value", ""),
        "scale_unit": metadata.get("scale_unit", ""),
        "sem_mode": metadata.get("sem_mode", ""),
        "image_quality": metadata.get("image_quality", ""),
        "notes": metadata.get("notes", ""),
        "saved_at": metadata.get("saved_at", ""),
        "image_sha256": metadata.get("image_sha256", ""),
        "annotation_count": len(annotations),
        "classes_present": ";".join(classes_present),
    }


def annotation_row(record: dict[str, Any], annotation: dict[str, Any], annotation_index: int) -> dict[str, Any]:
    bbox = annotation.get("bbox") or []
    bbox_values = bbox if len(bbox) == 4 else ["", "", "", ""]
    points = annotation.get("points") or []

    return {
        "filename": record.get("filename", ""),
        "annotation_index": annotation_index,
        "class_name": annotation.get("class_name", ""),
        "confidence": annotation.get("confidence", ""),
        "status": annotation.get("status", ""),
        "annotation_type": annotation.get("annotation_type", ""),
        "exportable_to_mask": annotation.get("exportable_to_mask", ""),
        "bbox_x": bbox_values[0],
        "bbox_y": bbox_values[1],
        "bbox_width": bbox_values[2],
        "bbox_height": bbox_values[3],
        "point_count": len(points),
    }


def build_metadata_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [metadata_row(record) for record in records]


def build_annotation_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        for index, annotation in enumerate(record.get("annotations", []), start=1):
            rows.append(annotation_row(record, annotation, index))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def export_metadata_csv(
    annotations_dir: Path = ANNOTATIONS_DIR,
    output_dir: Path = METADATA_EXPORT_DIR,
) -> MetadataExportResult:
    records, skipped = load_master_records(annotations_dir)
    metadata_rows = build_metadata_rows(records)
    annotation_rows = build_annotation_rows(records)

    metadata_csv_path = output_dir / "metadata.csv"
    annotations_csv_path = output_dir / "annotations.csv"
    write_csv(metadata_csv_path, metadata_rows, METADATA_COLUMNS)
    write_csv(annotations_csv_path, annotation_rows, ANNOTATION_COLUMNS)

    return MetadataExportResult(
        metadata_csv_path=metadata_csv_path,
        annotations_csv_path=annotations_csv_path,
        metadata_rows=len(metadata_rows),
        annotation_rows=len(annotation_rows),
        skipped=skipped,
    )


def counter_dict(counter: Counter) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: item[0]))


def compute_dataset_statistics(annotations_dir: Path = ANNOTATIONS_DIR) -> DatasetStatistics:
    records, skipped = load_master_records(annotations_dir)
    class_counter = Counter()
    status_counter = Counter()
    confidence_counter = Counter()
    type_counter = Counter()
    total_annotations = 0
    images_with_zero_annotations = 0

    for record in records:
        annotations = record.get("annotations", [])
        total_annotations += len(annotations)
        if not annotations:
            images_with_zero_annotations += 1

        for annotation in annotations:
            class_counter[annotation.get("class_name") or MISSING_VALUE] += 1
            status_counter[annotation.get("status") or MISSING_VALUE] += 1
            confidence_counter[annotation.get("confidence") or MISSING_VALUE] += 1
            type_counter[annotation.get("annotation_type") or MISSING_VALUE] += 1

    return DatasetStatistics(
        total_images=len(records),
        total_annotations=total_annotations,
        annotations_by_class_name=counter_dict(class_counter),
        annotations_by_status=counter_dict(status_counter),
        annotations_by_confidence=counter_dict(confidence_counter),
        annotations_by_annotation_type=counter_dict(type_counter),
        images_with_zero_annotations=images_with_zero_annotations,
        skipped=skipped,
    )
