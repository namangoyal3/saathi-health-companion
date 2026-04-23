"""Lab PDF vision pipeline — PyMuPDF rasterize + Opus 4.7 vision + pdfplumber fallback.

Pipeline:
  rasterize(pdf_path) → list[bytes]  (PNG pages at 300 DPI, max_edge 2576 px)
  opus_vision_extract(images) → list[BiomarkerRow]  (tool-forced schema)
  parse_lab_pdf(pdf_path) → list[BiomarkerRow]  (with fallback)
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import fitz  # PyMuPDF
import pdfplumber

from app.llm.haiku import haiku_call
from app.llm.opus import opus_call

MAX_EDGE_PX = 2576
DPI = 300
FALLBACK_THRESHOLD_CONFIDENCE = 0.85
FALLBACK_THRESHOLD_COUNT = 5

_BIOMARKER_EXTRACTION_TOOL: dict[str, Any] = {
    "name": "extract_biomarkers",
    "description": (
        "Extract all biomarker readings visible in the lab report images. "
        "Each row must have the biomarker name, value, unit, reference range if visible, "
        "and a flag indicating whether the value is low, high, or normal."
    ),
    "input_schema": {
        "type": "object",
        "required": ["biomarkers", "collection_date", "lab_chain"],
        "properties": {
            "collection_date": {
                "type": "string",
                "description": "Collection/report date in YYYY-MM-DD format, or empty string if not found.",
            },
            "lab_chain": {
                "type": "string",
                "description": "Lab chain name (e.g. thyrocare, drlal, metropolis). Lowercase.",
            },
            "biomarkers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["biomarker", "value", "unit", "flag", "confidence"],
                    "properties": {
                        "biomarker": {"type": "string"},
                        "value": {"type": "number"},
                        "unit": {"type": "string"},
                        "ref_low": {"type": ["number", "null"]},
                        "ref_high": {"type": ["number", "null"]},
                        "flag": {
                            "type": "string",
                            "enum": ["low", "high", "normal", "null"],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                },
            },
        },
    },
}

_FALLBACK_SYSTEM = """You are a lab report parser. Given plain text extracted from a PDF lab report,
extract every biomarker, its numeric value, unit, reference range, and flag (low/high/normal).
Respond ONLY with valid JSON: {"biomarkers": [...], "collection_date": "YYYY-MM-DD", "lab_chain": "name"}.
Each biomarker: {"biomarker":"...","value":0.0,"unit":"...","ref_low":null,"ref_high":null,"flag":"normal","confidence":0.8}"""


@dataclass
class BiomarkerRow:
    biomarker: str
    value: float
    unit: str
    ref_low: float | None
    ref_high: float | None
    flag: str
    confidence: float
    collection_date: str
    lab_chain: str


def rasterize(pdf_path: Path, *, dpi: int = DPI, max_edge_px: int = MAX_EDGE_PX) -> list[bytes]:
    """Convert each PDF page to a PNG bytes object at up to max_edge_px on the long edge."""
    doc = fitz.open(str(pdf_path))
    pages: list[bytes] = []

    for page in doc:
        # Compute scale so longest edge ≤ max_edge_px
        rect = page.rect
        base_w = rect.width * dpi / 72
        base_h = rect.height * dpi / 72
        scale = min(1.0, max_edge_px / max(base_w, base_h))
        mat = fitz.Matrix(scale * dpi / 72, scale * dpi / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
        pages.append(pix.tobytes("png"))

    doc.close()
    return pages


def opus_vision_extract(images: list[bytes]) -> dict[str, Any]:
    """Send rasterized pages to Opus 4.7 with tool-forced biomarker extraction."""
    content: list[dict[str, Any]] = []
    for img_bytes in images:
        b64 = base64.standard_b64encode(img_bytes).decode()
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64},
            }
        )
    content.append(
        {
            "type": "text",
            "text": (
                "Extract every biomarker from these lab report pages. "
                "Call extract_biomarkers with ALL findings."
            ),
        }
    )

    msg = opus_call(
        system=(
            "You are a medical lab report parser specializing in Indian lab chains "
            "(Thyrocare, Dr Lal, Metropolis, SRL). Extract biomarkers accurately. "
            "If a value is illegible set confidence≤0.5."
        ),
        user=content,
        effort="medium",
        tools=[_BIOMARKER_EXTRACTION_TOOL],
        max_tokens=4096,
        agent_name="lab-vision-agent",
        display="omitted",
    )

    for block in msg.content:
        if block.type == "tool_use" and block.name == "extract_biomarkers":
            return cast(dict[str, Any], block.input)

    return {}


def _fallback_extract(pdf_path: Path) -> dict[str, Any]:
    """pdfplumber text extraction + Haiku for low-quality PDFs."""
    text_parts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)

    full_text = "\n".join(text_parts)
    if not full_text.strip():
        return {}

    msg = haiku_call(
        system=_FALLBACK_SYSTEM,
        user=full_text[:8000],  # Haiku token budget
        max_tokens=2048,
        agent_name="lab-vision-fallback",
    )

    raw = ""
    for block in msg.content:
        if hasattr(block, "text"):
            raw = block.text
            break

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        return cast(dict[str, Any], json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return {}


def parse_lab_pdf(pdf_path: Path, *, use_fallback: bool = True) -> list[BiomarkerRow]:
    """Main entry point for lab PDF parsing.

    1. Rasterize with PyMuPDF at 300 DPI / 2576 px max.
    2. Opus 4.7 vision extract (tool-forced).
    3. If mean_confidence < 0.85 or len(biomarkers) < 5, run pdfplumber+Haiku fallback.
    """
    images = rasterize(pdf_path)
    data = opus_vision_extract(images) if images else {}

    biomarkers_raw: list[dict[str, Any]] = data.get("biomarkers", [])
    collection_date: str = data.get("collection_date", "")
    lab_chain: str = data.get("lab_chain", "unknown")

    mean_conf = (
        sum(b.get("confidence", 0.0) for b in biomarkers_raw) / len(biomarkers_raw)
        if biomarkers_raw
        else 0.0
    )

    if use_fallback and (
        mean_conf < FALLBACK_THRESHOLD_CONFIDENCE or len(biomarkers_raw) < FALLBACK_THRESHOLD_COUNT
    ):
        fallback_data = _fallback_extract(pdf_path)
        if fallback_data.get("biomarkers"):
            biomarkers_raw = fallback_data["biomarkers"]
            collection_date = fallback_data.get("collection_date", collection_date)
            lab_chain = fallback_data.get("lab_chain", lab_chain)

    rows: list[BiomarkerRow] = []
    for b in biomarkers_raw:
        try:
            rows.append(
                BiomarkerRow(
                    biomarker=str(b["biomarker"]),
                    value=float(b["value"]),
                    unit=str(b.get("unit", "")),
                    ref_low=float(b["ref_low"]) if b.get("ref_low") is not None else None,
                    ref_high=float(b["ref_high"]) if b.get("ref_high") is not None else None,
                    flag=str(b.get("flag", "null")),
                    confidence=float(b.get("confidence", 0.8)),
                    collection_date=collection_date,
                    lab_chain=lab_chain,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    return rows
