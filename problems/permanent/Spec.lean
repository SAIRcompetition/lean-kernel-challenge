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

/-- The instance: a fixed pseudo-random 7×7 0/1 matrix (LCG seed 20260709). -/
def matrixInstance : List (List Nat) := [
  [0, 1, 0, 1, 0, 1, 1],
  [0, 1, 0, 0, 0, 1, 1],
  [1, 1, 1, 1, 0, 0, 1],
  [1, 0, 1, 0, 0, 1, 1],
  [1, 1, 1, 0, 1, 1, 1],
  [1, 0, 1, 0, 1, 1, 0],
  [1, 1, 0, 1, 1, 1, 0]
]

/-- Deterministic n×n 0/1 matrix family (seeded), parametric in n. -/
def genRow (n i : Nat) : List Nat := (List.range n).map (fun j => (i * 31 + j * 17 + 7) % 2)
def genMatrix (n : Nat) : List (List Nat) := (List.range n).map (genRow n)

/-- Parametric spec: permanent of the n-th matrix. -/
def permanentSpecN (n : Nat) : Nat := permanentSpec (genMatrix n)
