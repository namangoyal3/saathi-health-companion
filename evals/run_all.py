"""Run all evals and exit non-zero if any acceptance criterion fails."""

from __future__ import annotations

import asyncio
import sys

from evals.eval_ddi_canonical import main as ddi_main
from evals.eval_lab_vision import main as lab_main
from evals.eval_safety_redteam import main as safety_main


async def main() -> int:
    results: dict[str, int] = {}

    print("=" * 60)
    print("eval_safety_redteam")
    print("=" * 60)
    results["safety"] = await safety_main()

    print("\n" + "=" * 60)
    print("eval_ddi_canonical")
    print("=" * 60)
    results["ddi"] = await ddi_main()

    print("\n" + "=" * 60)
    print("eval_lab_vision")
    print("=" * 60)
    results["lab"] = await lab_main()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, code in results.items():
        status = "PASS" if code == 0 else "FAIL"
        print(f"  {name:20s} {status}")
        if code != 0:
            all_passed = False

    print()
    if all_passed:
        print("All evals passed.")
        return 0
    else:
        print("One or more evals FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
