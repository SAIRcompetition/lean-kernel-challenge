import Spec
import Submission.Helpers

/-! Adversarial test: native_decide must be rejected by the axiom whitelist. -/

namespace Submission

def answer : Nat := 37338

theorem answer_correct : partitionSpec partitionInstance = answer := by native_decide

end Submission
