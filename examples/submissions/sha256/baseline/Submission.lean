import Spec

/-! Baseline: use the naive spec as the implementation. Correctness is trivial
(`impl` IS `sha256Spec`); the kernel evaluation of `impl n` runs one full
naive compression per chain step — every 32-bit word op is a separate
reduction. Beating this is the game. -/

namespace Submission

def impl : Nat → Nat := sha256Spec

theorem impl_correct : ∀ n, impl n = sha256Spec n := fun _ => rfl

end Submission
