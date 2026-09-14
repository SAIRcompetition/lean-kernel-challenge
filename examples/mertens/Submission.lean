import Spec

/-! Compute Möbius values using Mathlib's prime-factor lists. -/

namespace Submission

def moebiusByFactors (n : Nat) : Int :=
  if n = 0 then 0
  else if n.primeFactorsList.Nodup then (-1 : Int) ^ n.primeFactorsList.length else 0

theorem moebiusByFactors_eq (n : Nat) : moebiusByFactors n = ArithmeticFunction.moebius n := by
  by_cases hn : n = 0
  · subst n
    simp [moebiusByFactors]
  · simp only [moebiusByFactors, if_neg hn, ArithmeticFunction.moebius, ArithmeticFunction.coe_mk,
      ← Nat.squarefree_iff_nodup_primeFactorsList hn, ArithmeticFunction.cardFactors_apply]

def impl (n : Nat) : Int := ∑ k ∈ Finset.range (n + 1), moebiusByFactors k

theorem impl_correct : ∀ n, impl n = mertensSpec n := by
  intro n
  simp only [impl, mertensSpec, moebiusByFactors_eq]

end Submission
