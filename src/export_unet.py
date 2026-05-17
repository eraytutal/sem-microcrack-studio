import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image, ImageDraw


DATA_DIR = Path("data")
ANNOTATIONS_DIR = DATA_DIR / "annotations"
IMAGES_ORIGINAL_DIR = DATA_DIR / "images_original"
UNET_EXPORT_DIR = DATA_DIR / "exports" / "unet"
UNET_IMAGES_DIR = UNET_EXPORT_DIR / "images"
UNET_MASKS_DIR = UNET_EXPORT_DIR / "masks"


@dataclass
class UnetExportResult:
    images_exported: int
    masks_exported: int
    output_dir: Path
    skipped: list[str]


def normalize_to_uint8(array: np.ndarray) -> np.ndarray:
    array = np.asarray(array)

    if array.dtype == np.uint8:
        return array

    array = array.astype(np.float32)
    finite_mask = np.isfinite(array)
    if not finite_mask.any():
        return np.zeros(array.shape, dtype=np.uint8)

    min_value = array[finite_mask].min()
    max_value = array[finite_mask].max()
    if min_value == max_value:
        return np.zeros(array.shape, dtype=np.uint8)

    array = np.nan_to_num(array, nan=min_value, posinf=max_value, neginf=min_value)
    normalized = (array - min_value) / (max_value - min_value)
    return (normalized * 255).clip(0, 255).astype(np.uint8)


def image_from_array(array: np.ndarray) -> Image.Image:
    array = np.asarray(array)

    if array.ndim > 3:
        array = array[0]

    if array.ndim == 2:
        return Image.fromarray(normalize_to_uint8(array), mode="L")

    if array.ndim == 3 and array.shape[2] in {3, 4}:
        mode = "RGBA" if array.shape[2] == 4 else "RGB"
        return Image.fromarray(normalize_to_uint8(array), mode=mode)

    raise ValueError(f"Unsupported image shape: {array.shape}")


def load_export_image(image_path: Path) -> Image.Image:
    is_tiff = image_path.suffix.lower() in {".tif", ".tiff"}

    try:
        image = Image.open(image_path)
        image.load()
    except Exception:
        if not is_tiff:
            raise
        return image_from_array(tifffile.imread(image_path))

    if image.mode in {"RGB", "RGBA", "L"}:
        return image.copy()

    if image.mode in {"I;16", "I", "F"}:
        return image_from_array(np.asarray(image))

    if is_tiff:
        return image_from_array(tifffile.imread(image_path))

    return image.convert("RGB")


def resolve_image_path(record: dict) -> Path | None:
    candidates = []

    filename = record.get("filename")
    if filename:
        candidates.append(IMAGES_ORIGINAL_DIR / filename)

    stored_path = record.get("metadata", {}).get("stored_image_path")
    if stored_path:
        candidates.append(Path(stored_path))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def clamp_int(value: float, minimum: int, maximum: int) -> int:
    return int(round(min(max(value, minimum), maximum)))


def draw_rectangle(draw: ImageDraw.ImageDraw, bbox: list, width: int, height: int) -> None:
    if len(bbox) != 4:
        return

    x, y, box_width, box_height = [float(value) for value in bbox]
    x1 = clamp_int(x, 0, width)
    y1 = clamp_int(y, 0, height)
    x2 = clamp_int(x + box_width, 0, width)
    y2 = clamp_int(y + box_height, 0, height)

    if x2 <= x1 or y2 <= y1:
        return

    draw.rectangle([x1, y1, x2, y2], fill=255)


def draw_polygon(draw: ImageDraw.ImageDraw, points: list, width: int, height: int) -> None:
    if len(points) < 3:
        return

    clamped_points = [
        (
            clamp_int(float(point[0]), 0, width),
            clamp_int(float(point[1]), 0, height),
        )
        for point in points
        if len(point) >= 2
    ]

    if len(clamped_points) < 3:
        return

    draw.polygon(clamped_points, fill=255)


def render_mask(record: dict, size: tuple[int, int]) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    for annotation in record.get("annotations", []):
        if annotation.get("class_name") == "no_defect":
            continue
        if annotation.get("class_name") != "crack":
            continue
        if annotation.get("exportable_to_mask") is not True:
            continue

        annotation_type = annotation.get("annotation_type")
        if annotation_type == "rectangle":
            draw_rectangle(draw, annotation.get("bbox", []), width, height)
        elif annotation_type == "polygon":
            draw_polygon(draw, annotation.get("points", []), width, height)

    return mask


def export_unet_dataset(
    annotations_dir: Path = ANNOTATIONS_DIR,
    output_dir: Path = UNET_EXPORT_DIR,
) -> UnetExportResult:
    images_dir = output_dir / "images"
    masks_dir = output_dir / "masks"
    images_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    images_exported = 0
    masks_exported = 0
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
            mask_output_path = masks_dir / f"{export_stem}.png"

            image.save(image_output_path)
            mask = render_mask(record, image.size)
            mask.save(mask_output_path)

            images_exported += 1
            masks_exported += 1
        except Exception as exc:
            skipped.append(f"{annotation_path.name}: {exc}")

    return UnetExportResult(
        images_exported=images_exported,
        masks_exported=masks_exported,
        output_dir=output_dir,
        skipped=skipped,
    )
