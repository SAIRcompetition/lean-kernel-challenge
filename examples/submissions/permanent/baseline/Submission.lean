import Spec
import Submission.Helpers

/-! Baseline: naive parametric spec as impl. -/

namespace Submission

def impl : Nat → Nat := permanentSpecN

theorem impl_correct : ∀ n, impl n = permanentSpecN n := fun _ => rfl

end Submission
