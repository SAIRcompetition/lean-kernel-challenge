#!/usr/bin/env python3
"""Instance-bank generator and independent reference for problem `polydisc`.

Reproduces, word for word, the instance construction in
problems/polydisc/Spec.lean (Knuth-MMIX LCG -> centered k-bit coefficients,
degree min(2 + n//2, 24), width 4 + 8*max(0, n-44) bits), and checks the
discriminant against an INDEPENDENT reference: Sylvester matrix + fraction
Gaussian elimination, cross-checked against classical closed-form identities
(quadratic, depressed and general cubic, cyclotomic Phi_5, repeated roots) and,
when available, SymPy across degrees 2..24.

Run: python3 scripts/gen_polydisc_bank.py [max_n]
Prints the bank table and exits nonzero on any mismatch.
"""
import sys
from fractions import Fraction

A, C, M = 6364136223846793005, 1442695040888963407, 1 << 64  # Knuth MMIX


def degree(n): return min(2 + n // 2, 24)
def kbits(n): return 4 + 8 * max(0, n - 44)


def coeffs(n):
    """Monic, high-to-low: [1, a_(d-1), ..., a_0], a_i in [-2^(k-1), 2^(k-1))."""
    d, k = degree(n), kbits(n)
    words_per = (k + 63) // 64
    r = (A * (n + 1) + C) % M
    out = [1]
    for _ in range(d):
        w = 0
        for j in range(words_per):
            r = (A * r + C) % M
            w |= r << (64 * j)
        out.append((w >> (64 * words_per - k)) - (1 << (k - 1)))
    return out


def deriv(p):
    d = len(p) - 1
    return [(d - i) * p[i] for i in range(d)]


def sylvester(p, q):
    dp, dq = len(p) - 1, len(q) - 1
    return ([[0] * i + p + [0] * (dq - 1 - i) for i in range(dq)]
            + [[0] * i + q + [0] * (dp - 1 - i) for i in range(dp)])


def det_frac(m):
    m = [[Fraction(x) for x in row] for row in m]
    n, sign, det = len(m), 1, Fraction(1)
    for c in range(n):
        piv = next((r for r in range(c, n) if m[r][c] != 0), None)
        if piv is None:
            return 0
        if piv != c:
            m[c], m[piv] = m[piv], m[c]
            sign = -sign
        det *= m[c][c]
        for r in range(c + 1, n):
            f = m[r][c] / m[c][c]
            for cc in range(c, n):
                m[r][cc] -= f * m[c][cc]
    v = sign * det
    assert v.denominator == 1
    return int(v)


def disc(p):
    d = len(p) - 1
    return (-1 if (d * (d - 1) // 2) % 2 else 1) * det_frac(sylvester(p, deriv(p)))


BANK_ANCHORS = {
    0: -8,
    5: 44688,
    6: -327148848,
    60: -28968410430613311944536224933180784661283801064590930377643370677423701503329327223795094769215513316450695555799735612698137886710033736613637885196937526877114646947755159041323899718640225431073914750776429870882051125367565631973335802751258918746798533513136986506176016210947606423549557999310006952144563374189982563957908696653152593840076403465605406688295256575769124870668269215522542462926559579797375639149138737823706814048478979598344313966864330263276116566868644621720682304038257972303761987204723906700313337755544106893598420625616757795200762217662074409521882258213406506589235429634745390684443028762604196555305573884498635852298586235051570498312094934952627072703905294712367321415184219678148471542878020877316791828335972149990693047754125392193680096478390990746699008768571879190563493631361025310206393774678698180316026879406368823928857193463732194212993295453961932732522760359298360619930101184396542128287464863205328986287111202078774158763444706725069011021576025347958344652933185871605099870869210225982657485228538211929833874163577919870253916662699382688172945044676733365435912616216884153221366218549205081749015759350684424016788070641756612578475198689053909841890307395536415373317565179876598949086999359204994833156619880083685291904444510446773439571448474449080675573640611312307532717726988652009615949854041281870919914340129575980662873979829833723799693203598141595659448583989094368574390402575835922837378507797807060924716392600624323031884106107857293743813260325713357542002209220744456018835252162675087928111512041079251973050352768243815990859201736492596806290176827269900356290400973884105330305116640913129359927268465456119801483742210689983452655053296699781906430993460442612817462668160503658617131741098499325424608683086659608931515823434616139953434442155752606150390528,
}


def selfcheck():
    assert disc([1, 5, 3]) == 25 - 12                       # b^2 - 4c
    assert disc([1, 0, -2, 1]) == -4 * (-2) ** 3 - 27      # depressed cubic
    a, b, c = 2, -7, 3                                      # general cubic
    assert disc([1, a, b, c]) == 18*a*b*c - 4*a**3*c + a*a*b*b - 4*b**3 - 27*c*c
    assert disc([1, 1, 1, 1, 1]) == 125                     # disc(Phi_5) = 5^3
    assert disc([1, -2, 1]) == 0                            # (x-1)^2
    assert disc([1, 0, 0, 0]) == 0                          # x^3
    try:
        import random
        import sympy
        x = sympy.symbols('x')
        random.seed(7)
        for _ in range(40):
            d = random.randint(2, 24)
            p = [1] + [random.randint(-10**6, 10**6) for _ in range(d)]
            sp = sum(co * x**(d - i) for i, co in enumerate(p))
            assert sympy.Poly(sp, x).discriminant() == disc(p), p
        print("selfcheck: identities + SymPy(40 cases, deg 2..24) OK")
    except ImportError:
        print("selfcheck: identities OK (SymPy unavailable)")
    # Anchor the INSTANCE CONSTRUCTION itself (LCG constants, seeding, packing,
    # high-bit extraction, centering): these values are cross-checked against the
    # Lean spec (compiled #eval and the judge's kernel-checked path). A flipped
    # constant anywhere in the pipeline fails here. n=60 exercises multi-word
    # coefficients (words_per > 1). Regenerate on any deliberate bank change.
    for n, want in BANK_ANCHORS.items():
        got = disc(coeffs(n))
        assert got == want, f"bank anchor n={n}: got {got}, want {want}"
    print(f"selfcheck: {len(BANK_ANCHORS)} bank anchors OK")


def main():
    selfcheck()
    max_n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    print(f"{'n':<4}{'deg':<5}{'kbits':<7}{'discriminant':<44}")
    for n in range(max_n + 1):
        v = str(disc(coeffs(n)))
        print(f"{n:<4}{degree(n):<5}{kbits(n):<7}"
              f"{v if len(v) <= 42 else v[:36] + '...(' + str(len(v)) + 'd)'}")


if __name__ == "__main__":
    main()
