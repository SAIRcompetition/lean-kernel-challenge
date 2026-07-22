import Spec
import Submission.Helpers

/-! Baseline: naive spec as impl. -/

namespace Submission

def impl : Nat → Nat := partitionSpec

theorem impl_correct : ∀ n, impl n = partitionSpec n := fun _ => rfl

end Submission
