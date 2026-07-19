import Export.Parse
import Lean4Checker.Replay
import Lean

/-!
Lean Competition timing/audit kernel wrapper.

Modes:
  kernel <file>                             — replay all declarations through the official kernel (the timed event)
  kernel --parse-only <file>                — only parse the export
  kernel --check-literal <name> <file>      — audit that constant <name>'s value is a raw Nat literal (rule R2)
  kernel --check-axioms <a,b,c> <file>      — audit that every axiom in the export is whitelisted

Derived from lean-kernel-arena's `official` checker (which mirrors comparator's runKernel).

The `--check-axioms` mode re-runs comparator's axiom whitelist on the *exact*
export that gets timed, as an independent second line of defense: it rejects
`sorryAx` and the per-computation `native_decide` axioms even if they somehow
slipped past comparator or the export diverged from what comparator built.
-/

def runKernel (solution : Export.ExportedEnv) : IO Unit := do
  let mut env ← Lean.mkEmptyEnvironment
  let mut constMap := solution.constMap
  -- Lean's kernel interprets just the addition of `Quot as adding all of these so adding them
  -- multiple times leads to errors.
  constMap := constMap.erase `Quot.mk |>.erase `Quot.lift |>.erase `Quot.ind
  discard <| env.replay' constMap
  IO.println s!"Accepted {constMap.size} declarations."

/-- Recognize the standard elaborations of numeral literals:
`.lit`, `OfNat.ofNat _ (lit) _`, `Int.ofNat/negSucc` and `Neg.neg` thereof. -/
partial def isRawNumeral (e : Lean.Expr) : Bool :=
  match e with
  | .lit (.natVal _) => true
  | .app (.app (.app (.const ``OfNat.ofNat _) _) inner) _ => isRawNumeral inner
  | .app (.const ``Int.ofNat _) inner => isRawNumeral inner
  | .app (.const ``Int.negSucc _) inner => isRawNumeral inner
  | .app (.app (.app (.const ``Neg.neg _) _) _) inner => isRawNumeral inner
  | _ => false

def checkLiteral (solution : Export.ExportedEnv) (name : Lean.Name) : IO Unit := do
  let some ci := solution.constMap.get? name
    | throw <| .userError s!"constant '{name}' not found in export"
  let some value := ci.value?
    | throw <| .userError s!"constant '{name}' has no value"
  if isRawNumeral value then
    IO.println s!"OK: {name} is a raw numeral literal."
  else
    throw <| .userError s!"rule R2 violation: the body of '{name}' must be a raw numeral literal, found a compound expression"

/-- Audit that every axiom declared in the export is on the whitelist.
Mirrors comparator's `checkAxioms`, but runs on the exact timed export. -/
def checkAxioms (solution : Export.ExportedEnv) (whitelist : List Lean.Name) : IO Unit := do
  let allowed : Std.HashSet Lean.Name := whitelist.foldl (·.insert ·) {}
  let mut offenders : Array Lean.Name := #[]
  for (name, ci) in solution.constMap do
    match ci with
    | .axiomInfo _ => if !allowed.contains name then offenders := offenders.push name
    | _ => pure ()
  if offenders.isEmpty then
    IO.println s!"OK: all axioms whitelisted ({allowed.size} allowed)."
  else
    throw <| .userError s!"axiom whitelist violation: export declares non-whitelisted axiom(s) {offenders.toList}"

def parseFile (inputPath : String) : IO Export.ExportedEnv := do
  let handle ← IO.FS.Handle.mk inputPath .read
  Export.parseStream (.ofHandle handle)

def main (args : List String) : IO Unit := do
  match args with
  | ["--parse-only", inputPath] =>
    discard <| parseFile inputPath
    IO.println "Parse successful."
  | ["--check-literal", name, inputPath] =>
    let env ← parseFile inputPath
    checkLiteral env name.toName
  | ["--check-axioms", whitelist, inputPath] =>
    let env ← parseFile inputPath
    let names := (whitelist.splitOn ",").filterMap (fun s =>
      let s := s.trimAscii.toString
      if s.isEmpty then none else some s.toName)
    checkAxioms env names
  | [inputPath] =>
    let env ← parseFile inputPath
    runKernel env
  | _ => throw <| .userError "Usage: kernel [--parse-only | --check-literal <name> | --check-axioms <a,b,c>] <file>"
