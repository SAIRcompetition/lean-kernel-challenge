#!/usr/bin/env python3
"""New-paradigm performance evaluator for the Lean Kernel Challenge.

A submission provides `impl : Nat -> Output` and `impl_correct : forall n, impl n = spec n`.
Correctness is checked by building Solution (which references impl_correct); performance is
measured by timing the kernel reducing `impl n` at inputs of the judge's choosing.

The timing target `(Submission.impl n).succ != 0` is a trivially-true proposition whose
`decide +kernel` proof forces the kernel to reduce `impl n` to a literal — so we time the
reduction WITHOUT needing to know the answer value (which dodges the need to compute it).
It is built as a lakefile lean_lib so `import Submission` resolves the same way Solution does.
"""
import subprocess, time, os, json, sys, argparse

def _fib(n):
    a,b=0,1
    for _ in range(n): a,b=b,a+b
    return a
REFERENCE = {"fib": _fib}

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Per-problem eval inputs (increasing n). Naive baselines slow down / blow up along these.
INPUTS = {
    "fib":        [30, 35, 40, 45],
    "partition":  [10, 20, 30, 40],
    "mertens":    [50, 100, 200, 400],
    "primecount": [100, 300, 600, 1000],
    "saw":        [5, 7, 9, 11],
    "permanent":  [3, 4, 5, 6],
    "ca-rule110": [100, 1000, 5000, 20000],
}

def build(cwd, target, timeout):
    t = time.monotonic()
    try:
        r = subprocess.run(["lake","build",target], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, time.monotonic()-t, r.stdout+r.stderr
    except subprocess.TimeoutExpired:
        return "timeout", time.monotonic()-t, ""

def evaluate(problem, submission_dir, timeout=120):
    inputs = INPUTS[problem]
    w = f"/tmp/pe_{problem.replace('-','_')}"
    subprocess.run(["rm","-rf",w]); subprocess.run(["cp","-r",f"{BASE}/problems/{problem}",w])
    subprocess.run(["rm","-rf",f"{w}/.lake"])
    subprocess.run(["cp",f"{submission_dir}/Submission.lean",f"{w}/Submission.lean"])
    if os.path.isdir(f"{submission_dir}/Submission"):
        subprocess.run(["cp","-r",f"{submission_dir}/Submission",f"{w}/"])
    # correctness gate: build Solution (references impl_correct : forall n, impl n = spec n)
    rc, _, log = build(w, "Solution", 3600)
    if rc != 0:
        return {"problem":problem,"submission":os.path.basename(submission_dir),
                "status":"rejected","reason":"Solution build failed (impl_correct)",
                "log":[l for l in log.splitlines() if 'error' in l.lower()][:3]}
    # register a Perf lean_lib once
    lf = f"{w}/lakefile.toml"
    s = open(lf).read()
    if 'name = "Perf"' not in s:
        open(lf,"w").write(s.rstrip()+'\n\n[[lean_lib]]\nname = "Perf"\n')
    # per-input timing: kernel reduces impl n via a trivially-true decide +kernel goal
    scaling=[]
    for n in inputs:
        v = REFERENCE[problem](n)
        open(f"{w}/Perf.lean","w").write(
            f"import Submission\ntheorem perf_check : Submission.impl {n} = {v} := by decide +kernel\n")
        import time as _t
        t0=_t.monotonic()
        try:
            r=subprocess.run(["lake","env","lean","Perf.lean"],cwd=w,capture_output=True,text=True,timeout=timeout)
            dt=_t.monotonic()-t0; rc=r.returncode; to=False
        except subprocess.TimeoutExpired:
            dt=_t.monotonic()-t0; rc=1; to=True
        scaling.append({"n":n,"seconds":round(dt,2),"ok":(rc==0),"timeout":to})
        if rc=="timeout":
            break
    return {"problem":problem,"submission":os.path.basename(submission_dir),
            "status":"accepted","metric":"wall_time (dev)","scaling":scaling}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--problem",required=True)
    ap.add_argument("--submission",required=True)
    ap.add_argument("--timeout",type=int,default=120)
    a=ap.parse_args()
    r=evaluate(a.problem, a.submission, a.timeout)
    os.makedirs(f"{BASE}/results/{a.problem}",exist_ok=True)
    open(f"{BASE}/results/{a.problem}/{r['submission']}.perf.json","w").write(json.dumps(r,indent=2))
    # human summary
    print(f"{r['problem']}/{r['submission']}: {r['status']}")
    for row in r.get("scaling",[]):
        mark = "TIMEOUT" if row["timeout"] else ("ok" if row["ok"] else "FAIL")
        print(f"  n={row['n']:<7} {row['seconds']}s {mark}")
    if r.get("reason"): print("  reason:", r["reason"], r.get("log"))

if __name__=="__main__":
    main()
