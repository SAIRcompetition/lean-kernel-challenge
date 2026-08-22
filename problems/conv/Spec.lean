/-!
# Lean Kernel Challenge problem `conv` — SPEC (trusted, locked)

Integer convolution — the arithmetic core of a neural network's convolution
layer, and equally the coefficient product of two integer polynomials:
`c_k = Σ_{i+j=k} a_i · b_j`, computed by the naive double sum, O(n²) integer
multiplications, deliberately.

The instance bank is parametric in `n` and auditable (generator:
`scripts/gen_conv_bank.py`, cross-checked against SymPy polynomial products and
closed-form identities): two length-`n` sequences of centered 16-bit signed
coefficients drawn from the HIGH 16 bits of Knuth-MMIX LCG words (low LCG bits
are periodic — see problem `polydisc`), sequence A seeded with `2n`, sequence B
with `2n+1`. Difficulty scales with the length alone.

The result — `2n−1` coefficients with `|c_k| ≤ n·2^30` — is returned as one
natural number: each coefficient is offset by `2^(W−1)` into a nonnegative
`W`-bit limb, `W = Nat.log2 n + 33`, and the limbs are packed positionally
(`Σ e_k · 2^(W·k)`, coefficient 0 lowest). `2^(W−1) > n·2^30` makes every limb
fit, so the encoding is lossless. Reference values: `convSpec 1 = 4120008337`
(one product of two centered 16-bit values, offset by 2^32).

Fair warning, which is also the point of the problem: with carry-free limbs
this encoding equals the SIGNED evaluation product plus a fixed offset term —
`encode = a(B)·b(B) + 2^(W-1)·Σ_k B^k` at `B = 2^W`, where `a(B)`, `b(B)` are
Int evaluations that are genuinely negative on real instances — Kronecker
substitution plus an affine correction. Proving that packing lemma (carry
freeness, signed-to-offset conversion) and letting the kernel's native
big-number multiplication do the convolution IS the intended top of the
ladder; the contest above that rung is the constant-factor race in packing and
extraction, and below it Karatsuba-style algorithms on honest lists.
-/

/-- Knuth MMIX LCG: multiplier, increment, modulus 2^64. -/
def lcgA : Nat := 6364136223846793005
def lcgC : Nat := 1442695040888963407
def lcgM : Nat := 18446744073709551616

def lcgNext (r : Nat) : Nat := (lcgA * r + lcgC) % lcgM

def lcgSeed (s : Nat) : Nat := (lcgA * (s + 1) + lcgC) % lcgM

/-- `j` LCG steps from `r`. -/
def lcgIter : Nat → Nat → Nat
  | 0, r => r
  | j + 1, r => lcgIter j (lcgNext r)

/-- Element `i` of the sequence with seed input `s`: the HIGH 16 bits of stream
word `i+1`, centered to `[-2^15, 2^15)`. -/
def elemAt (s i : Nat) : Int :=
  Int.ofNat (lcgIter (i + 1) (lcgSeed s) >>> 48) - Int.ofNat (2 ^ 15)

/-- Instance sequences: A uses seed input `2n`, B uses `2n+1`; both length `n`. -/
def seqA (n : Nat) : List Int := (List.range n).map (elemAt (2 * n))
def seqB (n : Nat) : List Int := (List.range n).map (elemAt (2 * n + 1))

/-- Convolution coefficient `k`: the naive sum `Σ_{i≤k} a_i · b_{k-i}`
(out-of-range indices contribute 0). -/
def convAt (a b : List Int) (k : Nat) : Int :=
  (List.range (k + 1)).foldl (fun acc i => acc + a.getD i 0 * b.getD (k - i) 0) 0

/-- The full convolution: `len a + len b - 1` coefficients. -/
def convList (a b : List Int) : List Int :=
  (List.range (a.length + b.length - 1)).map (convAt a b)

/-- Limb width for instance `n`: `2^(W-1) > n·2^30 ≥ max |c_k|`. -/
def limbW (n : Nat) : Nat := Nat.log2 n + 33

/-- Pack coefficients into one Nat: coefficient `k`, offset into a nonnegative
`W`-bit limb, occupies bits `[W·k, W·(k+1))`. -/
def encode (W : Nat) (cs : List Int) : Nat :=
  cs.foldr (fun c acc => (c + Int.ofNat (2 ^ (W - 1))).toNat + acc * 2 ^ W) 0

/-- Parametric spec: the packed convolution of instance `n`'s two sequences. -/
def convSpec (n : Nat) : Nat := encode (limbW n) (convList (seqA n) (seqB n))
