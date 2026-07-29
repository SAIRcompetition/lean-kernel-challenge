/-!
# Lean Competition problem `partition` — SPEC (trusted, locked)

The partition function `p(n)`: the number of ways to write `n` as a sum of
positive integers, disregarding order. Specified by the textbook recurrence on
the largest allowed part, grouped by the multiplicity of that part.

Deliberately naive: kernel-evaluating this recurrence has no memoization, so
its cost is roughly `p(n) · n`. Submissions are expected to compute the value
efficiently and prove it against this spec.
-/

/-- `partAux k n` = number of partitions of `n` into parts of size ≤ `k`,
counted by how many copies `j` of the largest part `k` are used. -/
def partAux : Nat → Nat → Nat
  | 0, 0 => 1
  | 0, _ + 1 => 0
  | k + 1, n =>
    ((List.range (n / (k + 1) + 1)).map (fun j => partAux k (n - j * (k + 1)))).foldl (· + ·) 0

/-- The partition function. -/
def partitionSpec (n : Nat) : Nat := partAux n n

