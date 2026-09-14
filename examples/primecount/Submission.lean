import Spec
namespace Submission

def isPrime (p : Nat) : Bool :=
  decide (2 ≤ p) && (List.range p).all (fun d => decide (d < 2) || p % d != 0)

theorem isPrime_iff (p : Nat) : isPrime p = true ↔ Nat.Prime p := by
  rw [Nat.prime_def_lt']
  simp only [isPrime, Bool.and_eq_true, decide_eq_true_eq, List.all_eq_true,
    List.mem_range, Bool.or_eq_true, bne_iff_ne]
  constructor
  · rintro ⟨hp, h⟩
    refine ⟨hp, ?_⟩
    intro m hm hmp hd
    rcases h m hmp with hsmall | hmod
    · omega
    · exact hmod (Nat.mod_eq_zero_of_dvd hd)
  · rintro ⟨hp, h⟩
    refine ⟨hp, ?_⟩
    intro m hmp
    by_cases hm : m < 2
    · exact Or.inl hm
    · exact Or.inr (fun hmod => h m (by omega) hmp (Nat.dvd_of_mod_eq_zero hmod))

theorem isPrime_eq_mathlib (p : Nat) : isPrime p = decide (Nat.Prime p) := by
  apply Bool.eq_iff_iff.mpr
  simpa using isPrime_iff p

def checkFrom (p : Nat) : Nat → Nat → Bool
  | 0, _ => false
  | fuel + 1, d => if d * d ≤ p then (p % d == 0 || checkFrom p fuel (d + 1)) else false
def isPrimeFast (p : Nat) : Bool := decide (2 ≤ p) && !checkFrom p p 2
def impl (n : Nat) : Nat := ((List.range (n + 1)).filter isPrimeFast).length

theorem checkFrom_iff (p : Nat) : ∀ fuel d,
    (checkFrom p fuel d = true) ↔ ∃ e, d ≤ e ∧ e < d + fuel ∧ e * e ≤ p ∧ p % e = 0 := by
  intro fuel
  induction fuel with
  | zero => intro d; simp only [checkFrom]; constructor
            · intro h; exact absurd h (by decide)
            · rintro ⟨e, h1, h2, _, _⟩; omega
  | succ f ih =>
    intro d; rw [checkFrom]
    by_cases hd : d * d ≤ p
    · simp only [hd, if_true, Bool.or_eq_true, beq_iff_eq, ih (d + 1)]
      constructor
      · rintro (hmod | ⟨e, he1, he2, he3, he4⟩)
        · exact ⟨d, Nat.le_refl d, by omega, hd, hmod⟩
        · exact ⟨e, by omega, by omega, he3, he4⟩
      · rintro ⟨e, he1, he2, he3, he4⟩
        by_cases hde : d = e
        · subst hde; exact Or.inl he4
        · exact Or.inr ⟨e, by omega, by omega, he3, he4⟩
    · simp only [hd, if_false]; constructor
      · intro h; exact absurd h (by decide)
      · rintro ⟨e, he1, _, he3, _⟩; have := Nat.mul_le_mul he1 he1; omega

theorem small_factor (p : Nat) :
    (∃ d, 2 ≤ d ∧ d < p ∧ p % d = 0) ↔ (∃ e, 2 ≤ e ∧ e * e ≤ p ∧ p % e = 0) := by
  constructor
  · rintro ⟨d, hd2, hdp, hdmod⟩
    by_cases hsq : d * d ≤ p
    · exact ⟨d, hd2, hsq, hdmod⟩
    · have hdvd : d ∣ p := Nat.dvd_of_mod_eq_zero hdmod
      have hpe : d * (p / d) = p := Nat.mul_div_cancel' hdvd
      have hge2 : 2 ≤ p / d := by
        have h1 : d * 1 < d * (p / d) := by rw [hpe]; omega
        have := Nat.lt_of_mul_lt_mul_left h1; omega
      have hlt : p / d < d := by
        have h2 : d * (p / d) < d * d := by rw [hpe]; omega
        exact Nat.lt_of_mul_lt_mul_left h2
      refine ⟨p / d, hge2, ?_, ?_⟩
      · calc (p / d) * (p / d) ≤ d * (p / d) := Nat.mul_le_mul (Nat.le_of_lt hlt) (Nat.le_refl _)
          _ = p := hpe
      · have key : p % (p / d) = (d * (p / d)) % (p / d) := by rw [hpe]
        rw [key, Nat.mul_mod_left]
  · rintro ⟨e, he2, hesq, hemod⟩
    have h2e : 2 * e ≤ e * e := Nat.mul_le_mul he2 (Nat.le_refl e)
    exact ⟨e, he2, by omega, hemod⟩

theorem isPrimeFast_eq (p : Nat) : isPrimeFast p = isPrime p := by
  have hcheck : (checkFrom p p 2 = true) ↔ ∃ d, 2 ≤ d ∧ d < p ∧ p % d = 0 := by
    rw [checkFrom_iff, small_factor]
    constructor
    · rintro ⟨e, h1, _, h3, h4⟩; exact ⟨e, h1, h3, h4⟩
    · rintro ⟨e, h1, h3, h4⟩
      have : e ≤ e * e := Nat.le_mul_of_pos_right e (by omega)
      exact ⟨e, h1, by omega, h3, h4⟩
  have hall : ((List.range p).all (fun d => decide (d < 2) || p % d != 0) = true) ↔
              ¬ ∃ d, 2 ≤ d ∧ d < p ∧ p % d = 0 := by
    simp only [List.all_eq_true, List.mem_range, Bool.or_eq_true, decide_eq_true_eq, bne_iff_ne]
    constructor
    · rintro h ⟨d, hd2, hdp, hdmod⟩
      rcases h d hdp with h1 | h2
      · omega
      · exact h2 hdmod
    · intro h d hdp
      by_cases hd2 : d < 2
      · exact Or.inl hd2
      · exact Or.inr (fun hmod => h ⟨d, by omega, hdp, hmod⟩)
  unfold isPrimeFast isPrime
  by_cases hp2 : 2 ≤ p
  · have hd : decide (2 ≤ p) = true := by simp [hp2]
    rw [hd, Bool.true_and, Bool.true_and]
    by_cases hcomp : ∃ d, 2 ≤ d ∧ d < p ∧ p % d = 0
    · have hcf : checkFrom p p 2 = true := hcheck.mpr hcomp
      have haf : (List.range p).all (fun d => decide (d < 2) || p % d != 0) = false := by
        cases h : (List.range p).all (fun d => decide (d < 2) || p % d != 0)
        · rfl
        · exact absurd hcomp (hall.mp h)
      rw [hcf, haf, Bool.not_true]
    · have hcf : checkFrom p p 2 = false := by
        cases h : checkFrom p p 2
        · rfl
        · exact absurd (hcheck.mp h) hcomp
      have haf : (List.range p).all (fun d => decide (d < 2) || p % d != 0) = true := hall.mpr hcomp
      rw [hcf, haf, Bool.not_false]
  · have hd : decide (2 ≤ p) = false := by simp [hp2]
    rw [hd, Bool.false_and, Bool.false_and]

theorem impl_correct : ∀ n, impl n = primeCountSpec n := by
  intro n
  change ((List.range (n + 1)).filter isPrimeFast).length = Nat.primeCounting n
  simp only [Nat.primeCounting, Nat.primeCounting', Nat.count, List.countP_eq_length_filter]
  rw [List.filter_congr (fun p _ => (isPrimeFast_eq p).trans (isPrime_eq_mathlib p))]
end Submission
