/-!
# Lean Kernel Challenge problem `fib` — SPEC (trusted, locked)

Textbook Fibonacci. The source reads like an exponential call tree, but Lean's
equation compiler elaborates it via course-of-values recursion (`Nat.brecOn`), so
the kernel reduces it in time linear in n — cheap for small n, but linear cost
still grows without bound. A logarithmic algorithm (fast doubling) beats it by a
wide margin at large n. Submissions provide a fast function `impl : Nat -> Nat`
plus a proof it agrees with this spec on every input.
-/

def fibSpec : Nat → Nat
  | 0 => 0
  | 1 => 1
  | n + 2 => fibSpec n + fibSpec (n + 1)
