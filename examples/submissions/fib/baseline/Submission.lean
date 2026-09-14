import Spec

/-! Baseline: use Mathlib's standard Fibonacci function directly.
Correctness is reflexivity. Kernel-replay measurements, rather than compiled
execution, determine this implementation's performance in the challenge. -/

namespace Submission

def impl : Nat → Nat := Nat.fib

theorem impl_correct : ∀ n, impl n = Nat.fib n := fun _ => rfl

end Submission
