import Spec
import Submission.Helpers

/-! Baseline: naive spec as impl. -/

namespace Submission

def impl : Nat → Nat := sawSpec

theorem impl_correct : ∀ n, impl n = sawSpec n := fun _ => rfl

end Submission
