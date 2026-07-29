#!/usr/bin/env python3
"""New-paradigm performance evaluator for the Lean Kernel Challenge.

A submission provides `impl : Nat -> Output` and `impl_correct : forall n, impl n = spec n`.

Correctness gate (two independent checks, both required to pass):
  1. build the locked Solution (which references `impl_correct`), and
  2. audit the axioms `impl_correct` depends on via `#print axioms` — this is what
     actually rejects a `sorry`-backed proof (`sorryAx`) or `native_decide`, since a
     plain `lake build` only *warns* on `sorry`. Whitelist = config.json permitted_axioms.

Performance is then measured by timing the kernel reducing `impl n` at inputs of the
judge's choosing. The reference value `v = impl n` is obtained by a kernel-side `Meta.whnf`
reduction of the submission's own `impl` (NOT compiled `#eval`, whose codegen can be
exponential where the kernel reduction is linear, e.g. the naive fib spec) — so the timing
goal `impl n = v` forces the kernel to fully reduce `impl n`. A per-input mismatch
(`impl n != v`) makes the goal unprovable, which we surface as FAIL, distinct from TIMEOUT.
"""
import subprocess, time, os, json, re, argparse, resource, tempfile, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "judge"))
import judge as _judge      # reuse the authoritative input policy (no separate hardcoded list)


def _raise_stack():
    """Raise the child's stack rlimit before exec so deep kernel/Meta reduction of `impl n`
    doesn't overflow the default ~8 MB stack. Effective on the Linux eval host (infinite hard
    limit → 512 MB); macOS refuses to raise RLIMIT_STACK, so this is an honest no-op there and
    the default stack stands (enough for the moderate dev inputs)."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    except (ValueError, OSError):
        return
    cap = (512 * 1024 * 1024) if hard == resource.RLIM_INFINITY else hard
    for target in (cap, cap - (1 << 20), 256 * 1024 * 1024, 64 * 1024 * 1024):
        if target <= soft:
            return
        try:
            resource.setrlimit(resource.RLIMIT_STACK, (target, hard))
            return
        except (ValueError, OSError):
            continue

def _run(cmd, cwd, timeout):
    t = time.monotonic()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           preexec_fn=_raise_stack)
        return r.returncode, time.monotonic() - t, r.stdout + r.stderr, False
    except subprocess.TimeoutExpired:
        return 1, time.monotonic() - t, "", True


def audit_axioms(w, whitelist, timeout):
    """Return (ok, reason). Rejects sorryAx / non-whitelisted axioms in impl_correct."""
    open(f"{w}/AxCheck.lean", "w").write(
        "import Submission\n#print axioms Submission.impl_correct\n")
    rc, _, log, to = _run(["lake", "env", "lean", "AxCheck.lean"], w, timeout)
    if to:
        return False, "axiom audit timed out"
    if rc != 0:
        return False, "axiom audit failed to elaborate: " + \
            "; ".join(l for l in log.splitlines() if "error" in l.lower())[:200]
    if "does not depend on any axioms" in log:
        return True, "no axioms"
    m = re.search(r"depends on axioms:\s*\[([^\]]*)\]", log, re.S)
    if not m:
        # Unexpected output shape — fail closed.
        return False, "could not parse axiom list: " + log.strip()[:200]
    used = [a.strip() for a in m.group(1).split(",") if a.strip()]
    bad = [a for a in used if a not in whitelist]
    if bad:
        return False, f"non-whitelisted axiom(s): {bad}"
    return True, f"axioms ok: {used}"


# Reference value v = impl n by KERNEL-side reduction (Meta `whnf`), NOT compiled `#eval`:
# codegen can be exponential where the kernel reduction is cheap (naive fib compiles to an
# exponential tree but reduces via `brecOn` in linear kernel time), so #eval would fail to
# evaluate a submission the kernel handles fine. whnf reduces as the timed replay will, for
# Nat and Int results; a wrong v cannot mis-score (the decide+kernel build would then fail).
_VALUE_META = r"""import Submission
import Lean
open Lean Meta
set_option maxRecDepth 4000000
run_meta do
  let e0 ← whnf (mkApp (mkConst ``Submission.impl) (mkNatLit __N__))
  match e0 with
  | .lit (.natVal v) => IO.println s!"VALUE={v}"
  | .app (.const ``Int.ofNat _) a =>
    match (← whnf a) with
    | .lit (.natVal v) => IO.println s!"VALUE={v}"
    | _ => IO.println "NONLIT"
  | .app (.const ``Int.negSucc _) a =>
    match (← whnf a) with
    | .lit (.natVal v) => IO.println s!"VALUE=-{v + 1}"
    | _ => IO.println "NONLIT"
  | _ => IO.println "NONLIT"
"""


def eval_value(w, n, timeout):
    """Reduce `impl n` to a literal via the kernel-side oracle above. Returns (v_str, to);
    v_str is a decimal string (Nat or signed Int), or None on error/timeout."""
    open(f"{w}/EvalVal.lean", "w").write(_VALUE_META.replace("__N__", str(n)))
    rc, _, log, to = _run(["lake", "env", "lean", "EvalVal.lean"], w, timeout)
    if to or rc != 0:
        return None, to
    for line in log.splitlines():
        if line.startswith("VALUE="):
            return line[6:].strip(), False
    return None, False


_SLOW = ("(deterministic) timeout", "maximum number of heartbeats", "maximum recursion depth",
         "maxRecDepth", "stack overflow", "deep recursion")


def evaluate(problem, submission_dir, timeout=120):
    """Lightweight dev reproduction of the judge's perf phase. The authoritative verdict is
    judge/judge.py; this mirrors its semantics: correctness gate → per-input timing, where a
    too-slow input truncates the curve (accepted) and a deterministic fault errors (no score)."""
    sub = os.path.basename(submission_dir)
    cfg = json.load(open(f"{BASE}/problems/{problem}/config.json"))
    whitelist = cfg.get("permitted_axioms", ["propext", "Quot.sound", "Classical.choice"])
    inputs = _judge.perf_inputs(cfg, problem)
    if not inputs:
        return {"problem": problem, "submission": sub, "status": "error",
                "reason": f"no perf policy for '{problem}'"}
    w = tempfile.mkdtemp(prefix=f"pe_{problem.replace('-', '_')}_")   # unique — no concurrent clobber
    try:
        subprocess.run(["cp", "-r", f"{BASE}/problems/{problem}/.", w])
        subprocess.run(["rm", "-rf", f"{w}/.lake"])
        subprocess.run(["cp", f"{submission_dir}/Submission.lean", f"{w}/Submission.lean"])
        if os.path.isdir(f"{submission_dir}/Submission"):
            subprocess.run(["cp", "-r", f"{submission_dir}/Submission", f"{w}/"])

        def verdict(status, **kw):
            return {"problem": problem, "submission": sub, "status": status, **kw}

        rc, _, log, _ = _run(["lake", "build", "Solution"], w, 3600)
        if rc != 0:
            return verdict("rejected", reason="Solution build failed (impl_correct)",
                           log=[l for l in log.splitlines() if "error" in l.lower()][:3])
        ok, reason = audit_axioms(w, whitelist, 300)
        if not ok:
            return verdict("rejected", reason="axiom audit rejected: " + reason)

        lf = f"{w}/lakefile.toml"; s = open(lf).read()
        if 'name = "Perf"' not in s:
            open(lf, "w").write(s.rstrip() + '\n\n[[lean_lib]]\nname = "Perf"\n')

        scaling = []
        for n in inputs:
            v, to = eval_value(w, n, timeout)
            if v is None:
                scaling.append({"n": n, "seconds": None,
                                "result": "value-eval-timeout" if to else "value-eval-error"})
                break
            open(f"{w}/Perf.lean", "w").write(
                f"import Submission\ntheorem perf_check : Submission.impl {n} = {v} := by decide +kernel\n")
            rc, dt, plog, to = _run(["lake", "env", "lean", "Perf.lean"], w, timeout)
            if to or (rc != 0 and any(m in plog for m in _SLOW)):
                scaling.append({"n": n, "seconds": round(dt, 2), "result": "timeout"})   # too slow
                break
            if rc != 0:                       # deterministic failure = wrong value / fault
                return verdict("error", reason=f"perf build failed at n={n} (fault, not too-slow)",
                               scaling=scaling)
            scaling.append({"n": n, "seconds": round(dt, 2), "result": "ok"})
        scored = any(r["result"] == "ok" for r in scaling)     # scored if ANY input completed
        return verdict("accepted", scored=scored, metric="wall_time (dev)", scaling=scaling)
    finally:
        subprocess.run(["rm", "-rf", w])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", required=True)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()
    if not os.path.isfile(f"{BASE}/problems/{a.problem}/config.json"):
        raise SystemExit(f"unknown problem '{a.problem}'")
    r = evaluate(a.problem, a.submission, a.timeout)
    os.makedirs(f"{BASE}/results/{a.problem}", exist_ok=True)
    open(f"{BASE}/results/{a.problem}/{r['submission']}.perf.json", "w").write(json.dumps(r, indent=2))
    tail = "" if r["status"] != "accepted" else f" (scored={r['scored']})"
    print(f"{r['problem']}/{r['submission']}: {r['status']}{tail}")
    for row in r.get("scaling", []):
        secs = "-" if row["seconds"] is None else f"{row['seconds']}s"
        print(f"  n={row['n']:<7} {secs:<8} {row['result'].upper()}")
    if r.get("reason"):
        print("  reason:", r["reason"], r.get("log") or "")


if __name__ == "__main__":
    main()
