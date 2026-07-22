/-!
# Lean Kernel Challenge problem `fib` — SPEC (trusted, locked)

Textbook Fibonacci, deliberately naive: an exponential call tree, infeasible to
reduce in the kernel beyond small n. Submissions provide a fast function
`impl : Nat -> Nat` plus a proof it agrees with this spec on every input.
-/

def fibSpec : Nat → Nat
  | 0 => 0
  | 1 => 1
  | n + 2 => fibSpec n + fibSpec (n + 1)
