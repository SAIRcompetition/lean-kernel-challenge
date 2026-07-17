import Spec
import Submission.Helpers

/-!
Baseline: no algorithmic cleverness — let the official kernel grind the naive
spec directly. `decide +kernel` routes the evaluation to the C++ kernel,
bypassing elaborator-side reduction (which burns maxRecDepth per step).
-/

namespace Submission

def answer : Int := -1

theorem answer_correct : mertensSpec mertensInstance = answer := by decide +kernel

end Submission
