import Spec

/-! Baseline: count primes using Mathlib's smallest-prime-factor function. -/

namespace Submission

def isPrime (p : Nat) : Bool := decide (2 ≤ p) && (Nat.minFac p == p)

theorem isPrime_eq (p : Nat) : isPrime p = decide (Nat.Prime p) := by
  apply Bool.eq_iff_iff.mpr
  simp [isPrime, Nat.prime_def_minFac]

def impl (n : Nat) : Nat := (List.range (n + 1)).countP isPrime

theorem impl_correct : ∀ n, impl n = primeCountSpec n := by
  intro n
  simp only [impl, primeCountSpec, Nat.primeCounting, Nat.primeCounting', Nat.count,
    List.countP_eq_length_filter]
  rw [List.filter_congr (fun p _ => isPrime_eq p)]

end Submission
