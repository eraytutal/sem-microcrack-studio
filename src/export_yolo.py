import json
from dataclasses import dataclass
from pathlib import Path

from src.export_unet import ANNOTATIONS_DIR, DATA_DIR, load_export_image, resolve_image_path


YOLO_EXPORT_DIR = DATA_DIR / "exports" / "yolo_seg"
YOLO_IMAGES_DIR = YOLO_EXPORT_DIR / "images" / "train"
YOLO_LABELS_DIR = YOLO_EXPORT_DIR / "labels" / "train"
YOLO_CLASS_MAP = {
    "crack": 0,
    "scratch": 1,
    "pit": 2,
    "void": 3,
    "uncertain": 4,
}


@dataclass
class YoloExportResult:
    images_exported: int
    label_files_exported: int
    empty_label_files: int
    output_dir: Path
    skipped: list[str]


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def normalize_point(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    clamped_x = clamp_float(x, 0, width)
    clamped_y = clamp_float(y, 0, height)
    return clamped_x / width, clamped_y / height


def rectangle_to_points(bbox: list) -> list[list[float]]:
    if len(bbox) != 4:
        return []

    x, y, width, height = [float(value) for value in bbox]
    if width <= 0 or height <= 0:
        return []

    return [
        [x, y],
        [x + width, y],
        [x + width, y + height],
        [x, y + height],
    ]


def annotation_points(annotation: dict) -> list[list[float]]:
    annotation_type = annotation.get("annotation_type")
    if annotation_type == "rectangle":
        return rectangle_to_points(annotation.get("bbox", []))
    if annotation_type == "polygon":
        return annotation.get("points", [])
    return []


def annotation_to_yolo_line(annotation: dict, image_width: int, image_height: int) -> str | None:
    class_name = annotation.get("class_name")
    if class_name == "no_defect":
        return None
    if class_name not in YOLO_CLASS_MAP:
        return None
    if annotation.get("exportable_to_mask") is not True:
        return None

    points = annotation_points(annotation)
    if len(points) < 3:
        return None

    values = [str(YOLO_CLASS_MAP[class_name])]
    for point in points:
        if len(point) < 2:
            continue
        normalized_x, normalized_y = normalize_point(
            float(point[0]),
            float(point[1]),
            image_width,
            image_height,
        )
        values.extend([f"{normalized_x:.6f}", f"{normalized_y:.6f}"])

    if len(values) < 7:
        return None

    return " ".join(values)


def write_data_yaml(output_dir: Path) -> Path:
    yaml_path = output_dir / "data.yaml"
    names = [class_name for class_name, _ in sorted(YOLO_CLASS_MAP.items(), key=lambda item: item[1])]
    yaml_text = "\n".join(
        [
            "path: .",
            "train: images/train",
            "val: images/train",
            f"nc: {len(names)}",
            "names:",
            *[f"  {index}: {name}" for index, name in enumerate(names)],
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")
    return yaml_path


def export_yolo_segmentation_dataset(
    annotations_dir: Path = ANNOTATIONS_DIR,
    output_dir: Path = YOLO_EXPORT_DIR,
) -> YoloExportResult:
    images_dir = output_dir / "images" / "train"
    labels_dir = output_dir / "labels" / "train"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    write_data_yaml(output_dir)

    images_exported = 0
    label_files_exported = 0
    empty_label_files = 0
    skipped = []

    for annotation_path in sorted(annotations_dir.glob("*.json")):
        try:
            record = json.loads(annotation_path.read_text(encoding="utf-8"))
            image_path = resolve_image_path(record)
            if image_path is None:
                skipped.append(f"{annotation_path.name}: original image not found")
                continue

            image = load_export_image(image_path)
            expected_size = (int(record.get("width", image.width)), int(record.get("height", image.height)))
            if image.size != expected_size:
                image = image.resize(expected_size)

            export_stem = Path(record.get("filename", annotation_path.stem)).stem
            image_output_path = images_dir / f"{export_stem}.png"
            label_output_path = labels_dir / f"{export_stem}.txt"

            image.save(image_output_path)
            images_exported += 1

            lines = []
            for annotation in record.get("annotations", []):
                line = annotation_to_yolo_line(annotation, image.width, image.height)
                if line:
                    lines.append(line)

            label_output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            label_files_exported += 1
            if not lines:
                empty_label_files += 1
        except Exception as exc:
            skipped.append(f"{annotation_path.name}: {exc}")

    return YoloExportResult(
        images_exported=images_exported,
        label_files_exported=label_files_exported,
        empty_label_files=empty_label_files,
        output_dir=output_dir,
        skipped=skipped,
    )
