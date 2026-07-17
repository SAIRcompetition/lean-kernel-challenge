import Spec
import Submission.Helpers

/-! Positive test: multi-file submission with the proof in Submission/Helpers.lean. -/

namespace Submission

def answer : Nat := 187

theorem answer_correct : permanentSpec matrixInstance = answer := helper

end Submission
