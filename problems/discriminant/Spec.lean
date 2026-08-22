/-!
# Lean Kernel Challenge problem `discriminant` — SPEC (trusted, locked)

The discriminant of a monic integer polynomial, computed the textbook way:
`disc(p) = (-1)^(d(d-1)/2) · Res(p, p')`, with the resultant as the determinant
of the Sylvester matrix of `p` and `p'`, and the determinant by naive Laplace
cofactor expansion along the first row — exponential in the matrix size, and
deliberately so.

The instance bank is parametric in `n` and auditable: coefficients come from a
Knuth-MMIX LCG seeded with `n` (generator script:
`scripts/gen_discriminant_bank.py`, which also cross-checks this construction
against an independent fraction-elimination reference and SymPy). Degree ramps as
`min (2 + n/2) 24` — two inputs per degree, the classical head where the naive
spec is feasible — and once the degree caps at 24 (n = 44) the coefficient
width grows by 8 bits per step (`4 + 8·(n-44)`), so large `n` is a fixed-shape
47×47 determinant over ever bigger integers. Reference values:
`discSpec 0 = -8`, `discSpec 5 = 44688`, `discSpec 6 = -327148848`.

The determinant recursion carries explicit fuel that strictly decreases on
every call edge, keeping the definition structurally recursive (well-founded
recursion would not reduce in the kernel). Fuel bounds recursion *depth* — one
`detWork` level plus one `cofWork` chain of length ≤ size+1 per matrix size —
so `(N+2)²` is a generous, obviously sufficient budget for an N×N matrix; the
zero-fuel fallbacks are unreachable.
-/

/-- Knuth MMIX LCG: multiplier, increment, modulus 2^64. -/
def lcgA : Nat := 6364136223846793005
def lcgC : Nat := 1442695040888963407
def lcgM : Nat := 18446744073709551616

def lcgNext (r : Nat) : Nat := (lcgA * r + lcgC) % lcgM

def lcgSeed (n : Nat) : Nat := (lcgA * (n + 1) + lcgC) % lcgM

/-- `j` LCG steps from `r`. -/
def lcgIter : Nat → Nat → Nat
  | 0, r => r
  | j + 1, r => lcgIter j (lcgNext r)

/-- Instance degree: ramps 2, 2, 3, 3, … (two inputs per degree) and caps at 24. -/
def degreeOf (n : Nat) : Nat := min (2 + n / 2) 24

/-- Coefficient width in bits: 4 in the ramp head, then +8 per step past n = 44. -/
def kbitsOf (n : Nat) : Nat := 4 + 8 * (n - 44)

/-- The pre-mod word for coefficient `i`: `m` consecutive 64-bit LCG words,
little-endian (stream word `i·m + j` shifted by `64·j`). -/
def coeffWord (n i m : Nat) : Nat :=
  (List.range m).foldl
    (fun acc j => acc + lcgIter (i * m + j + 1) (lcgSeed n) * 2 ^ (64 * j)) 0

/-- Coefficient `i` (0 = the x^(d-1) coefficient): centered `k`-bit signed value.
The HIGH `k` bits of the `64·m`-bit word are used: the low bits of a
power-of-two-modulus LCG are periodic (period `2^k` for the low `k` bits), so
low-bit extraction would draw every small-width coefficient from one short
public cycle. -/
def coeffAt (n i : Nat) : Int :=
  let k := kbitsOf n
  let m := (k + 63) / 64
  Int.ofNat (coeffWord n i m >>> (64 * m - k)) - Int.ofNat (2 ^ (k - 1))

/-- The instance polynomial, monic, coefficients high-to-low: `[1, a_(d-1), …, a_0]`. -/
def polyOf (n : Nat) : List Int :=
  1 :: (List.range (degreeOf n)).map (coeffAt n)

/-- Formal derivative of a high-to-low coefficient list. -/
def derivHL (p : List Int) : List Int :=
  let d := p.length - 1
  (List.range d).map fun i => Int.ofNat (d - i) * p.getD i 0

def zeros (k : Nat) : List Int := List.replicate k 0

/-- Sylvester matrix of `p` (degree dp) and `q` (degree dq): `dq` shifted copies
of `p` above `dp` shifted copies of `q`, size `(dp+dq)²`. -/
def sylvester (p q : List Int) : List (List Int) :=
  let dp := p.length - 1
  let dq := q.length - 1
  ((List.range dq).map fun i => zeros i ++ p ++ zeros (dq - 1 - i)) ++
  ((List.range dp).map fun i => zeros i ++ q ++ zeros (dp - 1 - i))

/-- Drop column `j` from every row. -/
def minorAt (j : Nat) (rows : List (List Int)) : List (List Int) :=
  rows.map fun row => row.take j ++ row.drop (j + 1)

mutual
  /-- Determinant by Laplace expansion along the first row; fuel strictly
  decreases on every call edge (see header). Zero fuel is unreachable. -/
  def detWork : Nat → List (List Int) → Int
    | _, [] => 1
    | 0, _ :: _ => 0
    | f + 1, r :: rows => cofWork f r rows 0

  /-- Cofactor chain: `Σ_j (-1)^j · r_j · det(minor_j)`, walking the first row. -/
  def cofWork : Nat → List Int → List (List Int) → Nat → Int
    | 0, _, _, _ => 0
    | _ + 1, [], _, _ => 0
    | f + 1, a :: rest, rows, j =>
      (if j % 2 = 0 then a else -a) * detWork f (minorAt j rows)
        + cofWork f rest rows (j + 1)
end

def det (m : List (List Int)) : Int := detWork ((m.length + 2) ^ 2) m

/-- Parametric spec: the discriminant of instance `n`'s monic polynomial. -/
def discSpec (n : Nat) : Int :=
  let p := polyOf n
  let d := degreeOf n
  (if d * (d - 1) / 2 % 2 = 0 then (1 : Int) else -1) * det (sylvester p (derivHL p))
