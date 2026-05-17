import json
from dataclasses import dataclass
from pathlib import Path

from src.export_unet import ANNOTATIONS_DIR, DATA_DIR, load_export_image, resolve_image_path


COCO_EXPORT_DIR = DATA_DIR / "exports" / "coco"
COCO_IMAGES_DIR = COCO_EXPORT_DIR / "images" / "train"
COCO_JSON_PATH = COCO_EXPORT_DIR / "instances_train.json"
COCO_CATEGORY_MAP = {
    "crack": 1,
    "scratch": 2,
    "pit": 3,
    "void": 4,
    "uncertain": 5,
}
MIN_AREA = 1.0


@dataclass
class CocoExportResult:
    images_exported: int
    annotations_exported: int
    skipped_annotations: int
    output_json_path: Path
    output_image_dir: Path
    skipped: list[str]


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def clamp_point(point: list, image_width: int, image_height: int) -> list[float] | None:
    if len(point) < 2:
        return None

    x = clamp_float(float(point[0]), 0, image_width)
    y = clamp_float(float(point[1]), 0, image_height)
    return [round(x, 2), round(y, 2)]


def rectangle_to_points(bbox: list, image_width: int, image_height: int) -> list[list[float]]:
    if len(bbox) != 4:
        return []

    x, y, width, height = [float(value) for value in bbox]
    x1 = clamp_float(x, 0, image_width)
    y1 = clamp_float(y, 0, image_height)
    x2 = clamp_float(x + width, 0, image_width)
    y2 = clamp_float(y + height, 0, image_height)

    if x2 <= x1 or y2 <= y1:
        return []

    return [
        [round(x1, 2), round(y1, 2)],
        [round(x2, 2), round(y1, 2)],
        [round(x2, 2), round(y2, 2)],
        [round(x1, 2), round(y2, 2)],
    ]


def polygon_points(points: list, image_width: int, image_height: int) -> list[list[float]]:
    clamped_points = []
    for point in points:
        clamped_point = clamp_point(point, image_width, image_height)
        if clamped_point is not None:
            clamped_points.append(clamped_point)

    if len(clamped_points) > 1 and clamped_points[0] == clamped_points[-1]:
        clamped_points = clamped_points[:-1]

    return clamped_points


def polygon_area(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0

    area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        area += point[0] * next_point[1]
        area -= next_point[0] * point[1]

    return abs(area) / 2.0


def polygon_bbox(points: list[list[float]]) -> list[float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x_min = min(xs)
    y_min = min(ys)
    width = max(xs) - x_min
    height = max(ys) - y_min
    return [round(x_min, 2), round(y_min, 2), round(width, 2), round(height, 2)]


def flatten_points(points: list[list[float]]) -> list[float]:
    flattened = []
    for x, y in points:
        flattened.extend([round(x, 2), round(y, 2)])
    return flattened


def annotation_to_coco(
    annotation: dict,
    image_width: int,
    image_height: int,
) -> tuple[dict | None, str | None]:
    class_name = annotation.get("class_name")
    if class_name == "no_defect":
        return None, None
    if class_name not in COCO_CATEGORY_MAP:
        return None, f"Unsupported class: {class_name}"
    if annotation.get("exportable_to_mask") is not True:
        return None, None

    annotation_type = annotation.get("annotation_type")
    if annotation_type == "rectangle":
        points = rectangle_to_points(annotation.get("bbox", []), image_width, image_height)
    elif annotation_type == "polygon":
        points = polygon_points(annotation.get("points", []), image_width, image_height)
    else:
        return None, None

    if len(points) < 3:
        return None, f"Invalid {annotation_type} annotation with fewer than 3 polygon points."

    area = polygon_area(points)
    if area < MIN_AREA:
        return None, f"Invalid {annotation_type} annotation with near-zero area."

    return {
        "category_id": COCO_CATEGORY_MAP[class_name],
        "segmentation": [flatten_points(points)],
        "bbox": polygon_bbox(points),
        "area": round(area, 2),
        "iscrowd": 0,
    }, None


def coco_categories() -> list[dict]:
    return [
        {"id": category_id, "name": class_name}
        for class_name, category_id in sorted(COCO_CATEGORY_MAP.items(), key=lambda item: item[1])
    ]


def export_coco_dataset(
    annotations_dir: Path = ANNOTATIONS_DIR,
    output_dir: Path = COCO_EXPORT_DIR,
) -> CocoExportResult:
    images_dir = output_dir / "images" / "train"
    images_dir.mkdir(parents=True, exist_ok=True)

    images = []
    annotations = []
    skipped = []
    skipped_annotations = 0
    image_id = 1
    annotation_id = 1

    for annotation_path in sorted(annotations_dir.glob("*.json")):
        try:
            record = json.loads(annotation_path.read_text(encoding="utf-8"))
            image_path = resolve_image_path(record)
            if image_path is None:
                skipped.append(f"{annotation_path.name}: original image not found")
                continue

            image = load_export_image(image_path)
            width = int(record.get("width", image.width))
            height = int(record.get("height", image.height))
            if image.size != (width, height):
                image = image.resize((width, height))

            export_stem = Path(record.get("filename", annotation_path.stem)).stem
            export_file_name = f"{export_stem}.png"
            image.save(images_dir / export_file_name)

            images.append(
                {
                    "id": image_id,
                    "file_name": export_file_name,
                    "width": width,
                    "height": height,
                }
            )

            for annotation_index, annotation in enumerate(record.get("annotations", []), start=1):
                coco_annotation, skip_reason = annotation_to_coco(annotation, width, height)
                if coco_annotation is None:
                    if skip_reason:
                        skipped_annotations += 1
                        skipped.append(f"{annotation_path.name} annotation {annotation_index}: {skip_reason}")
                    continue

                coco_annotation.update(
                    {
                        "id": annotation_id,
                        "image_id": image_id,
                    }
                )
                annotations.append(coco_annotation)
                annotation_id += 1

            image_id += 1
        except Exception as exc:
            skipped.append(f"{annotation_path.name}: {exc}")

    coco_payload = {
        "images": images,
        "annotations": annotations,
        "categories": coco_categories(),
    }
    output_json_path = output_dir / "instances_train.json"
    output_json_path.write_text(json.dumps(coco_payload, indent=2), encoding="utf-8")

    return CocoExportResult(
        images_exported=len(images),
        annotations_exported=len(annotations),
        skipped_annotations=skipped_annotations,
        output_json_path=output_json_path,
        output_image_dir=images_dir,
        skipped=skipped,
    )


def synthetic_export_check(output_dir: Path) -> CocoExportResult:
    """Small internal check helper for development and tests."""
    return export_coco_dataset(output_dir=output_dir)
