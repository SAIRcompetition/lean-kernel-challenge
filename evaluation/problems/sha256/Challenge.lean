import Spec

/-!
# Lean Kernel Challenge problem `sha256` — CHALLENGE (trusted, locked)

Provide a function `impl : Nat -> Nat` and a proof it equals `sha256Spec` on
every input. The judge evaluates `impl` on inputs of its choosing. Fill both
holes in `Submission.lean`.
-/

def impl : Nat → Nat := sorry

theorem impl_correct : ∀ n, impl n = sha256Spec n := sorry
