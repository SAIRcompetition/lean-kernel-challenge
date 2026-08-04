import Spec

/-! Baseline: naive spec as impl. -/

namespace Submission

def impl : Nat → Nat := primeCountSpec

theorem impl_correct : ∀ n, impl n = primeCountSpec n := fun _ => rfl

end Submission
