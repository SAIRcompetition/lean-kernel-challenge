import Spec

/-! Baseline: the trusted depth-first walk counter. -/

namespace Submission

def impl : Nat → Nat := sawSpec

theorem impl_correct : ∀ n, impl n = sawSpec n := fun _ => rfl

end Submission
