#!/usr/bin/env python3
"""Independently check the parametric degree-24 polydisc specification.

Python reproduces the public MMIX LCG stream and computes each polynomial's
complete exact discriminant with SymPy.  A temporary Lean module then asks the
Lean kernel to normalize ``discSpec`` and compares the full
integer, not a hash or a bit-length fingerprint.  No generated source or
reference answer is written into the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

import sympy

from problem_layout import evaluation_problem_dir

ROOT = Path(__file__).resolve().parents[1]
PROBLEM_DIR = evaluation_problem_dir(ROOT, "polydisc")
CANDIDATE_SPEC = PROBLEM_DIR / "Spec.lean"
CANDIDATE_SUBMISSION = ROOT / "examples" / "polydisc" / "Submission.lean"
DEFAULT_INPUTS = [1 << 23, 1 << 33, 1 << 43, 1 << 53, 1 << 63]

LCG_A = 6364136223846793005
LCG_C = 1442695040888963407
LCG_MODULUS = 1 << 64


def lcg_next(state: int) -> int:
    return (LCG_A * state + LCG_C) % LCG_MODULUS


def difficulty_level(n: int) -> int:
    if n < 1 << 26:
        return 0
    if n < 1 << 36:
        return 1
    if n < 1 << 46:
        return 2
    if n < 1 << 56:
        return 3
    return 4


def coefficient_width(kbits: int, index: int) -> int:
    """Mirror the public deterministic width profile for index 1 through 24."""

    if kbits <= 64:
        base = 2 * max(0, 36 - kbits) // 7
        span = 10 + base
        width = base + (kbits - base) * index // span
    else:
        numerator = (kbits - 3) * (
            102 * 24 * index - 2 * index * index
        )
        denominator = 100 * 576
        width = 3 + (numerator + denominator - 1) // denominator
    return min(kbits, max(2, width))


def candidate_polynomial(n: int) -> tuple[list[int], int, list[int]]:
    """Return high-to-low coefficients, scale, and per-coefficient widths."""

    kbits = [15, 36, 205, 1001, 3484][difficulty_level(n)]
    state = (LCG_A * (n + 1) + LCG_C) % LCG_MODULUS
    coefficients = [1]
    widths = []
    for index in range(1, 25):
        width = coefficient_width(kbits, index)
        widths.append(width)
        words = (width + 63) // 64
        word = 0
        for shift in range(0, 64 * words, 64):
            state = lcg_next(state)
            word += state << shift
        coefficient = (word >> (64 * words - width)) - (1 << (width - 1))
        coefficients.append(1 if coefficient == 0 else coefficient)
    return coefficients, kbits, widths


def reference_records(inputs: list[int]) -> list[dict[str, object]]:
    x = sympy.symbols("x")
    records: list[dict[str, object]] = []
    for n in inputs:
        coefficients, kbits, widths = candidate_polynomial(n)
        polynomial = sympy.Poly.from_list(coefficients, gens=x, domain=sympy.ZZ)
        discriminant = int(polynomial.discriminant())
        magnitude = abs(discriminant)
        records.append(
            {
                "n": n,
                "level": difficulty_level(n),
                "kbits": kbits,
                "height_bits": max(abs(c).bit_length() for c in coefficients[1:]),
                "total_coefficient_bits": sum(
                    abs(c).bit_length() for c in coefficients[1:]
                ),
                "declared_width_bits": sum(widths),
                "negative": discriminant < 0,
                "magnitude": str(magnitude),
                "discriminant_bits": magnitude.bit_length(),
            }
        )
    return records


def lean_source(records: list[dict[str, object]]) -> str:
    chunks = [
        "import Lean\n",
        "import Spec\n\n",
        "open Lean Elab in\n",
        "run_meta do\n",
        "  let env \u2190 Lean.getEnv\n",
        "  for (label, n, wantNegative, wantBits, wantMagnitude) in [\n",
    ]
    for index, record in enumerate(records):
        comma = "," if index + 1 < len(records) else ""
        label = json.dumps(
            f"n={record['n']} level={record['level']} k={record['kbits']} "
            f"H={record['height_bits']} T={record['total_coefficient_bits']} "
            f"D={record['discriminant_bits']}"
        )
        negative = str(record["negative"]).lower()
        magnitude = json.dumps(record["magnitude"])
        chunks.append(
            f"    ({label}, {record['n']}, {negative}, "
            f"{record['discriminant_bits']}, {magnitude}){comma}\n"
        )
    chunks.extend(
        [
            "  ] do\n",
            "    let start \u2190 IO.monoNanosNow\n",
            "    let outer := Lean.Kernel.whnf env {}\n",
            "      (Lean.mkApp (Lean.mkConst ``discSpec)\n",
            "        (Lean.mkNatLit n))\n",
            "    let normalized : Option (Bool \u00d7 Nat) \u2190 match outer with\n",
            "      | .ok (.app (.const ``Int.ofNat _) value) =>\n",
            "          match Lean.Kernel.whnf env {} value with\n",
            "          | .ok (.lit (.natVal magnitude)) =>\n",
            "              pure (some (false, magnitude))\n",
            "          | _ => pure none\n",
            "      | .ok (.app (.const ``Int.negSucc _) value) =>\n",
            "          match Lean.Kernel.whnf env {} value with\n",
            "          | .ok (.lit (.natVal predecessor)) =>\n",
            "              pure (some (true, predecessor + 1))\n",
            "          | _ => pure none\n",
            "      | _ => pure none\n",
            "    let stop \u2190 IO.monoNanosNow\n",
            "    let got := normalized.map fun (negative, magnitude) =>\n",
            "      let bits := if magnitude == 0 then 0 else Nat.log2 magnitude + 1\n",
            "      (negative, bits, toString magnitude)\n",
            "    let expected := some (wantNegative, wantBits, wantMagnitude)\n",
            "    if got != expected then\n",
            "      throwError \"full discriminant mismatch for {label}\"\n",
            "    IO.println s!\"{label}: {(stop - start) / 1000000} ms exact=true\"\n",
        ]
    )
    return "".join(chunks)


def check_with_lean(records: list[dict[str, object]]) -> int:
    with tempfile.TemporaryDirectory(prefix="polydisc-candidate-") as tmp:
        build_dir = Path(tmp)
        compiled = subprocess.run(
            [
                "lake",
                "env",
                "lean",
                "-R",
                str(CANDIDATE_SPEC.parent),
                "-o",
                str(build_dir / "Spec.olean"),
                str(CANDIDATE_SPEC),
            ],
            cwd=PROBLEM_DIR,
            check=False,
        )
        if compiled.returncode != 0:
            return compiled.returncode

        lake_path = subprocess.check_output(
            ["lake", "env", "printenv", "LEAN_PATH"],
            cwd=PROBLEM_DIR,
            text=True,
        ).strip()
        environment = os.environ.copy()
        environment["LEAN_PATH"] = os.pathsep.join([tmp, lake_path])
        baseline = subprocess.run(
            [
                "lake",
                "env",
                "lean",
                "-R",
                str(CANDIDATE_SUBMISSION.parent),
                "-o",
                str(build_dir / "CandidateSubmission.olean"),
                str(CANDIDATE_SUBMISSION),
            ],
            cwd=PROBLEM_DIR,
            env=environment,
            check=False,
        )
        if baseline.returncode != 0:
            return baseline.returncode
        checked = subprocess.run(
            ["lake", "env", "lean", "--stdin"],
            cwd=PROBLEM_DIR,
            env=environment,
            input=lean_source(records),
            text=True,
            check=False,
        )
        return checked.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        action="append",
        type=int,
        dest="inputs",
        help="nonnegative candidate input; repeat as needed",
    )
    args = parser.parse_args()
    inputs = args.inputs or DEFAULT_INPUTS
    if any(n < 0 for n in inputs):
        parser.error("--input must be nonnegative")
    records = reference_records(inputs)
    return check_with_lean(records)


if __name__ == "__main__":
    raise SystemExit(main())
