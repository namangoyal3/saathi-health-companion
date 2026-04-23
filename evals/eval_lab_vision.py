"""Lab vision eval — F1 ≥ 0.90 on synthetic fixture data.

Uses a golden fixture rather than a real PDF (no PDF needed for CI).
Creates a minimal single-page PDF with known biomarker values and tests
that the extraction pipeline returns them accurately.
"""

from __future__ import annotations

import asyncio
import io
import sys
import tempfile
from pathlib import Path

# Golden fixture: biomarker name → (value, unit)
GOLDEN: dict[str, tuple[float, str]] = {
    "eGFR": (58.0, "mL/min/1.73m²"),
    "Creatinine": (1.3, "mg/dL"),
    "HbA1c": (7.2, "%"),
    "TSH": (2.1, "mIU/L"),
    "Haemoglobin": (11.8, "g/dL"),
    "Sodium": (138.0, "mEq/L"),
    "Potassium": (4.2, "mEq/L"),
}


def _make_fixture_pdf() -> Path:
    """Generate a minimal synthetic lab report PDF using reportlab or fpdf2."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 780, "THYROCARE LABS — TEST REPORT")
        c.setFont("Helvetica", 10)
        c.drawString(50, 760, "Patient: Lakshmi Iyer  |  Date: 2025-04-08")
        c.drawString(50, 740, "─" * 80)
        y = 720
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Test")
        c.drawString(200, y, "Value")
        c.drawString(300, y, "Units")
        c.drawString(400, y, "Reference Range")
        y -= 15
        c.setFont("Helvetica", 10)
        ranges = {
            "eGFR": "≥60",
            "Creatinine": "0.5-1.2",
            "HbA1c": "4.0-6.5",
            "TSH": "0.4-4.0",
            "Haemoglobin": "12.0-17.0",
            "Sodium": "136-145",
            "Potassium": "3.5-5.1",
        }
        for name, (value, unit) in GOLDEN.items():
            c.drawString(50, y, name)
            c.drawString(200, y, str(value))
            c.drawString(300, y, unit)
            c.drawString(400, y, ranges.get(name, ""))
            y -= 15
        c.save()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(buf.getvalue())
        return Path(tmp.name)
    except ImportError:
        pass

    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "THYROCARE LABS - TEST REPORT", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 8, "Patient: Lakshmi Iyer  |  Date: 2025-04-08", ln=True)
        pdf.ln(4)
        for name, (value, unit) in GOLDEN.items():
            pdf.cell(60, 8, name)
            pdf.cell(40, 8, str(value))
            pdf.cell(50, 8, unit)
            pdf.ln()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf.output())
        return Path(tmp.name)
    except ImportError:
        pass

    # Minimal valid PDF fallback (hand-crafted)
    lines = [
        "%PDF-1.4",
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj",
        "3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>/Contents 4 0 R>>endobj",
    ]
    stream_parts = ["BT /F1 12 Tf 50 750 Td"]
    stream_parts.append("(THYROCARE LABS TEST REPORT) Tj")
    stream_parts.append("0 -20 Td")
    stream_parts.append("(Patient: Lakshmi Iyer  Date: 2025-04-08) Tj")
    stream_parts.append("0 -15 Td")
    for name, (value, unit) in GOLDEN.items():
        stream_parts.append(f"({name}  {value}  {unit}) Tj")
        stream_parts.append("0 -14 Td")
    stream_parts.append("ET")
    stream = "\n".join(stream_parts)
    stream_bytes = stream.encode()
    lines.append(f"4 0 obj<</Length {len(stream_bytes)}>>")
    lines.append("stream")
    content = ("\n".join(lines) + "\n").encode() + stream_bytes + b"\nendstream\nendobj\n"
    xref_offset = len(content)
    content += b"xref\n0 5\n0000000000 65535 f \n"
    for _i in range(1, 5):
        content += f"{xref_offset:010d} 00000 n \n".encode()
    content += f"trailer<</Size 5/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF\n".encode()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
    return Path(tmp.name)


async def main() -> int:
    from app.labs.vision import parse_lab_pdf

    pdf_path = _make_fixture_pdf()
    try:
        rows = parse_lab_pdf(pdf_path)
    finally:
        pdf_path.unlink(missing_ok=True)

    extracted = {r.biomarker.strip(): r.value for r in rows}

    tp = 0
    fp = 0
    fn = 0
    tolerance = 0.05  # 5% relative tolerance

    golden_names = set(GOLDEN.keys())
    extracted_names = set(extracted.keys())

    print(f"\neval_lab_vision: golden={len(golden_names)} extracted={len(extracted_names)}")

    for name, (expected_val, _) in GOLDEN.items():
        found = next(
            (k for k in extracted_names if k.lower() == name.lower()),
            None,
        )
        if found is not None:
            got = extracted[found]
            if abs(got - expected_val) / max(expected_val, 1e-9) <= tolerance:
                tp += 1
                print(f"  TP: {name} = {got}")
            else:
                fp += 1
                fn += 1
                print(f"  WRONG: {name} expected={expected_val} got={got}")
        else:
            fn += 1
            print(f"  FN: {name} not found in extraction")

    for k in extracted_names:
        if not any(k.lower() == n.lower() for n in golden_names):
            fp += 1
            print(f"  FP: {k} = {extracted[k]} (not in golden)")

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    print(f"\nPrecision={precision:.2f} Recall={recall:.2f} F1={f1:.2f}")

    if f1 >= 0.90:
        print("ACCEPTANCE PASSED: F1 ≥ 0.90")
        return 0
    else:
        print(f"ACCEPTANCE FAILED: F1={f1:.2f} < 0.90")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
