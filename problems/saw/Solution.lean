import Spec
import Submission

/-! # Lean Competition problem `saw` — SOLUTION BRIDGE (trusted, locked) -/

@[reducible] noncomputable def answer : Nat := Submission.answer

theorem answer_correct : sawSpec sawInstance = answer := Submission.answer_correct
