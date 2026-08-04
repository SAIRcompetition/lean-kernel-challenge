import Spec

/-! Baseline: naive spec as implementation. -/

namespace Submission

def impl : Nat → Int := mertensSpec

theorem impl_correct : ∀ n, impl n = mertensSpec n := fun _ => rfl

end Submission
