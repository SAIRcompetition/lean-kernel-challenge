import Spec

/-! Baseline: use the naive spec as the implementation. Correctness is trivial
(`impl` IS `discSpec`); the kernel runs Laplace cofactor expansion on the
Sylvester matrix — factorial in the degree (measured: 6 ms at degree 2, 87 ms at
degree 3, 5.7 s at degree 4, ~x65 per degree) — so the naive path truncates
around degree 5–6 (n ≈ 7–9).
Real reach needs a fraction-free or division-free determinant (Bareiss,
Berkowitz, subresultant PRS) with its equality proof. Beating this is the
game. -/

namespace Submission

def impl : Nat → Int := discSpec

theorem impl_correct : ∀ n, impl n = discSpec n := fun _ => rfl

end Submission
