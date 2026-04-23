"""DDI canonical eval — Lakshmi Iyer's 7-medication regimen.

Acceptance: exactly 2 HIGH-severity flags (Metformin+eGFR and Amlodipine+dizziness).
"""

from __future__ import annotations

import asyncio
import sys

from app.agents.ddi import DDIInput, DDIResult, LabPanelInput, MedicationInput, SymptomInput, run
from evals.personas.lakshmi import LAKSHMI


def _build_input() -> DDIInput:
    meds = [
        MedicationInput(
            name=m.name,
            dose_mg=m.dose_mg,
            frequency_rrule=m.frequency_rrule,
            start_date=str(m.start_date),
            prescriber=m.prescriber,
        )
        for m in LAKSHMI.medications
    ]

    labs = [
        LabPanelInput(
            panel_date=str(p.panel_date),
            biomarkers={b.name: float(b.value) for b in p.biomarkers},
        )
        for p in LAKSHMI.lab_panels
    ]

    symptoms = [
        SymptomInput(
            date=str(s.date),
            symptom=s.symptom,
            source=s.source,
        )
        for s in LAKSHMI.symptoms
    ]

    return DDIInput(
        senior_id=LAKSHMI.senior_id,
        medications=meds,
        recent_labs=labs,
        recent_symptoms=symptoms,
    )


async def main() -> int:
    ddi_input = _build_input()
    result: DDIResult = await run(ddi_input)

    high_flags = [f for f in result.flags if f.severity == "HIGH"]

    print(f"\neval_ddi_canonical: {len(result.flags)} total flags, {len(high_flags)} HIGH")
    for f in result.flags:
        print(f"  [{f.severity}] {f.interaction_type} — {', '.join(f.drugs_involved)}")
        print(f"    {f.finding[:120]}")

    print(f"\nReasoning summary: {result.reasoning_summary[:200]}")

    # Acceptance: ≥2 HIGH flags
    if len(high_flags) < 2:
        print(f"\nACCEPTANCE FAILED: expected ≥2 HIGH flags, got {len(high_flags)}")
        return 1

    # Check for the two canonical findings
    metformin_egfr = any(
        "metformin" in " ".join(f.drugs_involved).lower() and f.interaction_type == "drug_lab"
        for f in high_flags
    )
    dizziness_bp = any(
        ("amlodipine" in " ".join(f.drugs_involved).lower() or "telmisartan" in " ".join(f.drugs_involved).lower())
        and f.interaction_type == "drug_symptom"
        for f in high_flags
    )

    if not metformin_egfr:
        print("ACCEPTANCE FAILED: missing Metformin+eGFR HIGH flag")
        return 1
    if not dizziness_bp:
        print("ACCEPTANCE FAILED: missing Amlodipine/Telmisartan+dizziness HIGH flag")
        return 1

    print("\nACCEPTANCE PASSED: 2 canonical HIGH flags confirmed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
