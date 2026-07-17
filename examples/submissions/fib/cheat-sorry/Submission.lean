import Spec
import Submission.Helpers

/-! Adversarial test: sorry-based "proof" must be rejected by the axiom audit. -/

namespace Submission

def answer : Nat := 42

theorem answer_correct : fibSpec fibInstance = answer := by sorry

end Submission
