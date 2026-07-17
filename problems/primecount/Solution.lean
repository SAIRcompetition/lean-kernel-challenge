import Spec
import Submission

/-! # Lean Competition problem `primecount` — SOLUTION BRIDGE (trusted, locked) -/

@[reducible] noncomputable def answer : Nat := Submission.answer

theorem answer_correct : primeCountSpec primeCountInstance = answer := Submission.answer_correct
