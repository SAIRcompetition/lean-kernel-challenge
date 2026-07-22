import Spec
import Submission

/-! SOLUTION BRIDGE (locked). -/

@[reducible] def impl : Nat → Nat := Submission.impl

theorem impl_correct : ∀ n, impl n = partitionSpec n := Submission.impl_correct
