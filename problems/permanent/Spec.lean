/-!
# Lean Competition problem `permanent` — SPEC (trusted, locked)

The input packs two public instance coordinates into one natural number:

* `n >>> 32` is the dimension of the square matrix;
* `n &&& 0xffffffff` is the instance seed.

For dimensions at least three, the seed selects a deterministic 0/1 matrix
with exactly three distinct ones in every row: the diagonal and two seeded
off-diagonal columns. This fixes the branching factor while retaining the full
32-bit instance family. The diagonal guarantees at least one perfect matching.
The trusted computation uses a depth-first traversal of column choices rather
than materialising the list of all permutations.
-/

/-- Decode the public scaling coordinate from a packed judge input. -/
def permanentDimension (n : Nat) : Nat := n >>> 32

/-- Decode the independent 32-bit instance seed from a packed judge input. -/
def permanentSeed (n : Nat) : Nat := n &&& 0xffffffff

/-- A small 32-bit avalanche mixer used only to generate deterministic instances. -/
def permanentMix32 (x : Nat) : Nat :=
  let x := ((x ^^^ (x >>> 16)) * 0x7feb352d) &&& 0xffffffff
  let x := ((x ^^^ (x >>> 15)) * 0x846ca68b) &&& 0xffffffff
  (x ^^^ (x >>> 16)) &&& 0xffffffff

/-- Map `k` past one excluded column. -/
def permanentSkipOne (excluded k : Nat) : Nat :=
  if k < excluded then k else k + 1

/-- Map `k` past two distinct excluded columns. -/
def permanentSkipTwo (a b k : Nat) : Nat :=
  let lo := min a b
  let hi := max a b
  let x := if k < lo then k else k + 1
  if x < hi then x else x + 1

/-- The first seeded off-diagonal column of a row. Requires `3 ≤ dimension`. -/
def permanentColumnOne (dimension seed i : Nat) : Nat :=
  permanentSkipOne i
    (permanentMix32 (seed ^^^ (i * 0x9e3779b9) ^^^ 0x85ebca6b) % (dimension - 1))

/-- The second seeded off-diagonal column, distinct from the diagonal and first. -/
def permanentColumnTwo (dimension seed i : Nat) : Nat :=
  let first := permanentColumnOne dimension seed i
  permanentSkipTwo i first
    (permanentMix32 (seed ^^^ (i * 0x9e3779b9) ^^^ 0xc2b2ae35) % (dimension - 2))

/-- A seeded matrix entry. Dimensions below three use the full square matrix. -/
def permanentEntry (dimension seed i j : Nat) : Nat :=
  if dimension < 3 then
    1
  else if i = j || j = permanentColumnOne dimension seed i ||
      j = permanentColumnTwo dimension seed i then
    1
  else
    0

def genPermanentRow (dimension seed i : Nat) : List Nat :=
  (List.range dimension).map (permanentEntry dimension seed i)

/-- The deterministic matrix selected by a dimension and seed. -/
def genPermanentMatrix (dimension seed : Nat) : List (List Nat) :=
  (List.range dimension).map (genPermanentRow dimension seed)

/--
Sum the products associated with all injective column choices. The bit mask
records columns already chosen by earlier rows. For a square matrix this is
the usual permanent (the Leibniz formula without signs), but the traversal does
not allocate the factorial-size list of permutations.
-/
def permanentRows (width : Nat) : List (List Nat) → Nat → Nat
  | [], _ => 1
  | row :: rows, used =>
      (List.range width).foldl (fun total j =>
        let entry := row.getD j 0
        if entry = 0 || used.testBit j then
          total
        else
          total + entry * permanentRows width rows (used ||| (1 <<< j))) 0

/-- The mathematical permanent of a square matrix. -/
def permanentSpec (m : List (List Nat)) : Nat :=
  permanentRows m.length m 0

/-- Parametric spec: the permanent of the matrix selected by the packed input. -/
def permanentSpecN (n : Nat) : Nat :=
  permanentSpec (genPermanentMatrix (permanentDimension n) (permanentSeed n))
