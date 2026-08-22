import Spec
import Submission

/-! SOLUTION BRIDGE (trusted, locked). Do not edit. -/

@[reducible] def impl : Nat → Nat := Submission.impl

theorem impl_correct : ∀ n, impl n = convSpec n := Submission.impl_correct
