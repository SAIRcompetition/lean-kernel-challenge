import Spec
import Submission

/-! # Lean Competition problem `mertens` — SOLUTION BRIDGE (trusted, locked) -/

@[reducible] noncomputable def answer : Int := Submission.answer

theorem answer_correct : mertensSpec mertensInstance = answer := Submission.answer_correct
