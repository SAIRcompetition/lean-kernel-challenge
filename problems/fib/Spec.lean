import Mathlib.Data.Nat.Fib.Basic

/-!
# Lean Kernel Challenge problem `fib` — SPEC (trusted, locked)

The correctness target is Mathlib's official `Nat.fib`, imported from the
pinned Mathlib v4.33.1 release. There is no challenge-specific Fibonacci
algorithm in the trusted specification.

`Nat.fib` satisfies `F(0) = 0`, `F(1) = 1`, and
`F(n + 2) = F(n) + F(n + 1)`. Implementations may use any permitted algorithm
with a proof that it equals `Nat.fib` for every natural-number input.
-/

/-- Compatibility name for existing submissions; exactly Mathlib's `Nat.fib`. -/
abbrev fibSpec : Nat → Nat := Nat.fib
