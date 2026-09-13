import Mathlib.NumberTheory.ArithmeticFunction.Moebius

/-- The Mertens function, summing Mathlib's Möbius function over `0 ≤ k ≤ n`.
Mathlib defines the zero term to be zero. -/
def mertensSpec (n : Nat) : Int :=
  ∑ k ∈ Finset.range (n + 1), ArithmeticFunction.moebius k
