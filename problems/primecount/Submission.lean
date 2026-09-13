import Spec

namespace Submission

/-- TODO 1: Optimize this implementation. Keep it total and kernel-reducible. -/
def impl : Nat → Nat := primeCountSpec

/-- TODO 2: Prove that `impl n` equals `primeCountSpec n` for every natural number n.
Keep the theorem statement unchanged. -/
theorem impl_correct : ∀ n, impl n = primeCountSpec n := fun _ => rfl

end Submission
