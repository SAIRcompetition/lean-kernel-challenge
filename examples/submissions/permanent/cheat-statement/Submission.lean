import Spec
import Submission.Helpers

/-! Adversarial test: prove a DIFFERENT (trivial) statement under the expected name. -/

namespace Submission

def answer : Nat := 0

theorem answer_correct : permanentSpec [] = answer := rfl

end Submission
