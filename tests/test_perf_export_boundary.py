"""Real-tool regression tests for the perf-export boundary check.

Run inside the isolated judge image with ``LKC_REAL_TOOLS=1``; skipped otherwise.
The perf export crosses from the untrusted build/export step into the trusted timer,
so the judge binds its ``impl``/``Eq``/``Eq.refl`` to the comparator-verified solution
export (``comparator --verify-performance``) before timing.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "judge"))
import judge


# The boundary tests need a tiny reducible function, not the published fib
# dependency graph. Keep the fixture self-contained rather than copying its
# potentially multi-gigabyte .lake directory into each test workspace.
CORE_FIB_SPEC = """def fibSpec : Nat → Nat
  | 0 => 0
  | 1 => 1
  | n + 2 => fibSpec n + fibSpec (n + 1)
"""
CORE_FIB_BASELINE = """import Spec
namespace Submission
def impl : Nat → Nat := fibSpec
theorem impl_correct : ∀ n, impl n = fibSpec n := fun _ => rfl
end Submission
"""
CORE_FIB_CHALLENGE = """import Spec
def impl : Nat → Nat := sorry
theorem impl_correct : ∀ n, impl n = fibSpec n := sorry
"""
CORE_FIB_SOLUTION = """import Spec
import Submission
@[reducible] def impl : Nat → Nat := Submission.impl
theorem impl_correct : ∀ n, impl n = fibSpec n := Submission.impl_correct
"""
CORE_FIB_LAKEFILE = """name = "perfBoundaryFixture"
defaultTargets = ["Challenge", "Solution"]
[leanOptions]
autoImplicit = false
[[lean_lib]]
name = "Spec"
[[lean_lib]]
name = "Challenge"
[[lean_lib]]
name = "Solution"
[[lean_lib]]
name = "Submission"
"""


@unittest.skipUnless(os.environ.get("LKC_REAL_TOOLS") == "1", "requires isolated judge image")
class PerfExportBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "workspace"
        self.work.mkdir()
        self.baseline = CORE_FIB_BASELINE
        for name, source in {
            "Spec.lean": CORE_FIB_SPEC,
            "Challenge.lean": CORE_FIB_CHALLENGE,
            "Solution.lean": CORE_FIB_SOLUTION,
            "Submission.lean": self.baseline,
            "lakefile.toml": CORE_FIB_LAKEFILE,
        }.items():
            (self.work / name).write_text(source)
        shutil.copy2(ROOT / "lean-toolchain", self.work / "lean-toolchain")
        shutil.copy2(ROOT / "problems/fib/config.json", self.work / "config.json")
        self.env = judge.tool_env()
        self.lean, prefix, core = judge._resolve_lean_runtime(self.work, self.env)
        self.lib = self.work / ".lake/build/lib/lean"
        self.verified_env = judge._verified_runtime_env(self.env, self.lib, prefix, core)
        self.export = self.root / "solution.ndjson"

    def command(self, args, env=None, expected=0):
        rc, out = judge.run(list(map(str, args)), self.work, env or self.env, 120)
        self.assertEqual(rc, expected, out)
        return out

    def build(self, source):
        (self.work / "Submission.lean").write_text(source)
        self.command(["lake", "build", "Submission"])

    def compare_full(self):
        env = dict(self.env, COMPARATOR_SOLUTION_EXPORT=str(self.export))
        self.command(["lake", "env", judge.COMPARATOR, "config.json"], env)

    def verify_perf(self, path, target, n, value, valid=True):
        rc, out = judge.run([str(judge.COMPARATOR), "--verify-performance",
                            str(self.work / "config.json"), str(self.export), str(path),
                            target, str(n), str(value)], self.work, self.env, 120)
        self.assertEqual(rc == 0, valid, out)

    def test_genuine_perf_export_is_accepted_and_bound_to_n_and_v(self):
        self.compare_full()
        perf = self.root / "perf.ndjson"
        kind, detail, target = judge._perf_export(self.work, self.verified_env, 10, "55",
                                                 perf, 120, self.lib, self.lean)
        self.assertEqual(kind, "ok", detail)
        self.verify_perf(perf, target, 10, "55")
        # The check is bound to the requested (n, v): a different n or a wrong v is refused.
        self.verify_perf(perf, target, 11, "55", valid=False)
        self.verify_perf(perf, target, 10, "54", valid=False)

    def test_performance_result_type_alias_is_preserved(self):
        (self.work / "Submission.lean").write_text(self.baseline.replace(
            "namespace Submission", "namespace Submission\nabbrev Output := Nat").replace(
            "def impl : Nat → Nat", "def impl : Nat → Output"))
        self.compare_full()
        perf = self.root / "alias.ndjson"
        kind, detail, target = judge._perf_export(self.work, self.verified_env, 10, "55",
                                                 perf, 120, self.lib, self.lean)
        self.assertEqual(kind, "ok", detail)
        self.verify_perf(perf, target, 10, "55")

    def test_forged_performance_implementation_is_rejected(self):
        self.compare_full()
        # A different, trivially-fast impl with a fake proof: the kernel would still accept
        # `impl 10 = 55 := Eq.refl 55` because `(fun _ => 55) 10` reduces to 55, so only the
        # binding to the VERIFIED impl can catch it.
        self.build(self.baseline.replace(":= fibSpec", ":= fun _ => 55").replace(
            "∀ n, impl n = fibSpec n := fun _ => rfl", "True := True.intro"))
        perf = self.root / "forged.ndjson"
        kind, detail, target = judge._perf_export(self.work, self.verified_env, 10, "55",
                                                 perf, 120, self.lib, self.lean)
        self.assertEqual(kind, "ok", detail)
        self.verify_perf(perf, target, 10, "55", valid=False)


if __name__ == "__main__":
    unittest.main()
