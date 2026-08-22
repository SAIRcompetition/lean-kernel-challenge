import Spec

/-!
# Lean Kernel Challenge problem `discriminant` — CHALLENGE (trusted, locked)

Provide a function `impl : Nat -> Int` and a proof it equals `discSpec` on
every input. The judge evaluates `impl` on inputs of its choosing. Fill both
holes in `Submission.lean`.
-/

def impl : Nat → Int := sorry

theorem impl_correct : ∀ n, impl n = discSpec n := sorry
