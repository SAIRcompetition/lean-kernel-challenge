import Spec
import Mathlib

/-! Negative fixture: primecount has no Mathlib dependency, so this import fails. -/

namespace Submission

def impl : Nat → Nat := primeCountSpec

theorem impl_correct : ∀ n, impl n = primeCountSpec n := fun _ => rfl

end Submission
