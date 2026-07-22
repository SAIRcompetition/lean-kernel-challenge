import Spec
import Submission.Helpers

/-! Baseline: use the naive spec as the implementation. Correctness is trivial
(`impl` IS `fibSpec`); the kernel evaluation of `impl n` runs the exponential
spec, so it is slow. Beating this is the game. -/

namespace Submission

def impl : Nat → Nat := fibSpec

theorem impl_correct : ∀ n, impl n = fibSpec n := fun _ => rfl

end Submission
