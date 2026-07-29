/-!
# Lean Competition problem `saw` — SPEC (trusted, locked)

The number of self-avoiding walks of length `n` on the square lattice ℤ²,
starting at the origin (`sawSpec : Nat → Nat`). Specified by brute-force
extension of all walks. Deliberately exhaustive; submissions are expected to
count faster (symmetry reduction, better data structures) and prove the count
against this spec for every `n`.
-/

def dirs : List (Int × Int) := [(1, 0), (-1, 0), (0, 1), (0, -1)]

def memPos (q : Int × Int) (w : List (Int × Int)) : Bool :=
  w.any (fun r => r.1 == q.1 && r.2 == q.2)

def extendWalk (w : List (Int × Int)) : List (List (Int × Int)) :=
  match w with
  | [] => []
  | p :: _ =>
    dirs.filterMap (fun d =>
      let q := (p.1 + d.1, p.2 + d.2)
      if memPos q w then none else some (q :: w))

def walks : Nat → List (List (Int × Int))
  | 0 => [[((0 : Int), (0 : Int))]]
  | n + 1 => (walks n).flatMap extendWalk

def sawSpec (n : Nat) : Nat := (walks n).length

