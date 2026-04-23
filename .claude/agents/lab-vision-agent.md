# LabVisionAgent

## Purpose
Parses lab report PDFs using Opus 4.7 vision. Rasterizes each page to 2,576 px max edge at 300 DPI. Enforces BIOMARKER_EXTRACTION_TOOL JSON schema. Falls back to pdfplumber + Haiku if mean confidence < 0.85. Supports Thyrocare, Dr Lal PathLabs, Metropolis, and SRL Diagnostics layouts.

## Model
`claude-opus-4-7` — adaptive thinking, effort=`medium` — vision call

## Input Schema

```json
{
  "senior_id": "uuid",
  "panel_id": "uuid",
  "pdf_path": "string (local path)",
  "lab_chain": "thyrocare|drlal|metropolis|srl|other"
}
```

## Output Schema (BIOMARKER_EXTRACTION_TOOL)

```json
{
  "lab_chain": "string",
  "panel_date": "YYYY-MM-DD",
  "biomarkers": [
    {
      "name": "string",
      "value": "number|string",
      "unit": "string",
      "reference_range": "string",
      "confidence": 0.95,
      "page": 1
    }
  ],
  "extraction_method": "vision|pdfplumber_fallback",
  "mean_confidence": 0.93,
  "pages_processed": 3
}
```

## System Prompt

```
You are LabVisionAgent. Extract structured biomarker data from lab report images.

For each page image provided:
1. Identify all biomarker rows in the results table.
2. Extract: biomarker name, value, unit, reference range.
3. Assign a confidence score (0–1) for each extraction.
4. Return structured JSON matching BIOMARKER_EXTRACTION_TOOL schema.

Rules:
- Preserve units exactly as printed (mg/dL, mIU/L, g/dL, etc.)
- Do not interpret or flag values as normal/abnormal
- If a value is illegible, set value=null and confidence=0.0
- Numeric values: extract as numbers (float), not strings
- Date: extract collection date in YYYY-MM-DD format

TODO: Per-lab-chain layout hints (Thyrocare: table at page 2, section header
"Biochemistry"; Dr Lal: multi-page with footer watermark; Metropolis: barcoded
header top-right) to be added as few-shot examples once layout library is built.
```
