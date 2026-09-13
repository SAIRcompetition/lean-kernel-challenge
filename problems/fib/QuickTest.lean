import Submission
import Mathlib.Data.Nat.Fib.Basic

-- Check the required all-input theorem, not just the numeric examples below.
example : ∀ n : Nat, Submission.impl n = Nat.fib n := Submission.impl_correct

def main : IO UInt32 := do
  IO.println "Public quick test only — no submission, official evaluation, or score."
  let mut passed := true
  for n in ([0, 1, 2, 10, 20] : List Nat) do
    let actual := Submission.impl n
    if actual == Nat.fib n then
      IO.println s!"PASS input={n}"
    else
      IO.eprintln s!"FAIL input={n}: got {actual}, expected {Nat.fib n}"
      passed := false
  return if passed then 0 else 1
