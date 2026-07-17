import Spec
import Submission

/-! # Lean Competition problem `permanent` — SOLUTION BRIDGE (trusted, locked) -/

@[reducible] noncomputable def answer : Nat := Submission.answer

theorem answer_correct : permanentSpec matrixInstance = answer := Submission.answer_correct
