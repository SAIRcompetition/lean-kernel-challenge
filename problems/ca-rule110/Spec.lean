/-!
# Lean Competition problem `ca-rule110` — SPEC (trusted, locked)

Rule 110 cellular automaton on a cyclic row of `ruleWidth` cells. Inputs pack
an evolution length in their high bits and an independent 32-bit initial-state
seed in their low bits. The result is the final row encoded as a natural
number (least-significant bit = cell 0). Deliberately list-based and
index-heavy; submissions are expected to evolve the automaton efficiently
(e.g. on a bit-packed representation) and prove the result against this spec
for every packed input.
-/

def ruleWidth : Nat := 256

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

/-- Decode the public scaling coordinate from a packed judge input. -/
def caSteps (n : Nat) : Nat := n >>> 32

/-- Decode the seed-specific 32-bit instance coordinate. -/
def caSeed (n : Nat) : Nat := n &&& 0xffffffff

/-- A small 32-bit mixer for deriving a dense row from `(seed, cell index)`. -/
def caMix32 (x : Nat) : Nat :=
  let x := ((x ^^^ (x >>> 16)) * 0x7feb352d) &&& 0xffffffff
  let x := ((x ^^^ (x >>> 15)) * 0x846ca68b) &&& 0xffffffff
  (x ^^^ (x >>> 16)) &&& 0xffffffff

/-- A deterministic seeded initial row. The first two cells are fixed to
different values, excluding the two spatially uniform configurations. -/
def initRowFor (seed : Nat) : List Bool :=
  (List.range ruleWidth).map fun i =>
    if i = 0 then true
    else if i = 1 then false
    else (caMix32 (seed + (i + 1) * 0x9e3779b9)).testBit 31

/-- Parametric spec: the seed-specific Rule 110 instance encoded by `n`. -/
def caSpecN (n : Nat) : Nat :=
  encodeRow (iterRow (caSteps n) (initRowFor (caSeed n)))
