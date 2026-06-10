import os
from functools import lru_cache

import cv2
from PIL import Image

INFERENCE_SIZE = 640
CONFIDENCE_THRESHOLD = 0.01
IOU_THRESHOLD = 0.45


@lru_cache(maxsize=1)
def _get_model():
    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise RuntimeError("ultralytics is not installed") from exc

    # app/services -> app -> project root
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    model_path = os.path.join(base_dir, "best.pt")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    return YOLO(model_path)


def crop_id_card_with_model(image_path, output_path=None):
    """
    Crop the most confident detected card region using best.pt.
    Returns the saved crop path, or None if detection fails.
    """
    result = detect_and_crop_with_model(image_path, crop_output_path=output_path)
    return result["crop_path"] if result else None


def detect_and_crop_with_model(image_path, crop_output_path=None, boxed_output_path=None):
    """
    Run best.pt inference at 640px, then save:
    1. the detected bounding-box crop
    2. the original image annotated with box + label
    """
    try:
        if not os.path.exists(image_path):
            return None

        model = _get_model()
        results = model.predict(
            source=image_path,
            imgsz=INFERENCE_SIZE,
            conf=CONFIDENCE_THRESHOLD,
            iou=IOU_THRESHOLD,
            verbose=False,
            save=False,
        )
        if not results:
            return None

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return None

        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy() if result.boxes.conf is not None else None
        best_idx = int(confidences.argmax()) if confidences is not None and len(confidences) else 0

        box = boxes[best_idx].tolist()
        x1, y1, x2, y2 = [max(0, int(v)) for v in box]

        img = cv2.imread(image_path)
        if img is None:
            return None

        h, w = img.shape[:2]
        x1 = min(max(0, x1), w - 1)
        y1 = min(max(0, y1), h - 1)
        x2 = min(max(x1 + 1, x2), w)
        y2 = min(max(y1 + 1, y2), h)

        if x2 <= x1 or y2 <= y1:
            return None

        cropped = img[y1:y2, x1:x2]
        if cropped.size == 0:
            return None

        if crop_output_path is None:
            base, ext = os.path.splitext(image_path)
            crop_output_path = f"{base}_crop{ext or '.jpg'}"

        if boxed_output_path is None:
            base, ext = os.path.splitext(image_path)
            boxed_output_path = f"{base}_boxed{ext or '.jpg'}"

        crop_output_dir = os.path.dirname(crop_output_path)
        if crop_output_dir:
            os.makedirs(crop_output_dir, exist_ok=True)
        boxed_output_dir = os.path.dirname(boxed_output_path)
        if boxed_output_dir:
            os.makedirs(boxed_output_dir, exist_ok=True)

        # Use PIL for a more reliable save path on Windows and verify the file is written.
        rgb_image = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb_image).save(crop_output_path)

        confidence = float(confidences[best_idx]) if confidences is not None and len(confidences) else None
        class_id = int(result.boxes.cls[best_idx].item()) if result.boxes.cls is not None else 0
        label_name = str(result.names.get(class_id, "object"))
        label = f"{label_name} {confidence:.2f}" if confidence is not None else label_name
        boxed_image = img.copy()
        cv2.rectangle(boxed_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        label_y = max(y1, label_size[1] + baseline + 4)
        cv2.rectangle(
            boxed_image,
            (x1, label_y - label_size[1] - baseline - 4),
            (min(x1 + label_size[0] + 8, w), label_y + baseline),
            (0, 255, 0),
            -1,
        )
        cv2.putText(
            boxed_image,
            label,
            (x1 + 4, label_y - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
        boxed_rgb_image = cv2.cvtColor(boxed_image, cv2.COLOR_BGR2RGB)
        Image.fromarray(boxed_rgb_image).save(boxed_output_path)

        crop_saved = os.path.exists(crop_output_path) and os.path.getsize(crop_output_path) > 0
        boxed_saved = os.path.exists(boxed_output_path) and os.path.getsize(boxed_output_path) > 0
        if crop_saved and boxed_saved:
            return {
                "crop_path": crop_output_path,
                "boxed_path": boxed_output_path,
                "confidence": confidence,
                "label": label_name,
                "box": [x1, y1, x2, y2],
            }
        return None
    except Exception:
        return None
