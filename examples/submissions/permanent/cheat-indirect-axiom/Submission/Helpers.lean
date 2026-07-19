import Spec

/-!
The proof of `answer_correct` depends on `helper_lemma`, which depends on
`sneaky` (a local `axiom`). If the audit only inspected the theorem's direct
references it might miss `sneaky`; walking the export closure must catch it.
-/

namespace Submission

axiom sneaky : permanentSpec matrixInstance = 187

theorem helper_lemma : permanentSpec matrixInstance = 187 := sneaky

end Submission
