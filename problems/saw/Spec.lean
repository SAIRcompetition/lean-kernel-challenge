/-!
# Lean Competition problem `saw` — SPEC (trusted, locked)

This task counts self-avoiding walks on a deterministic obstacle instance of
the square lattice. The packed input has two public coordinates:

* `n >>> 32` is the walk length;
* `n &&& 0xffffffff` is the instance seed.

The seed selects a sparse obstacle field. The non-negative x-axis is always
open, guaranteeing at least one valid walk at every length. The trusted
computation counts extensions depth first and does not materialise all walks.
-/

def sawDirs : List (Int × Int) := [(1, 0), (-1, 0), (0, 1), (0, -1)]

/-- Decode the public scaling coordinate from a packed judge input. -/
def sawLength (n : Nat) : Nat := n >>> 32

/-- Decode the independent 32-bit instance seed from a packed judge input. -/
def sawSeed (n : Nat) : Nat := n &&& 0xffffffff

def sawMemPos (q : Int × Int) (visited : List (Int × Int)) : Bool :=
  visited.any (fun r => r.1 == q.1 && r.2 == q.2)

/-- An injective encoding of signed coordinates as natural numbers. -/
def sawEncodeInt (x : Int) : Nat :=
  if x < 0 then 2 * x.natAbs - 1 else 2 * x.natAbs

/-- A small 32-bit avalanche mixer used only to generate deterministic instances. -/
def sawMix32 (x : Nat) : Nat :=
  let x := ((x ^^^ (x >>> 16)) * 0x7feb352d) &&& 0xffffffff
  let x := ((x ^^^ (x >>> 15)) * 0x846ca68b) &&& 0xffffffff
  (x ^^^ (x >>> 16)) &&& 0xffffffff

/--
The seeded sparse obstacle field. Roughly one point in eleven is blocked away
from the forced open corridor on the non-negative x-axis.
-/
def sawBlocked (seed : Nat) (p : Int × Int) : Bool :=
  if p.2 = 0 ∧ 0 ≤ p.1 then
    false
  else
    sawMix32
      (seed ^^^
        (sawEncodeInt p.1 * 0x9e3779b9) ^^^
        (sawEncodeInt p.2 * 0x85ebca6b) ^^^
        0xc2b2ae35) % 11 == 0

/-- Count valid extensions without allocating the complete set of walks. -/
def sawCount : Nat → Nat → (Int × Int) → List (Int × Int) → Nat
  | 0, _, _, _ => 1
  | steps + 1, seed, p, visited =>
      sawDirs.foldl (fun total d =>
        let q := (p.1 + d.1, p.2 + d.2)
        if sawMemPos q visited || sawBlocked seed q then
          total
        else
          total + sawCount steps seed q (q :: visited)) 0

/-- Number of obstacle-avoiding self-avoiding walks for the packed instance. -/
def sawSpec (n : Nat) : Nat :=
  let origin : Int × Int := (0, 0)
  sawCount (sawLength n) (sawSeed n) origin [origin]
