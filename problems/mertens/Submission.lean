import Spec

namespace Submission

/-- TODO 1: Optimize this implementation. Keep it total and kernel-reducible. -/
def impl (n : Nat) : Int := mertensSpec n

/-- TODO 2: Prove equality with the sum of Mathlib's `ArithmeticFunction.moebius` through n.
Keep the theorem statement unchanged. -/
theorem impl_correct : ∀ n, impl n = mertensSpec n := by
  intro n
  rfl

end Submission
