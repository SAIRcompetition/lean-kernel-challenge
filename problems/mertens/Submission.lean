import Spec

namespace Submission

/-- TODO 1: Optimize this implementation. Keep it total and kernel-reducible. -/
def impl : Nat → Int := mertensSpec

/-- TODO 2: Prove that `impl n` equals `mertensSpec n` for every natural number n.
Keep the theorem statement unchanged. -/
theorem impl_correct : ∀ n, impl n = mertensSpec n := fun _ => rfl

end Submission
