import Spec
import Mathlib

/-! Adversarial: import Mathlib → workspace has no Mathlib dep, build fails (R4). -/

namespace Submission

def impl : Nat → Nat := fibSpec

theorem impl_correct : ∀ n, impl n = fibSpec n := fun _ => rfl

end Submission
