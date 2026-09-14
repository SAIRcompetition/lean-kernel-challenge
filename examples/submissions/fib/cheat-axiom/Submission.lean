import Spec

/-! Adversarial: prove impl_correct from a bogus custom axiom → non-whitelisted axiom, rejected (R4). -/

namespace Submission

axiom bogus : ∀ n, fibSpec n = fibSpec n

def impl : Nat → Nat := fibSpec

theorem impl_correct : ∀ n, impl n = fibSpec n := fun n => bogus n

end Submission
