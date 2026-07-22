import Spec
import Submission.Helpers

/-!
Optimized submission: fast doubling — O(log n) big-number multiplications
instead of the loop's n additions.

Identities (addition-only except one guarded truncated subtraction):
  F(2m)   = F(m) * (2*F(m+1) - F(m))
  F(2m+1) = F(m+1)^2 + F(m)^2

`fd` recurses on binary halving, powered by structural fuel: `n → n/2` is not
structural, and well-founded recursion would not reduce inside the kernel.
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

/-- The Fibonacci addition formula. -/
theorem addF : (n m : Nat) →
    fibSpec (m + n + 1) = fibSpec (m + 1) * fibSpec (n + 1) + fibSpec m * fibSpec n
  | 0, m => by
    show fibSpec (m + 1) = fibSpec (m + 1) * 1 + fibSpec m * 0
    omega
  | 1, m => by
    show fibSpec (m + 2) = fibSpec (m + 1) * 1 + fibSpec m * 1
    have h : fibSpec (m + 2) = fibSpec m + fibSpec (m + 1) := rfl
    omega
  | n + 2, m => by
    have ih0 : fibSpec (m + n + 1)
             = fibSpec (m + 1) * fibSpec (n + 1) + fibSpec m * fibSpec n := addF n m
    have ih1 : fibSpec (m + n + 2)
             = fibSpec (m + 1) * fibSpec (n + 2) + fibSpec m * fibSpec (n + 1) := addF (n + 1) m
    have hL : fibSpec (m + (n + 2) + 1) = fibSpec (m + n + 1) + fibSpec (m + n + 2) := rfl
    have hR : fibSpec (n + 2 + 1) = fibSpec (n + 1) + fibSpec (n + 2) := rfl
    have hF2 : fibSpec (n + 2) = fibSpec n + fibSpec (n + 1) := rfl
    rw [hL, ih0, ih1]
    simp only [hR, hF2, Nat.mul_add]
    omega

/-- Odd doubling: `F(2m+1) = F(m+1)² + F(m)²`. -/
theorem fib_odd (m : Nat) :
    fibSpec (2 * m + 1) = fibSpec (m + 1) * fibSpec (m + 1) + fibSpec m * fibSpec m := by
  have h := addF m m
  have e : m + m + 1 = 2 * m + 1 := by omega
  rw [e] at h
  exact h

/-- Even doubling: `F(2m) = F(m) * (2*F(m+1) − F(m))`. -/
theorem fib_even (m : Nat) :
    fibSpec (2 * m) = fibSpec m * (2 * fibSpec (m + 1) - fibSpec m) := by
  match m with
  | 0 => decide
  | k + 1 =>
    have h := addF (k + 1) k
    have e : k + (k + 1) + 1 = 2 * (k + 1) := by omega
    rw [e] at h
    have hrec : fibSpec (k + 2) = fibSpec k + fibSpec (k + 1) := rfl
    have hsub : 2 * fibSpec (k + 1 + 1) - fibSpec (k + 1)
              = 2 * fibSpec k + fibSpec (k + 1) := by
      show 2 * fibSpec (k + 2) - fibSpec (k + 1) = 2 * fibSpec k + fibSpec (k + 1)
      omega
    rw [h, hsub]
    have hstep : fibSpec (k + 1 + 1) = fibSpec k + fibSpec (k + 1) := rfl
    rw [hstep, Nat.mul_add, Nat.mul_add]
    have hc : fibSpec k * fibSpec (k + 1) = fibSpec (k + 1) * fibSpec k :=
      Nat.mul_comm _ _
    have h2 : fibSpec (k + 1) * (2 * fibSpec k) = 2 * (fibSpec (k + 1) * fibSpec k) := by
      rw [Nat.mul_left_comm]
    omega

/-- Correctness of fast doubling, by structural induction on the fuel. -/
theorem fd_spec : (fuel n : Nat) → n ≤ fuel → fd fuel n = (fibSpec n, fibSpec (n + 1))
  | 0, 0, _ => rfl
  | _ + 1, 0, _ => rfl
  | fuel + 1, n + 1, h => by
    have hdiv : (n + 1) / 2 ≤ fuel := by omega
    have ih := fd_spec fuel ((n + 1) / 2) hdiv
    simp only [fd, ih]
    by_cases hpar : (n + 1) % 2 = 0
    · rw [if_pos hpar]
      show _ = (fibSpec (n + 1), fibSpec (n + 2))
      have e1 : 2 * ((n + 1) / 2) = n + 1 := by omega
      have e2 : 2 * ((n + 1) / 2) + 1 = n + 2 := by omega
      have he := fib_even ((n + 1) / 2)
      have ho := fib_odd ((n + 1) / 2)
      rw [e1] at he
      rw [e2] at ho
      rw [he, ho]
    · rw [if_neg hpar]
      show _ = (fibSpec (n + 1), fibSpec (n + 2))
      have e1 : 2 * ((n + 1) / 2) + 1 = n + 1 := by omega
      have e2 : 2 * ((n + 1) / 2) + 2 = n + 2 := by omega
      have he := fib_even ((n + 1) / 2)
      have ho := fib_odd ((n + 1) / 2)
      have ho1 := ho
      rw [e1] at ho1
      have hsum : fibSpec (2 * ((n + 1) / 2) + 2)
                = fibSpec (2 * ((n + 1) / 2)) + fibSpec (2 * ((n + 1) / 2) + 1) := rfl
      rw [e2] at hsum
      rw [hsum, he, ho, ho1]

def impl (n : Nat) : Nat := (fd n n).1

theorem impl_correct : ∀ n, impl n = fibSpec n := by
  intro n
  show (fd n n).1 = fibSpec n
  rw [fd_spec n n (Nat.le_refl _)]

end Submission
