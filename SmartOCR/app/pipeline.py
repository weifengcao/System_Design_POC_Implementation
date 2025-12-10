from __future__ import annotations

import io
from typing import List

from PIL import Image

from . import models, extractors
from .storage import InMemoryDoc

try:
    import pytesseract
except Exception:  # pragma: no cover - optional dep
    pytesseract = None

try:
    from pdf2image import convert_from_bytes
except Exception:  # pragma: no cover - optional dep
    convert_from_bytes = None


def _load_images(content: bytes) -> List[Image.Image]:
    if not content:
        return []
    # Heuristic: PDF if starts with %PDF
    if content.startswith(b"%PDF") and convert_from_bytes:
        poppler_path = None
        from .config import settings
        poppler_path = settings.poppler_path
        kwargs = {"poppler_path": poppler_path} if poppler_path else {}
        return convert_from_bytes(content, **kwargs)

    # Fallback to single image
    return [Image.open(io.BytesIO(content)).convert("RGB")]


def _ocr_page(img: Image.Image, page_number: int) -> tuple[List[models.Block], str]:
    """
    Run OCR on a single page. If pytesseract is unavailable, return a stub.
    """
    if not pytesseract:
        text = f"Stub OCR output for page {page_number}"
        bbox = models.BoundingBox(x=0, y=0, width=img.width, height=img.height)
        block = models.Block(
            id=f"blk-{page_number}",
            page_number=page_number,
            bbox=bbox,
            type="paragraph",
            text=text,
            confidence=0.5,
            reading_order=page_number,
        )
        return [block], text

    from .config import settings
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    text = pytesseract.image_to_string(img)
    blocks: List[models.Block] = []
    # Aggregate all words into a single paragraph block for now.
    xs = [data["left"][i] for i in range(len(data["text"])) if data["text"][i].strip()]
    ys = [data["top"][i] for i in range(len(data["text"])) if data["text"][i].strip()]
    ws = [data["width"][i] for i in range(len(data["text"])) if data["text"][i].strip()]
    hs = [data["height"][i] for i in range(len(data["text"])) if data["text"][i].strip()]
    if xs and ys and ws and hs:
        min_x, min_y = min(xs), min(ys)
        max_x = max(x + w for x, w in zip(xs, ws))
        max_y = max(y + h for y, h in zip(ys, hs))
        bbox = models.BoundingBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)
    else:
        bbox = models.BoundingBox(x=0, y=0, width=img.width, height=img.height)

    block = models.Block(
        id=f"blk-{page_number}",
        page_number=page_number,
        bbox=bbox,
        type="paragraph",
        text=text.strip(),
        confidence=0.8,
        reading_order=page_number,
    )
    blocks.append(block)
    return blocks, text


def run_ocr(content: bytes, doc_type: str = "generic") -> models.OCRResult:
    """
    Load bytes, convert PDF/images to PIL, run OCR (pytesseract if available), and emit blocks/fields.
    """
    images = _load_images(content)
    if not images:
        # Nothing to process
        return models.OCRResult(
            job_id="",
            source_uri="",
            blocks=[],
            fields=[],
            confidence=0.0,
        )

    all_blocks: List[models.Block] = []
    page_texts: List[str] = []
    for idx, img in enumerate(images, start=1):
        blocks, text = _ocr_page(img, idx)
        all_blocks.extend(blocks)
        page_texts.append(text)

    full_text = "\n".join(page_texts).strip()
    total_conf = sum(b.confidence for b in all_blocks) / max(1, len(all_blocks))

    fields = extractors.extract_fields(
        full_text=full_text, doc_type=doc_type, default_conf=total_conf, page_count=len(images)
    )

    return models.OCRResult(
        job_id="",
        source_uri="",
        blocks=all_blocks,
        fields=fields,
        confidence=total_conf,
    )
