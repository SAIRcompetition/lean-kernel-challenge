import Spec
import Mathlib   -- violates R5; workspace lakefile has no Mathlib dep, so this must fail to build

namespace Submission
def answer : Nat := 187
theorem answer_correct : permanentSpec matrixInstance = answer := by decide +kernel
end Submission
