#!/usr/bin/env python3
"""Print and independently verify the public polydisc scale anchors.

The generator is shared with `check_polydisc_candidate.py`; every displayed
discriminant is computed independently with SymPy from the generated degree-24
coefficient list.
"""

from __future__ import annotations

import argparse

from check_polydisc_candidate import DEFAULT_INPUTS, reference_records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", action="append", type=int, dest="inputs",
        help="nonnegative input to print; repeat as needed",
    )
    args = parser.parse_args()
    inputs = args.inputs or DEFAULT_INPUTS
    if any(n < 0 for n in inputs):
        parser.error("--input must be nonnegative")

    print("n\tlevel\tkbits\theight_bits\ttotal_coeff_bits\tdisc_bits\tsign")
    for record in reference_records(inputs):
        sign = "-" if record["negative"] else "+"
        print(
            f"{record['n']}\t{record['level']}\t{record['kbits']}\t"
            f"{record['height_bits']}\t{record['total_coefficient_bits']}\t"
            f"{record['discriminant_bits']}\t{sign}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
