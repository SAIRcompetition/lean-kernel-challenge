import Spec
import Submission.Helpers

/-!
Baseline: no algorithmic cleverness — let the official kernel grind the naive
spec directly. `decide +kernel` routes the evaluation to the C++ kernel,
bypassing elaborator-side reduction (which burns maxRecDepth per step).
-/

namespace Submission

def answer : Nat := 527562713

theorem answer_correct : caSpec = answer := by decide +kernel

end Submission
