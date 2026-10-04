"""Local detection and selective redaction; never regenerate the image."""

import math
import os
from threading import Lock
from typing import Any

from PIL import Image

_lock = Lock()
_processor: Any = None
_model: Any = None
MODEL_ID = "IDEA-Research/grounding-dino-tiny"
# Conservatively cover readable text, including personal data without OCR guesses.
PROMPT = "person. face. license plate. text. document. screen."


def detect_regions(image: Image.Image) -> list[tuple[int, int, int, int]]:
    """Return rectangles in original pixel coordinates, using CPU inference."""
    global _processor, _model
    import torch
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    with _lock, torch.inference_mode():
        if _model is None:
            torch.set_num_threads(int(os.environ.get("REPORT_VLM_THREADS", "4")))
            model_id = os.environ.get("PHOTO_PRIVACY_MODEL", MODEL_ID)
            processor = AutoProcessor.from_pretrained(model_id)
            model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id)
            _model = model.to("cpu").eval()
            _processor = processor
        inputs = _processor(
            images=image.convert("RGB"), text=PROMPT, return_tensors="pt"
        )
        outputs = _model(**inputs)
        result = _processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=0.2,
            text_threshold=0.2,
            target_sizes=[(image.height, image.width)],
        )[0]
        regions = []
        for coordinates in result["boxes"].tolist():
            if len(coordinates) != 4 or not all(math.isfinite(x) for x in coordinates):
                raise ValueError("Invalid privacy detection coordinates")
            x1, y1, x2, y2 = coordinates
            box = (
                max(0, math.floor(x1)),
                max(0, math.floor(y1)),
                min(image.width, math.ceil(x2)),
                min(image.height, math.ceil(y2)),
            )
            if box[0] >= box[2] or box[1] >= box[3]:
                raise ValueError("Empty privacy detection rectangle")
            regions.append(box)
        return regions


def anonymize(image: Image.Image) -> Image.Image:
    regions = detect_regions(image)
    result = image.copy()
    for box in regions:
        crop = image.crop(box)
        # A single average color removes all identifying detail in the rectangle.
        crop = crop.resize((1, 1), Image.Resampling.BOX).resize(crop.size)
        if image.mode == "RGBA":
            crop.putalpha(255)
        result.paste(crop, box)
    return result
