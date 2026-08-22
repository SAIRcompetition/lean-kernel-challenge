import Spec
import Submission

/-! SOLUTION BRIDGE (trusted, locked). Do not edit. -/

@[reducible] def impl : Nat → Int := Submission.impl

theorem impl_correct : ∀ n, impl n = discSpec n := Submission.impl_correct
