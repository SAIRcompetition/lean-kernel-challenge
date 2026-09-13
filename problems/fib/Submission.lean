import Spec

namespace Submission

/-- TODO 1: Optimize this body. Keep the function total and kernel-reducible. -/
def impl (n : Nat) : Nat := Nat.fastFib n

/-- TODO 2: Prove that `impl n` equals Mathlib's `Nat.fib n` for every natural number n.
Keep the theorem statement unchanged. -/
theorem impl_correct : ∀ n, impl n = Nat.fib n := by
  intro n
  exact Nat.fastFib_eq n

end Submission
