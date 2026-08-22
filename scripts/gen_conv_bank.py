#!/usr/bin/env python3
"""Instance-bank generator and independent reference for problem `conv`.

Reproduces, word for word, the instance construction in
problems/conv/Spec.lean (Knuth-MMIX LCG, HIGH-16-bit centered coefficients,
sequence A seeded with 2n, B with 2n+1, limb width W = n.bit_length() + 32),
and checks the convolution against SymPy polynomial products, closed-form
identities, and the carry-free Kronecker packing lemma. Bank anchors pin the
instance construction itself: a flipped constant anywhere fails loudly.

Run: python3 scripts/gen_conv_bank.py [max_n]
"""
import sys

A, C, M = 6364136223846793005, 1442695040888963407, 1 << 64  # Knuth MMIX


def seq(n, which):
    """Length-n sequence; which: 0 = A (seed input 2n), 1 = B (seed input 2n+1)."""
    r = (A * (2 * n + which + 1) + C) % M
    out = []
    for _ in range(n):
        r = (A * r + C) % M
        out.append((r >> 48) - (1 << 15))
    return out


def conv(a, b):
    c = [0] * (len(a) + len(b) - 1) if a and b else []
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            c[i + j] += x * y
    return c


def W(n):
    return n.bit_length() + 32


def encode(n, cs):
    w, off = W(n), 1 << (W(n) - 1)
    v = 0
    for c in reversed(cs):
        e = c + off
        assert 0 <= e < (1 << w), (n, c)
        v = v * (1 << w) + e
    return v


def convSpec(n):
    return encode(n, conv(seq(n, 0), seq(n, 1)))


BANK_ANCHORS = {
    1: 4120008337,
    2: 36,          # convSpec(n) % 10**6 for n >= 2 (full values are large)
    4: 465812,
    16: 725177,
    64: 642448,
}


def selfcheck():
    assert conv([1, 1], [1, -1]) == [1, 0, -1]
    assert conv([1, 2, 3], [4, 5]) == [4, 13, 22, 15]
    try:
        import random
        import sympy
        x = sympy.symbols('x')
        random.seed(11)
        for _ in range(30):
            a = [random.randint(-2**15, 2**15 - 1) for _ in range(random.randint(1, 40))]
            b = [random.randint(-2**15, 2**15 - 1) for _ in range(random.randint(1, 40))]
            pa = sum(co * x**i for i, co in enumerate(a))
            pb = sum(co * x**i for i, co in enumerate(b))
            prod = sympy.expand(pa * pb)
            want = ([0] if prod == 0 else sympy.Poly(prod, x).all_coeffs()[::-1])
            got = conv(a, b)
            want = want + [0] * (len(got) - len(want))
            assert got == want, (a, b)
        print("selfcheck: identities + SymPy(30 products) OK")
    except ImportError:
        print("selfcheck: identities OK (SymPy unavailable)")
    # Packing losslessness — the actual content of the carry-free lemma: every
    # coefficient is recoverable from the OFFSET encoding by limb extraction,
    # and the encoding equals the signed Kronecker product plus the offset term.
    for n in (3, 8, 20):
        w = W(n)
        B, off = 1 << w, 1 << (w - 1)
        a, b = seq(n, 0), seq(n, 1)
        cs = conv(a, b)
        v = convSpec(n)
        got = [((v >> (w * k)) & (B - 1)) - off for k in range(2 * n - 1)]
        assert got == cs, n                       # limb extraction is lossless
        aB = sum(c * B**i for i, c in enumerate(a))
        bB = sum(c * B**i for i, c in enumerate(b))
        assert v == aB * bB + off * sum(B**k for k in range(2 * n - 1)), n
    print("selfcheck: offset-packing losslessness + affine Kronecker relation OK")
    # Instance-construction anchors (cross-checked against the Lean spec).
    assert convSpec(1) == BANK_ANCHORS[1]
    for n in (2, 4, 16, 64):
        assert convSpec(n) % 10**6 == BANK_ANCHORS[n], n
    print(f"selfcheck: {len(BANK_ANCHORS)} bank anchors OK")


def main():
    selfcheck()
    max_n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    print(f"{'n':<5}{'W':<4}{'output':<44}")
    for n in range(1, max_n + 1):
        v = str(convSpec(n))
        print(f"{n:<5}{W(n):<4}{v if len(v) <= 42 else v[:36] + '...(' + str(len(v)) + 'd)'}")


if __name__ == "__main__":
    main()
