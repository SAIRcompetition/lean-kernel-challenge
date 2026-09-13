"""Reference answers agree with independent fixtures and trusted Lean definitions."""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "judge"))
import judge
import reference_answers as reference
from test_packed_instance_specs import CASES, POLYDISC_VECTORS, lean_int_values


class ReferenceAnswerTests(unittest.TestCase):
    def test_packed_and_polydisc_match_independent_frozen_answers(self):
        for problem, case_set in CASES.items():
            for scale, seed, expected in case_set["vectors"]:
                with self.subTest(problem=problem, scale=scale, seed=seed):
                    self.assertEqual(reference.compute_answer(problem, (scale << 32) | seed), expected)
        for n, expected in POLYDISC_VECTORS:
            with self.subTest(problem="polydisc", n=n):
                self.assertEqual(str(reference.compute_answer("polydisc", n)), expected)

    @unittest.skipUnless(shutil.which("lake"), "Lean toolchain is not installed")
    def test_direct_references_match_trusted_lean_specs(self):
        for problem, spec in [("fib", "fibSpec"), ("partition", "partitionSpec"),
                              ("mertens", "mertensSpec"), ("primecount", "primeCountSpec")]:
            inputs = [0, 1, 2, 5, 10, 20]
            with self.subTest(problem=problem):
                expected = lean_int_values(problem, spec, inputs)
                self.assertEqual([str(reference.compute_answer(problem, n)) for n in inputs], expected)

    @unittest.skipUnless(shutil.which("lake"), "Lean toolchain is not installed")
    def test_polydisc_largest_width_matches_trusted_lean(self):
        n = 2 ** 57
        self.assertEqual([str(reference.compute_answer("polydisc", n))],
                         lean_int_values("polydisc", "discSpec", [n]))

    def test_exact_discriminant_and_pivoting(self):
        self.assertEqual(reference.determinant([[0, 2], [3, 4]]), -6)
        self.assertEqual(reference.determinant([[1, 2], [2, 4]]), 0)
        self.assertEqual(reference.polynomial_discriminant([1, 0, -1]), 4)
        self.assertEqual(reference.polynomial_discriminant([1, 0, 0, -2]), -108)

    def test_bundle_rejects_mismatch_omission_duplicate_and_invalid_literals(self):
        spec = "a" * 64
        original = reference.prepare("fib", [3, 4], spec)
        self.assertEqual(reference.validate(original, "fib", [3, 4], spec), {3: "2", 4: "3"})
        mutations = [
            lambda b: b.update(problem="partition"),
            lambda b: b.update(spec_sha256="b" * 64),
            lambda b: b["answers"].pop(),
            lambda b: b["answers"][1].update(n=3),
            lambda b: b["answers"].reverse(),
            lambda b: b["answers"][0].update(type="Int"),
        ] + [lambda b, value=value: b["answers"][0].update(value=value)
             for value in [2, True, "02", "-0", "+2", "2\n", "-2"]]
        for mutate in mutations:
            bundle = json.loads(json.dumps(original))
            mutate(bundle)
            with self.assertRaises(ValueError):
                reference.validate(bundle, "fib", [3, 4], spec)
        changed = json.loads(json.dumps(original))
        changed["answers"][0]["value"] = "3"
        self.assertNotEqual(reference.seal(original)["sha256"], reference.seal(changed)["sha256"])

    def test_private_stdin_is_consumed_before_subprocess_environment_is_built(self):
        bundle = reference.prepare("fib", [3], "a" * 64)
        stream = io.TextIOWrapper(io.BytesIO(b"test-only-seed\n" + reference.canonical_bytes(bundle)))
        with mock.patch.object(sys, "stdin", stream), \
             mock.patch.object(judge, "PERF_SEED", ""), \
             mock.patch.object(judge, "_PERF_SEED_SOURCE", [None]), \
             mock.patch.object(judge, "_REFERENCE_ANSWERS", None), \
             mock.patch.dict(os.environ, {"PERF_SEED_STDIN": "1", "REFERENCE_ANSWERS_STDIN": "1"}):
            judge._consume_perf_seed_stdin()
            self.assertEqual(judge._REFERENCE_ANSWERS, bundle)
            self.assertEqual(stream.buffer.read(), b"")
            self.assertNotIn("REFERENCE_ANSWERS_STDIN", judge.tool_env())
            self.assertNotIn("PERF_SEED", judge.tool_env())

    def test_cli_prepares_full_private_plan_without_any_submission(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "answers.json"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/prepare_reference.py"), "--problem", "fib",
                 "--official", "--output", str(output)], input="test-only-seed\n",
                env={k: v for k, v in os.environ.items() if k not in
                     ("PERF_SEED", "PERF_COUNT", "REFERENCE_ANSWERS_STDIN")},
                text=True, capture_output=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            bundle = json.loads(output.read_text())
            self.assertEqual(len(bundle["answers"]), 6)
            self.assertEqual(
                bundle["spec_sha256"],
                judge.specification_fingerprint(ROOT / "problems/fib"),
            )
            self.assertNotIn("test-only-seed", proc.stdout + proc.stderr)

    @unittest.skipUnless(shutil.which("lean"), "Lean toolchain is not installed")
    def test_direct_kernel_check_accepts_wf_implementation_and_rejects_wrong_answer(self):
        # The default Meta oracle cannot unfold wfId. Standard answers avoid it,
        # but the generated theorem must still compute and check the actual impl.
        # This checks the generated-theorem boundary, not the published fib task.
        # Keep a standalone core fixture so importing Mathlib in that task does
        # not require dependency setup for this generic regression.
        source = """
def fibSpec : Nat → Nat
  | 0 => 0
  | 1 => 1
  | n + 2 => fibSpec n + fibSpec (n + 1)

namespace Submission
def wfId (n : Nat) : Nat :=
  if h : n = 0 then 0 else wfId (n - 1) + 1
termination_by n
decreasing_by omega
theorem wfId_eq (n : Nat) : wfId n = n := by
  induction n with
  | zero => simp [wfId]
  | succ n ih =>
    rw [wfId]
    simp only [Nat.succ_ne_zero, ↓reduceDIte, Nat.add_sub_cancel, ih]
def impl (n : Nat) : Nat := fibSpec (wfId n)
theorem impl_correct (n : Nat) : impl n = fibSpec n := by
  simp [impl, wfId_eq]
end Submission
"""
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            env = dict(os.environ, LEAN_PATH=td,
                       ELAN_TOOLCHAIN=(ROOT / "lean-toolchain").read_text().strip())
            (work / "Submission.lean").write_text(source)
            built = subprocess.run(["lean", "-o", "Submission.olean", "Submission.lean"],
                                   cwd=td, env=env, text=True, capture_output=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            for value, succeeds in [(reference.compute_answer("fib", 3), True), (3, False)]:
                theorem, _ = judge._perf_theorem_source(3, str(value), "reference-regression")
                (work / "Check.lean").write_text(theorem)
                checked = subprocess.run(["lean", "Check.lean"], cwd=td, env=env,
                                         text=True, capture_output=True, timeout=30)
                self.assertEqual(checked.returncode == 0, succeeds, checked.stdout + checked.stderr)


if __name__ == "__main__":
    unittest.main()
