#!/usr/bin/env python3
"""Known-answer checks for the four packed, seed-specific Lean specs.

The reference functions below intentionally do not import judge or duplicate
Lean output files.  They implement the public generators in Python, while the
test asks Lean to evaluate the trusted `Spec` modules on the same small inputs.
Frozen answers make an accidental matching change on both sides visible.
"""

import hashlib
import itertools
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASK32 = (1 << 32) - 1


def packed(scale, seed):
    return (scale << 32) | seed


def mix32(value):
    value = ((value ^ (value >> 16)) * 0x7FEB352D) & MASK32
    value = ((value ^ (value >> 15)) * 0x846CA68B) & MASK32
    return (value ^ (value >> 16)) & MASK32


def permanent_matrix_reference(dimension, seed):
    def skip_one(excluded, index):
        return index if index < excluded else index + 1

    def skip_two(a, b, index):
        lo, hi = sorted((a, b))
        value = index if index < lo else index + 1
        return value if value < hi else value + 1

    def entry(i, j):
        if dimension < 3:
            return 1
        row_key = seed ^ (i * 0x9E3779B9)
        first = skip_one(i, mix32(row_key ^ 0x85EBCA6B) % (dimension - 1))
        second = skip_two(
            i, first, mix32(row_key ^ 0xC2B2AE35) % (dimension - 2)
        )
        return int(j in (i, first, second))

    return [
        [entry(i, j) for j in range(dimension)]
        for i in range(dimension)
    ]


def permanent_reference(dimension, seed):
    matrix = permanent_matrix_reference(dimension, seed)
    return sum(
        all(matrix[i][permutation[i]] for i in range(dimension))
        for permutation in itertools.permutations(range(dimension))
    )


def _encode_int(value):
    return 2 * abs(value) - 1 if value < 0 else 2 * value


def saw_reference(length, seed):
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def blocked(point):
        x, y = point
        if y == 0 and x >= 0:
            return False
        mixed = (
            seed
            ^ (_encode_int(x) * 0x9E3779B9)
            ^ (_encode_int(y) * 0x85EBCA6B)
            ^ 0xC2B2AE35
        )
        return mix32(mixed) % 11 == 0

    def count(steps, point, visited):
        if steps == 0:
            return 1
        total = 0
        for dx, dy in directions:
            next_point = (point[0] + dx, point[1] + dy)
            if next_point in visited or blocked(next_point):
                continue
            visited.add(next_point)
            total += count(steps - 1, next_point, visited)
            visited.remove(next_point)
        return total

    return count(length, (0, 0), {(0, 0)})


def ca_reference(steps, seed):
    row = [
        True if i == 0 else
        False if i == 1 else
        bool((mix32(seed + (i + 1) * 0x9E3779B9) >> 31) & 1)
        for i in range(256)
    ]

    def rule110(left, center, right):
        return (left, center, right) not in {
            (True, True, True),
            (True, False, False),
            (False, False, False),
        }

    for _ in range(steps):
        row = [
            rule110(row[(i - 1) % 256], row[i], row[(i + 1) % 256])
            for i in range(256)
        ]
    return sum(int(bit) << i for i, bit in enumerate(row))


def sha256_reference(steps, seed):
    words = []
    state = seed & MASK32
    for _ in range(8):
        state = (1664525 * state + 1013904223) & MASK32
        words.append(state)
    digest = b"".join(word.to_bytes(4, "big") for word in words)
    for _ in range(steps):
        digest = hashlib.sha256(digest).digest()
    return int.from_bytes(digest, "big")


CASES = {
    "permanent": {
        "spec": "permanentSpecN",
        "reference": permanent_reference,
        "vectors": [
            (0, MASK32, 1),
            (1, 0, 1),
            (2, MASK32, 2),
            (3, 1, 6),
            (4, MASK32, 9),
        ],
    },
    "saw": {
        "spec": "sawSpec",
        "reference": saw_reference,
        "vectors": [
            (0, MASK32, 1),
            (1, 0, 4),
            (4, 1, 62),
            (5, MASK32, 162),
        ],
    },
    "ca-rule110": {
        "spec": "caSpecN",
        "reference": ca_reference,
        "vectors": [
            (0, MASK32,
             39182519112023866544536036211526227574914928668350269117402648292207235003753),
            (1, 0,
             28790360432100359675900384225747522345744538390329335443481557656821485535085),
            (3, 1,
             50446023508594522752218378513672912399469115759546551205210818808364694200440),
            (3, MASK32,
             57946779343320518290994834605164800604358144145646316131344707774039196456965),
        ],
    },
    "sha256": {
        "spec": "sha256Spec",
        "reference": sha256_reference,
        "vectors": [
            (0, MASK32,
             27289928277517450473726143143723056889608837264336340939145516705529457565575),
            (1, 0,
             4221607917069570966164243239090007043043907574719640821053522951032627001827),
            (2, 1,
             12951784694840770977245544593908270174466873362802972520527567559343483793530),
            (2, MASK32,
             26532797636208419703597189387299034950736569895671931202685968991573420836534),
        ],
    },
}


def lean_values(problem, spec_name, vectors):
    workspace = ROOT / "problems" / problem
    subprocess.run(
        ["lake", "build", "Spec"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    source = "import Spec\n" + "\n".join(
        f"#eval {spec_name} {packed(scale, seed)}"
        for scale, seed, _ in vectors
    ) + "\n"
    result = subprocess.run(
        ["lake", "env", "lean", "--stdin"],
        cwd=workspace,
        input=source,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    values = [
        int(line)
        for line in result.stdout.splitlines()
        if re.fullmatch(r"[0-9]+", line)
    ]
    if len(values) != len(vectors):
        raise AssertionError(
            f"Lean printed {len(values)} values for {problem}, expected {len(vectors)}; "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        )
    return values


class PackedInstanceKnownAnswerTests(unittest.TestCase):
    def test_permanent_generator_has_fixed_row_degree_and_diagonal(self):
        for dimension in (3, 4, 8, 12):
            for seed in (0, 1, MASK32, 0x12345678):
                matrix = permanent_matrix_reference(dimension, seed)
                with self.subTest(dimension=dimension, seed=seed):
                    self.assertTrue(all(sum(row) == 3 for row in matrix))
                    self.assertTrue(all(matrix[i][i] == 1 for i in range(dimension)))

    def test_packing_covers_zero_scale_and_seed_boundaries(self):
        for problem, case_set in CASES.items():
            with self.subTest(problem=problem):
                self.assertTrue(any(scale == 0 for scale, _, _ in case_set["vectors"]))
                self.assertTrue(any(seed == 0 for _, seed, _ in case_set["vectors"]))
                self.assertTrue(any(seed == MASK32 for _, seed, _ in case_set["vectors"]))
                for scale, seed, _ in case_set["vectors"]:
                    value = packed(scale, seed)
                    self.assertEqual(value >> 32, scale)
                    self.assertEqual(value & MASK32, seed)

    def test_independent_references_match_frozen_answers(self):
        for problem, case_set in CASES.items():
            reference = case_set["reference"]
            for scale, seed, expected in case_set["vectors"]:
                with self.subTest(problem=problem, scale=scale, seed=seed):
                    self.assertEqual(reference(scale, seed), expected)

    def test_lean_specs_match_independent_references(self):
        for problem, case_set in CASES.items():
            with self.subTest(problem=problem):
                expected = [value for _, _, value in case_set["vectors"]]
                self.assertEqual(
                    lean_values(problem, case_set["spec"], case_set["vectors"]),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
