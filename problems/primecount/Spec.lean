/-!
# Lean Competition problem `primecount` — SPEC (trusted, locked)

The prime counting function `π(n)`, specified naively via trial division.
Deliberately quadratic; submissions are expected to compute the value
efficiently and prove it against this spec.
-/

/-- Trial-division primality. -/
def isPrime (p : Nat) : Bool :=
  decide (2 ≤ p) && (List.range p).all (fun d => decide (d < 2) || p % d != 0)

/-- The prime counting function `π(n)`. -/
def primeCountSpec (n : Nat) : Nat :=
  ((List.range (n + 1)).filter isPrime).length

