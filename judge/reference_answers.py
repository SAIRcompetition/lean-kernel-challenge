"""Organizer-owned exact answers for the nine Stage 1 problems.

No contestant code, Lean elaboration, network, or third-party packages are used.
The answer bundle is prepared once per hidden plan and consumed before any
untrusted process starts. It is data, never a replacement for the kernel check.
"""

import hashlib
import json
import re
import sys

if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

SCHEMA = "reference-answers-v1"
MAX_BUNDLE_BYTES = 8 * 1024 * 1024
OUTPUT_TYPES = {
    "fib": "Nat", "partition": "Nat", "mertens": "Int", "primecount": "Nat",
    "permanent": "Nat", "saw": "Nat", "ca-rule110": "Nat", "sha256": "Nat",
    "polydisc": "Int",
}

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
    states = {0: 1}
    for row in matrix:
        following = {}
        for mask, count in states.items():
            for column, enabled in enumerate(row):
                bit = 1 << column
                if enabled and not mask & bit:
                    following[mask | bit] = following.get(mask | bit, 0) + count
        states = following
    return states.get((1 << dimension) - 1, 0)


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


def determinant(matrix):
    """Exact fraction-free Bareiss elimination, with row pivoting."""
    a = [list(row) for row in matrix]
    size = len(a)
    if size == 0:
        return 1
    previous, sign = 1, 1
    for k in range(size - 1):
        pivot_row = next((i for i in range(k, size) if a[i][k]), None)
        if pivot_row is None:
            return 0
        if pivot_row != k:
            a[k], a[pivot_row] = a[pivot_row], a[k]
            sign = -sign
        pivot = a[k][k]
        for i in range(k + 1, size):
            for j in range(k + 1, size):
                numerator = a[i][j] * pivot - a[i][k] * a[k][j]
                value, remainder = divmod(numerator, previous)
                if remainder:
                    raise ValueError("non-exact Bareiss division")
                a[i][j] = value
            a[i][k] = 0
        previous = pivot
    return sign * a[-1][-1]


def polynomial_discriminant(coefficients):
    """Discriminant via the Sylvester resultant of f and f'."""
    degree = len(coefficients) - 1
    derivative = [c * (degree - i) for i, c in enumerate(coefficients[:-1])]
    matrix = [
        [0] * i + coefficients + [0] * (degree - 2 - i)
        for i in range(degree - 1)
    ] + [
        [0] * i + derivative + [0] * (degree - 1 - i)
        for i in range(degree)
    ]
    resultant = determinant(matrix)
    value, remainder = divmod(resultant, coefficients[0])
    if remainder:
        raise ValueError("non-exact discriminant division")
    return (-1) ** (degree * (degree - 1) // 2) * value


def fibonacci(n):
    a, b = 0, 1
    for bit in bin(n)[2:]:
        c, d = a * (2 * b - a), a * a + b * b
        a, b = (c, d) if bit == "0" else (d, c + d)
    return a


def partition(n):
    counts = [1] + [0] * n
    for part in range(1, n + 1):
        for total in range(part, n + 1):
            counts[total] += counts[total - part]
    return counts[n]


def sieve(n):
    primes = [True] * (n + 1)
    primes[0] = False
    if n:
        primes[1] = False
    for p in range(2, n + 1):
        if primes[p]:
            for k in range(p * p, n + 1, p):
                primes[k] = False
    return [p for p, prime in enumerate(primes) if prime]


def mertens(n):
    mu = [1] * (n + 1)
    mu[0] = 0
    for p in sieve(n):
        for k in range(p, n + 1, p):
            mu[k] *= -1
        for k in range(p * p, n + 1, p * p):
            mu[k] = 0
    return sum(mu)


def compute_answer(problem, n):
    if problem not in OUTPUT_TYPES or type(n) is not int or n < 0:
        raise ValueError("unsupported reference problem or input")
    if problem == "fib":
        return fibonacci(n)
    if problem == "partition":
        return partition(n)
    if problem == "mertens":
        return mertens(n)
    if problem == "primecount":
        return len(sieve(n))
    if problem == "polydisc":
        return polynomial_discriminant(candidate_polynomial(n)[0])
    functions = {"permanent": permanent_reference, "saw": saw_reference,
                 "ca-rule110": ca_reference, "sha256": sha256_reference}
    return functions[problem](n >> 32, n & MASK32)


def canonical_bytes(bundle):
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def prepare(problem, inputs, spec_sha256):
    bundle = {
        "schema": SCHEMA, "problem": problem, "spec_sha256": spec_sha256,
        "answers": [
            {"n": n, "type": OUTPUT_TYPES[problem], "value": str(compute_answer(problem, n))}
            for n in inputs
        ],
    }
    validate(bundle, problem, inputs, spec_sha256)
    return bundle


def validate(bundle, problem, inputs, spec_sha256):
    """Reject mismatched, missing, duplicate, or noncanonical answers before judging."""
    if (not isinstance(bundle, dict)
            or set(bundle) != {"schema", "problem", "spec_sha256", "answers"}
            or bundle["schema"] != SCHEMA or bundle["problem"] != problem
            or bundle["spec_sha256"] != spec_sha256
            or not re.fullmatch(r"[0-9a-f]{64}", spec_sha256)
            or problem not in OUTPUT_TYPES
            or not isinstance(bundle["answers"], list)
            or len(bundle["answers"]) != len(inputs)
            or not inputs or len(set(inputs)) != len(inputs)):
        raise ValueError("reference answers do not match the problem, specification, or plan")
    values = {}
    for n, answer in zip(inputs, bundle["answers"]):
        if (not isinstance(answer, dict) or set(answer) != {"n", "type", "value"}
                or type(answer["n"]) is not int or answer["n"] != n
                or answer["type"] != OUTPUT_TYPES[problem]
                or not isinstance(answer["value"], str)
                or not re.fullmatch(r"0|[1-9][0-9]*|-[1-9][0-9]*", answer["value"])
                or (answer["type"] == "Nat" and answer["value"].startswith("-"))):
            raise ValueError("reference answer has an invalid coordinate, type, or literal")
        values[n] = answer["value"]
    if len(canonical_bytes(bundle)) > MAX_BUNDLE_BYTES:
        raise ValueError("reference answer bundle is too large")
    return values


def seal(bundle):
    return {"contract": SCHEMA, "sha256": hashlib.sha256(canonical_bytes(bundle)).hexdigest(),
            "spec_sha256": bundle["spec_sha256"], "count": len(bundle["answers"])}
