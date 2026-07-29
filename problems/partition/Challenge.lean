import Spec

/-! CHALLENGE (locked). Provide a total `impl : Nat -> Nat` and prove it equals
partitionSpec on every input. -/

def impl : Nat → Nat := sorry

theorem impl_correct : ∀ n, impl n = partitionSpec n := sorry
