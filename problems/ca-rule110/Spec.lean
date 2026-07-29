/-!
# Lean Competition problem `ca-rule110` — SPEC (trusted, locked)

Rule 110 cellular automaton on a cyclic row of `ruleWidth` cells, evolved for
`n` steps (`caSpecN : Nat → Nat`); the result is the final row encoded as a
natural number (least-significant bit = cell 0). Deliberately list-based and
index-heavy; submissions are expected to evolve the automaton efficiently
(e.g. on a bit-packed representation) and prove the result against this spec
for every `n`.
-/

def ruleWidth : Nat := 32

def rule110 (l c r : Bool) : Bool :=
  match l, c, r with
  | true, true, true => false
  | true, false, false => false
  | false, false, false => false
  | _, _, _ => true

def stepRow (row : List Bool) : List Bool :=
  (List.range row.length).map fun i =>
    rule110 (row.getD ((i + row.length - 1) % row.length) false)
            (row.getD i false)
            (row.getD ((i + 1) % row.length) false)

def iterRow : Nat → List Bool → List Bool
  | 0, row => row
  | t + 1, row => iterRow t (stepRow row)

def encodeRow (row : List Bool) : Nat :=
  row.foldr (fun b acc => 2 * acc + (if b then 1 else 0)) 0

/-- The instance: a fixed pseudo-random initial row (LCG seed 20260709). -/
def initRow : List Bool := [true, true, true, true, true, false, false, false, true, false, true, false, true, false, false, true, false, true, true, false, false, true, true, true, true, true, false, true, false, false, false, true]

/-- Parametric spec: automaton state after n steps, parametric in n. -/
def caSpecN (n : Nat) : Nat := encodeRow (iterRow n initRow)
