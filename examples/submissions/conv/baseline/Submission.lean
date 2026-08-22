import Spec

/-! Baseline: use the naive spec as the implementation. Correctness is trivial
(`impl` IS `convSpec`); the kernel runs the naive double sum with `getD` index
walks — measured ~n^2.5 (25 ms at n=8, 2.6 s at n=64, 17.7 s at n=128), naive
truncation around n ≈ 600–800. The ladder: honest list algorithms (Karatsuba),
then the packing lemma + one native big-number multiplication (Kronecker
substitution). Beating this is the game. -/

namespace Submission

def impl : Nat → Nat := convSpec

theorem impl_correct : ∀ n, impl n = convSpec n := fun _ => rfl

end Submission
