import Spec
import Submission.Helpers

/-!
# Lean Competition problem `fib` — SUBMISSION (yours to edit)

Rules:
- R1: only this file and files under `Submission/` may be edited/added.
- R2: `Submission.answer` must elaborate to a raw numeral literal
      (e.g. `def answer : Nat := 12586269025`), not a compound expression.
- R3: `answer_correct` may only depend on the standard axioms
      (`propext`, `Quot.sound`, `Classical.choice`). In particular
      `native_decide` and `sorry` are rejected.

Scoring: wall-free instruction count for the official kernel to re-check your
entire submission (your proofs AND the evaluation they force). Lower is better.
-/

namespace Submission

def answer : Nat := sorry

theorem answer_correct : fibSpec fibInstance = answer := sorry

end Submission
