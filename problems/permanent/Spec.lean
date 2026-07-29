/-!
# Lean Competition problem `permanent` — SPEC (trusted, locked)

The permanent of a 0/1 matrix, specified by direct summation over all
permutations (Leibniz formula without signs). Deliberately factorial-cost;
submissions are expected to compute the value efficiently (e.g. Ryser's
formula) and prove it against this spec.
-/

/-- All ways to insert `x` into a list. -/
def insertions (x : Nat) : List Nat → List (List Nat)
  | [] => [[x]]
  | y :: ys => (x :: y :: ys) :: (insertions x ys).map (y :: ·)

/-- All permutations of a list. -/
def perms : List Nat → List (List Nat)
  | [] => [[]]
  | x :: xs => (perms xs).flatMap (insertions x)

/-- Product of the entries selected by a permutation. -/
def diagProd (m : List (List Nat)) (σ : List Nat) : Nat :=
  ((m.zip σ).map (fun rj => rj.1.getD rj.2 0)).foldl (· * ·) 1

/-- The permanent. -/
def permanentSpec (m : List (List Nat)) : Nat :=
  ((perms (List.range m.length)).map (diagProd m)).foldl (· + ·) 0

/-- Deterministic n×n 0/1 matrix family, parametric in `n`. Off-diagonal entries are a bit
    of a Knuth multiplicative hash of `(i, j)` (from a high position, so it is not a
    checkerboard); the diagonal is forced to 1 so the matrix always has at least the
    identity as a perfect matching — hence a non-zero, non-degenerate permanent for every n
    (the pseudo-random off-diagonal makes it grow non-trivially: p(7)=133, p(12)=240758, …). -/
def genRow (n i : Nat) : List Nat :=
  (List.range n).map (fun j =>
    if i = j then 1 else ((i * 2654435761 + j * 2246822519 + 1013904223) >>> 16) % 2)
def genMatrix (n : Nat) : List (List Nat) := (List.range n).map (genRow n)

/-- Parametric spec: permanent of the n-th matrix. -/
def permanentSpecN (n : Nat) : Nat := permanentSpec (genMatrix n)
