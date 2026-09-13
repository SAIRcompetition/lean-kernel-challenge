import Spec

namespace Submission

def isPrime (p : Nat) : Bool := decide (2 ≤ p) && (Nat.minFac p == p)

theorem isPrime_eq (p : Nat) : isPrime p = decide (Nat.Prime p) := by
  apply Bool.eq_iff_iff.mpr
  simp [isPrime, Nat.prime_def_minFac]

/-- TODO 1: Optimize this implementation, which uses Mathlib's `Nat.minFac`.
Keep it total and kernel-reducible. -/
def impl (n : Nat) : Nat := (List.range (n + 1)).countP isPrime

/-- TODO 2: Prove equality with Mathlib's `Nat.primeCounting` for every natural number n.
Keep the theorem statement unchanged. -/
theorem impl_correct : ∀ n, impl n = primeCountSpec n := by
  intro n
  simp only [impl, primeCountSpec, Nat.primeCounting, Nat.primeCounting', Nat.count,
    List.countP_eq_length_filter]
  rw [List.filter_congr (fun p _ => isPrime_eq p)]

end Submission
