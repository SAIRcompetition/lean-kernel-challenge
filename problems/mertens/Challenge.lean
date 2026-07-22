import Spec

/-! CHALLENGE (trusted, locked). Provide `impl : Nat -> Int` and prove it equals
`mertensSpec` on every input. -/

def impl : Nat → Int := sorry

theorem impl_correct : ∀ n, impl n = mertensSpec n := sorry
