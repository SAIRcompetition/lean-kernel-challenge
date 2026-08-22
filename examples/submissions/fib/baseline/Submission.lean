import Spec

/-! Baseline: use the naive spec as the implementation. Correctness is trivial
(`impl` IS `fibSpec`); the kernel reduces it via `brecOn` course-of-values
recursion in near-linear time (~5.5 s at n = 100000) — slow, but NOT the
exponential blowup the source suggests; the big win is fast doubling
(O(log n) big-number multiplications), not a linear rewrite. Beating this
baseline is the game. -/

namespace Submission

def impl : Nat → Nat := fibSpec

theorem impl_correct : ∀ n, impl n = fibSpec n := fun _ => rfl

end Submission
