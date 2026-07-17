import Spec
import Submission.Helpers

/-!
Adversarial test for rule R2: define `answer` as the spec expression itself,
so `answer_correct` holds by syntactic `rfl` with ZERO kernel computation.
Comparator accepts this (statement and axioms are fine) — only the R2
literal audit can catch it.
-/

namespace Submission

def answer : Nat := permanentSpec matrixInstance

theorem answer_correct : permanentSpec matrixInstance = answer := rfl

end Submission
