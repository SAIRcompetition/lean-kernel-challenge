import Spec
import Submission.Helpers

/-! Baseline: naive parametric spec as impl. -/

namespace Submission

def impl : Nat → Nat := caSpecN

theorem impl_correct : ∀ n, impl n = caSpecN n := fun _ => rfl

end Submission
