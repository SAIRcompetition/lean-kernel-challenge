import Spec

/-! Adversarial: impl_correct left as sorry → sorryAx, must be rejected by the axiom audit (R4). -/

namespace Submission

def impl : Nat → Nat := fibSpec

theorem impl_correct : ∀ n, impl n = fibSpec n := sorry

end Submission
