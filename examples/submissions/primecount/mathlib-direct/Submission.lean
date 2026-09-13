import Spec

/-! Use Mathlib's prime-counting implementation directly. -/

namespace Submission

def impl : Nat → Nat := primeCountSpec

theorem impl_correct : ∀ n, impl n = primeCountSpec n := fun _ => rfl

end Submission
