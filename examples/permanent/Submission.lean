import Spec

/-! Baseline: the trusted depth-first computation on the seeded fixed-row-degree matrix. -/

namespace Submission

def impl : Nat → Nat := permanentSpecN

theorem impl_correct : ∀ n, impl n = permanentSpecN n := fun _ => rfl

end Submission
