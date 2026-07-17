import Spec
import Submission

/-! # Lean Competition problem `ca-rule110` — SOLUTION BRIDGE (trusted, locked) -/

@[reducible] noncomputable def answer : Nat := Submission.answer

theorem answer_correct : caSpec = answer := Submission.answer_correct
