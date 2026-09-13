/-!
# Lean Competition problem `mertens` — SPEC (trusted, locked)

The Mertens function `M(n) = Σ_{k=1..n} μ(k)`, with the Möbius function μ
specified naively via trial division. Deliberately quadratic; submissions are
expected to compute the value efficiently and prove it against this spec.
-/

/-- Trial-division primality. -/
def isPrime (p : Nat) : Bool :=
  decide (2 ≤ p) && (List.range p).all (fun d => decide (d < 2) || p % d != 0)

/-- Number of distinct prime divisors ω(n). -/
def omegaCount (n : Nat) : Nat :=
  ((List.range (n + 1)).filter (fun p => isPrime p && n % p == 0)).length

/-- Squarefreeness by trial division against all squares. -/
def isSquarefree (n : Nat) : Bool :=
  (List.range (n + 1)).all (fun d => decide (d < 2) || n % (d * d) != 0)

/-- The Möbius function (with the conventional `μ(0) = 0`). -/
def mu (n : Nat) : Int :=
  if n == 0 then 0
  else if isSquarefree n then (if omegaCount n % 2 == 0 then 1 else -1)
  else 0

/-- The Mertens function `M(n)`. -/
def mertensSpec (n : Nat) : Int :=
  ((List.range (n + 1)).map mu).foldl (· + ·) 0

