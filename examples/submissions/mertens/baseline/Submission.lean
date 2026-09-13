import Spec

/-! Baseline: sum Mathlib's Möbius function. -/

namespace Submission

def impl (n : Nat) : Int := mertensSpec n

theorem impl_correct : ∀ n, impl n = mertensSpec n := by
  intro n
  rfl

end Submission
