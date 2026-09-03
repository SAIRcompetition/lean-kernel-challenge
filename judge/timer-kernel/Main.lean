import Export.Parse
import Lean.Replay
import Lean

/-!
Lean Competition timing/audit kernel wrapper.

Modes:
  kernel <file>                             — parse, then time replaying the complete closure
  kernel --target <name> <file>             — prepare the dependency environment, then time
                                               replaying only the named theorem declaration
  kernel --parse-only <file>                — only parse the export
  kernel --check-axioms <a,b,c> <file>      — audit that every axiom in the export is whitelisted

A leading `--count-instructions` (timing modes only) makes the timer open its own hardware
instruction counter (Linux perf_event_open) around the measured replay and report the count
in the measurement record; the judge passes it only for metric=perf_instructions. Without it
the timer never touches the PMU, so wall-time development runs work on hosts and build
sandboxes that have no PMU access, and the record carries `"instructions": null`.

Every timed replay additionally reports `peak_rss_kb`: the peak resident set of the replay
window alone (Linux RSS high-water mark, reset via /proc/self/clear_refs just before the
window opens). This needs procfs, not the PMU, so it is unconditional on Linux; off Linux
the record carries `"peak_rss_kb": null`.

Derived from lean-kernel-arena's `official` checker (which mirrors comparator's runKernel).

The `--check-axioms` mode re-runs comparator's axiom whitelist on the *exact*
export that gets timed, as an independent second line of defense: it rejects
`sorryAx` and the per-computation `native_decide` axioms even if they somehow
slipped past comparator or the export diverged from what comparator built.
-/

namespace TimerKernel

@[extern "lean_kernel_timer_perf_enable"]
opaque perfEnable : IO Unit

@[extern "lean_kernel_timer_perf_disable"]
opaque perfDisable : IO Unit

@[extern "lean_kernel_timer_perf_instructions"]
opaque perfInstructions : IO String

@[extern "lean_kernel_timer_memory_window_open"]
opaque memoryWindowOpen : IO Unit

@[extern "lean_kernel_timer_memory_window_peak_kb"]
opaque memoryWindowPeakKb : IO String

def normalizedConstMap (solution : Export.ExportedEnv) :
    Std.HashMap Lean.Name Lean.ConstantInfo :=
  -- Lean's kernel interprets just the addition of `Quot as adding all of these so adding them
  -- multiple times leads to errors.
  solution.constMap.erase `Quot.mk |>.erase `Quot.lift |>.erase `Quot.ind

def emitMeasurement (boundary : String) (target : Option Lean.Name) (wallNs : Nat)
    (instructions : Option Nat) (peakRssKb : Option Nat) : IO Unit := do
  let positiveWallNs := max 1 wallNs
  let payload := Lean.Json.mkObj [
    ("measurement_contract", .str "kernel-replay-v2"),
    ("boundary", .str boundary),
    ("target", target.map (fun name => Lean.Json.str name.toString) |>.getD .null),
    ("wall_ns", .num (positiveWallNs : Lean.JsonNumber)),
    ("instructions", instructions.map (fun n => Lean.Json.num (n : Lean.JsonNumber)) |>.getD .null),
    ("peak_rss_kb", peakRssKb.map (fun kb => Lean.Json.num (kb : Lean.JsonNumber)) |>.getD .null),
    ("phase", .str "complete")
  ]
  IO.println s!"KERNEL_TIMING={payload.compress}"

def measureReplay (countInstructions : Bool) (boundary : String) (target : Option Lean.Name)
    (replay : IO α) (validate : α → IO Unit := fun _ => pure ()) : IO α := do
  -- Reset the RSS high-water mark before arming the counter: the reset's own kernel work
  -- is never counted, and VmHWM afterwards reports this replay window's peak alone. This
  -- needs procfs, not the PMU, so it is unconditional (a no-op stub off Linux).
  memoryWindowOpen
  if countInstructions then perfEnable
  let started ← IO.monoNanosNow
  let (result, stopped) ←
    try
      let result ← replay
      let stopped ← IO.monoNanosNow
      pure (result, stopped)
    finally
      -- A kernel exception must not leave the timer's PMU event enabled.
      if countInstructions then perfDisable
  -- Read the counter the timer just disabled, before any post-replay work adds to it.
  let instructions ← if countInstructions then pure (some (← perfInstructions).toNat!) else pure none
  -- VmHWM only rises until the next window reset, so reading it here cannot lose the
  -- in-window peak. The non-Linux stub reports 0, published as null.
  let peakKb := (← memoryWindowPeakKb).toNat!
  let peakRssKb := if peakKb == 0 then none else some peakKb
  -- Validate the replay result outside the measured interval, but before publishing a
  -- successful measurement record.
  validate result
  emitMeasurement boundary target (stopped - started) instructions peakRssKb
  return result

def runKernel (countInstructions : Bool) (solution : Export.ExportedEnv) : IO Unit := do
  let env ← Lean.mkEmptyEnvironment
  let constMap := normalizedConstMap solution
  discard <| measureReplay countInstructions "full-closure-replay-v1" none (env.replay constMap)

def runTarget (countInstructions : Bool) (solution : Export.ExportedEnv) (targetText : String) :
    IO Unit := do
  if targetText.isEmpty then
    throw <| .userError "target declaration name must not be empty"
  let target := targetText.toName
  unless target.toString == targetText do
    throw <| .userError s!"target declaration name is not canonical: {targetText}"
  let constMap := normalizedConstMap solution
  let some targetInfo := constMap[target]?
    | throw <| .userError s!"target theorem is absent from export: {target}"
  if targetInfo.isUnsafe || targetInfo.isPartial then
    throw <| .userError s!"target theorem is unsafe or partial: {target}"
  match targetInfo with
  | .thmInfo _ => pure ()
  | _ => throw <| .userError s!"target declaration is not a theorem: {target}"
  unless solution.constOrder.back? == some target do
    throw <| .userError s!"target theorem is not the final exported declaration: {target}"
  for (name, _) in constMap do
    if name != target && target.isPrefixOf name then
      throw <| .userError s!"target theorem has an extracted proof helper: {name}"

  -- Replay every dependency through the official kernel before opening the counter. Since
  -- lean4export emits a theorem's transitive closure, removing the root leaves precisely the
  -- environment in which that one declaration can be checked.
  let preEnv ← (← Lean.mkEmptyEnvironment).replay (constMap.erase target)
  if (preEnv.toKernelEnv.find? target).isSome then
    throw <| .userError s!"target theorem unexpectedly exists in the prepared environment: {target}"
  let targetMap : Std.HashMap Lean.Name Lean.ConstantInfo :=
    ({} : Std.HashMap Lean.Name Lean.ConstantInfo).insert target targetInfo
  let _ ← measureReplay
    countInstructions
    "target-declaration-replay-v1"
    (some target)
    (preEnv.replay targetMap)
    (fun env => do
      unless (env.toKernelEnv.find? target).isSome do
        throw <| .userError s!"target theorem was not installed by kernel replay: {target}")

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

end TimerKernel

def main (args : List String) : IO Unit := do
  -- `--count-instructions` is only meaningful for the two timing modes; the judge passes it
  -- exclusively under metric=perf_instructions.
  let (countInstructions, args) :=
    match args with
    | "--count-instructions" :: rest => (true, rest)
    | _ => (false, args)
  match args with
  | ["--parse-only", inputPath] =>
    discard <| TimerKernel.parseFile inputPath
    IO.println "Parse successful."
  | ["--check-axioms", whitelist, inputPath] =>
    let env ← TimerKernel.parseFile inputPath
    let names := (whitelist.splitOn ",").filterMap (fun s =>
      let s := s.trimAscii.toString
      if s.isEmpty then none else some s.toName)
    TimerKernel.checkAxioms env names
  | ["--target", target, inputPath] =>
    let env ← TimerKernel.parseFile inputPath
    TimerKernel.runTarget countInstructions env target
  | [inputPath] =>
    let env ← TimerKernel.parseFile inputPath
    TimerKernel.runKernel countInstructions env
  | _ => throw (.userError
      ("Usage: kernel [--count-instructions] [--target <name> | --parse-only | " ++
       "--check-axioms <a,b,c>] <file>"))
