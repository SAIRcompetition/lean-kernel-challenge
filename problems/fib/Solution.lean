import Spec
import Submission

/-!
# Lean Competition problem `fib` — SOLUTION BRIDGE (trusted, locked)

Fixed bridge from the contestant's `Submission` namespace to the challenge
statement. Contestants must not edit this file.
-/

@[reducible] noncomputable def answer : Nat := Submission.answer

theorem answer_correct : fibSpec fibInstance = answer := Submission.answer_correct
