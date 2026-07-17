/-!
# Lean Competition problem `fib` — SPEC (trusted, locked)

Textbook Fibonacci, deliberately naive. Evaluating `fibSpec fibInstance` by
kernel reduction directly is astronomically infeasible (exponential call tree);
submissions are expected to provide a fast computation together with a
correctness proof against this spec.

This file is part of the trusted problem statement. Contestants must not edit it.
-/

def fibSpec : Nat → Nat
  | 0 => 0
  | 1 => 1
  | n + 2 => fibSpec n + fibSpec (n + 1)

/-- The instance parameter for this problem. -/
def fibInstance : Nat := 100000
