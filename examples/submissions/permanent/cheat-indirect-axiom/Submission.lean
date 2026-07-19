import Spec
import Submission.Helpers

/-!
Adversarial test (R3, indirect dependency): the illegal axiom is not used directly
in `answer_correct` but reached through a helper definition. Verifies that the
axiom audit walks the full lean4export dependency closure, not just the theorem's
immediate references.
-/

namespace Submission

def answer : Nat := 187

theorem answer_correct : permanentSpec matrixInstance = answer :=
  helper_lemma

end Submission
