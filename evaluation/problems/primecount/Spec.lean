import Mathlib.NumberTheory.PrimeCounting

/-- Mathlib's prime-counting function: the number of primes at most `n`. -/
def primeCountSpec : Nat → Nat := Nat.primeCounting
