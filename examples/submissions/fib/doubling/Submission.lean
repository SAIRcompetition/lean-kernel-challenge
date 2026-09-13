import Spec

/-!
Fast-doubling submission with correctness proved against Mathlib's `Nat.fib`.
The number of halving stages is logarithmic; arithmetic uses growing natural
numbers, so this is not a logarithmic bit-time claim.

Identities (addition-only except one guarded truncated subtraction):
  F(2m)   = F(m) * (2*F(m+1) - F(m))
  F(2m+1) = F(m+1)^2 + F(m)^2

`fd` recurses on binary halving using structural fuel for direct kernel
reduction. Other recursion schemes are also allowed when kernel-reducible.
-/

namespace Submission

/-- Fast-doubling Fibonacci pair: for `n ≤ fuel`, `fd fuel n = (F n, F (n+1))`. -/
def fd : Nat → Nat → Nat × Nat
  | 0, _ => (0, 1)
  | _ + 1, 0 => (0, 1)
  | fuel + 1, n + 1 =>
    match fd fuel ((n + 1) / 2) with
    | (a, b) =>
      if (n + 1) % 2 = 0 then
        (a * (2 * b - a), b * b + a * a)
      else
        (b * b + a * a, a * (2 * b - a) + (b * b + a * a))

/-- Odd doubling: `F(2m+1) = F(m+1)² + F(m)²`. -/
theorem fib_odd (m : Nat) :
    Nat.fib (2 * m + 1) = Nat.fib (m + 1) * Nat.fib (m + 1) + Nat.fib m * Nat.fib m := by
  simpa only [pow_two] using Nat.fib_two_mul_add_one m

/-- Even doubling: `F(2m) = F(m) * (2*F(m+1) − F(m))`. -/
theorem fib_even (m : Nat) :
    Nat.fib (2 * m) = Nat.fib m * (2 * Nat.fib (m + 1) - Nat.fib m) :=
  Nat.fib_two_mul m

/-- Correctness of fast doubling, by structural induction on the fuel. -/
theorem fd_spec : (fuel n : Nat) → n ≤ fuel → fd fuel n = (Nat.fib n, Nat.fib (n + 1))
  | 0, 0, _ => rfl
  | _ + 1, 0, _ => rfl
  | fuel + 1, n + 1, h => by
    have hdiv : (n + 1) / 2 ≤ fuel := by omega
    have ih := fd_spec fuel ((n + 1) / 2) hdiv
    simp only [fd, ih]
    by_cases hpar : (n + 1) % 2 = 0
    · rw [if_pos hpar]
      show _ = (Nat.fib (n + 1), Nat.fib (n + 2))
      have e1 : 2 * ((n + 1) / 2) = n + 1 := by omega
      have e2 : 2 * ((n + 1) / 2) + 1 = n + 2 := by omega
      have he := fib_even ((n + 1) / 2)
      have ho := fib_odd ((n + 1) / 2)
      rw [e1] at he
      rw [e2] at ho
      rw [he, ho]
    · rw [if_neg hpar]
      show _ = (Nat.fib (n + 1), Nat.fib (n + 2))
      have e1 : 2 * ((n + 1) / 2) + 1 = n + 1 := by omega
      have e2 : 2 * ((n + 1) / 2) + 2 = n + 2 := by omega
      have he := fib_even ((n + 1) / 2)
      have ho := fib_odd ((n + 1) / 2)
      have ho1 := ho
      rw [e1] at ho1
      have hsum : Nat.fib (2 * ((n + 1) / 2) + 2)
                = Nat.fib (2 * ((n + 1) / 2)) + Nat.fib (2 * ((n + 1) / 2) + 1) :=
        Nat.fib_add_two
      rw [e2] at hsum
      rw [hsum, he, ho, ho1]

def impl (n : Nat) : Nat := (fd n n).1

theorem impl_correct : ∀ n, impl n = Nat.fib n := by
  intro n
  show (fd n n).1 = Nat.fib n
  rw [fd_spec n n (Nat.le_refl _)]

end Submission
