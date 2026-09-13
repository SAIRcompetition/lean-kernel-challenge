import Spec

/-!
# Lean Kernel Challenge problem `fib` — CHALLENGE (trusted, locked)

Provide a function `impl : Nat -> Nat` and a proof it equals Mathlib's `Nat.fib` on every
input. The judge evaluates `impl` on inputs of its choosing. Fill both holes in
`Submission.lean`.
-/

def impl : Nat → Nat := sorry

theorem impl_correct : ∀ n, impl n = Nat.fib n := sorry
