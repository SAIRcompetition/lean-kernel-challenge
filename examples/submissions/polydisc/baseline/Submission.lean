import Spec

/-! Baseline: use the trusted normal subresultant PRS directly. Abnormal degree
drops and failed exact divisions fall back to the reduced monic Sylvester
matrix with fraction-free Bareiss elimination. Correctness is definitional;
competitors can improve the representation or evaluation path. -/

namespace Submission

def impl : Nat → Int := discSpec

theorem impl_correct : ∀ n, impl n = discSpec n := fun _ => rfl

end Submission
