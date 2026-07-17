import Spec
import Submission

/-! # Lean Competition problem `partition` — SOLUTION BRIDGE (trusted, locked) -/

@[reducible] noncomputable def answer : Nat := Submission.answer

theorem answer_correct : partitionSpec partitionInstance = answer := Submission.answer_correct
