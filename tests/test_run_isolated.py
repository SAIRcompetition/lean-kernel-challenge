#!/usr/bin/env python3
"""Static/behavioral tests for the mandatory Docker evaluation wrapper.

The tests use a recording Docker stub, so they run on CI hosts without a
Docker daemon while still checking the exact argv passed to `docker run`.
"""

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WRAPPER = ROOT / "scripts" / "run_isolated.sh"

FAKE_DOCKER = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
if args[:2] == ["image", "inspect"]:
    print("sha256:" + "a" * 64)
    raise SystemExit(0)
record = {
    "args": args,
    "PERF_SEED": os.environ.get("PERF_SEED"),
    "OFFICIAL_EVAL": os.environ.get("OFFICIAL_EVAL"),
    "EVALUATION_COHORT": os.environ.get("EVALUATION_COHORT"),
    "EVALUATION_RUN_ID": os.environ.get("EVALUATION_RUN_ID"),
    "EVALUATION_IMAGE": os.environ.get("EVALUATION_IMAGE"),
    "EVALUATION_MEMORY": os.environ.get("EVALUATION_MEMORY"),
    "EVALUATION_CPUS": os.environ.get("EVALUATION_CPUS"),
    "EVALUATION_PIDS_LIMIT": os.environ.get("EVALUATION_PIDS_LIMIT"),
    "EVALUATION_EXECUTOR_ID": os.environ.get("EVALUATION_EXECUTOR_ID"),
    "EVALUATION_EXECUTOR_VERSION": os.environ.get("EVALUATION_EXECUTOR_VERSION"),
    "seed_stdin": sys.stdin.read() if "PERF_SEED_STDIN=1" in args else None,
}
with Path(os.environ["DOCKER_CAPTURE"]).open("a") as out:
    out.write(json.dumps(record) + "\n")

# Model the judge's persistent verdict write on the actual evaluation call.
if "judge/judge.py" in args and os.environ.get("FAKE_WRITE_VERDICT") == "1":
    result_mount = next(
        arg for arg in args
        if arg.startswith("type=bind,src=")
        and arg.endswith(",dst=/work/lean-kernel-challenge/results")
    )
    result_src = result_mount.removeprefix("type=bind,src=").split(",dst=", 1)[0]
    problem = args[args.index("--problem") + 1]
    if "--tag" in args:
        name = args[args.index("--tag") + 1]
    else:
        name = "submission"
    verdict = Path(result_src) / problem / f"{name}.json"
    verdict.parent.mkdir(parents=True, exist_ok=True)
    verdict.write_text(json.dumps({
        "problem": problem,
        "submission": name,
        "run_id": os.environ["EVALUATION_RUN_ID"],
        "status": "accepted",
        "evaluation_mode": "official",
        "evaluation_cohort": {"round": os.environ["EVALUATION_COHORT"]},
    }) + "\n")
"""


class RunIsolatedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.submission = self.base / "entry-dir"
        self.results = self.base / "results"
        self.submission.mkdir()
        self.results.mkdir()
        (self.submission / "Submission.lean").write_text(
            "namespace Submission\nend Submission\n"
        )

        self.capture = self.base / "docker.jsonl"
        self.fake_docker = self.base / "fake-docker"
        self.fake_docker.write_text(FAKE_DOCKER)
        self.fake_docker.chmod(
            self.fake_docker.stat().st_mode | stat.S_IXUSR
        )
        self.env = os.environ.copy()
        self.env.update(
            {
                "DOCKER_BIN": str(self.fake_docker),
                "DOCKER_CAPTURE": str(self.capture),
                "FAKE_WRITE_VERDICT": "1",
            }
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_wrapper(self, *extra, seed=True):
        cmd = [
            str(WRAPPER),
            "--problem",
            "fib",
            "--submission",
            str(self.submission),
            "--results",
            str(self.results),
            "--cohort",
            "round-2026-01",
        ]
        if seed:
            cmd += ["--perf-seed", "hidden seed value"]
        cmd += list(extra)
        return subprocess.run(
            cmd, env=self.env, text=True, capture_output=True, check=False
        )

    def records(self):
        return [
            json.loads(line)
            for line in self.capture.read_text().splitlines()
        ]

    def assert_pair(self, args, option, value):
        pos = args.index(option)
        self.assertEqual(args[pos + 1], value)

    def assert_mandatory_envelope(self, record):
        args = record["args"]
        self.assertEqual(args[:2], ["run", "--rm"])
        self.assert_pair(args, "--network", "none")
        self.assert_pair(args, "--memory", "768m")
        self.assert_pair(args, "--cpus", "1.5")
        self.assert_pair(args, "--pids-limit", "97")
        self.assert_pair(args, "--security-opt", "no-new-privileges:true")
        self.assert_pair(args, "--user", "judge")
        passed_env = [
            args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--env"
        ]
        self.assertNotIn("PERF_SEED", passed_env)
        self.assertIn("OFFICIAL_EVAL", [
            args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--env"
        ])
        self.assertIn("EVALUATION_COHORT", passed_env)
        self.assertIn("TIMING_METRIC=perf_instructions", args)
        self.assertIn("SANDBOX_MODE=container", args)
        self.assertIn("--cap-drop", args)
        self.assert_pair(args, "--cap-drop", "ALL")
        self.assertIn("ISOLATION_ATTESTATION=run_isolated.sh", args)
        for name in (
            "EVALUATION_RUN_ID",
            "EVALUATION_IMAGE",
            "EVALUATION_MEMORY",
            "EVALUATION_CPUS",
            "EVALUATION_PIDS_LIMIT",
            "EVALUATION_EXECUTOR_ID",
            "EVALUATION_EXECUTOR_VERSION",
        ):
            self.assertIn(name, passed_env)
        self.assertNotIn("hidden seed value", args)
        self.assertIsNone(record["PERF_SEED"])
        self.assertEqual(record["OFFICIAL_EVAL"], "1")
        self.assertEqual(record["EVALUATION_COHORT"], "round-2026-01")
        self.assertRegex(record["EVALUATION_RUN_ID"], r"^run-[0-9]+-[0-9]+-[0-9]+$")
        self.assertEqual(record["EVALUATION_MEMORY"], "768m")
        self.assertEqual(record["EVALUATION_CPUS"], "1.5")
        self.assertEqual(record["EVALUATION_PIDS_LIMIT"], "97")
        self.assertRegex(record["EVALUATION_IMAGE"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(record["EVALUATION_EXECUTOR_ID"], r"^local-pmu-[0-9a-f]{16}$")
        self.assertRegex(
            record["EVALUATION_EXECUTOR_VERSION"],
            r"^pmu-contract-sha256:[0-9a-f]{64}$",
        )

        submission_mount = (
            f"type=bind,src={self.submission.resolve()},"
            "dst=/submission,readonly"
        )
        results_mount = (
            f"type=bind,src={self.results.resolve()},"
            "dst=/work/lean-kernel-challenge/results"
        )
        self.assertIn(submission_mount, args)
        self.assertIn(results_mount, args)
        self.assertNotIn(results_mount + ",readonly", args)

    def test_constructs_locked_preflight_and_evaluation_commands(self):
        proc = self.run_wrapper(
            "--tag",
            "official-entry",
            "--reps",
            "3",
            "--image",
            "registry.example/judge:v1",
            "--memory",
            "768m",
            "--cpus",
            "1.5",
            "--pids-limit",
            "97",
            "--perfmon",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

        records = self.records()
        self.assertEqual(len(records), 2)
        for record in records:
            self.assert_mandatory_envelope(record)
            self.assert_pair(record["args"], "--cap-add", "PERFMON")
            self.assertIn("sha256:" + "a" * 64, record["args"])
            self.assertNotIn("registry.example/judge:v1", record["args"])

        preflight = records[0]["args"]
        self.assert_pair(preflight, "--entrypoint", "/usr/bin/test")
        self.assertEqual(preflight[-2:], [
            "-w", "/work/lean-kernel-challenge/results"
        ])

        evaluation = records[1]["args"]
        self.assertNotIn("--entrypoint", evaluation)
        self.assertIn("--interactive", evaluation)
        self.assertIn("PERF_SEED_STDIN=1", evaluation)
        self.assertEqual(records[1]["seed_stdin"], "hidden seed value\n")
        self.assertIsNone(records[0]["seed_stdin"])
        self.assertIn("python3", evaluation)
        self.assertIn("judge/judge.py", evaluation)
        self.assert_pair(evaluation, "--problem", "fib")
        self.assert_pair(evaluation, "--submission", "/submission")
        self.assert_pair(evaluation, "--tag", "official-entry")
        self.assert_pair(evaluation, "--reps", "3")

        verdict = self.results / "fib" / "official-entry.json"
        self.assertTrue(verdict.is_file())
        self.assertIn(str(verdict), proc.stdout)

    def test_perfmon_is_optional_but_isolation_is_not(self):
        proc = self.run_wrapper(
            "--memory", "768m",
            "--cpus", "1.5",
            "--pids-limit", "97",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for record in self.records():
            self.assert_mandatory_envelope(record)
            self.assertNotIn("--cap-add", record["args"])
        evaluation = self.records()[1]["args"]
        self.assert_pair(evaluation, "--tag", "entry-dir")
        self.assertTrue((self.results / "fib" / "entry-dir.json").is_file())

    def test_rejects_missing_seed_before_invoking_docker(self):
        self.env.pop("PERF_SEED", None)
        proc = self.run_wrapper(seed=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("PERF_SEED", proc.stderr)
        self.assertFalse(self.capture.exists())

    def test_rejects_slug_longer_than_judge_limit(self):
        proc = self.run_wrapper("--tag", "a" * 97)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("invalid tag slug", proc.stderr)
        self.assertFalse(self.capture.exists())

    def test_stale_verdict_cannot_mask_a_run_that_wrote_nothing(self):
        old = self.results / "fib" / "entry-dir.json"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text(json.dumps({
            "problem": "fib",
            "submission": "entry-dir",
            "run_id": "old-run",
            "status": "accepted",
        }))
        self.env["FAKE_WRITE_VERDICT"] = "0"

        proc = self.run_wrapper(
            "--memory", "768m", "--cpus", "1.5", "--pids-limit", "97")

        self.assertEqual(proc.returncode, 1)
        self.assertIn("without a matching verdict", proc.stderr)
        self.assertEqual(json.loads(old.read_text())["run_id"], "old-run")

    def test_rejects_relative_mount_sources_before_invoking_docker(self):
        proc = subprocess.run(
            [
                str(WRAPPER),
                "--problem", "fib",
                "--submission", "relative/submission",
                "--results", str(self.results),
                "--perf-seed", "seed",
                "--cohort", "test-round",
            ],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("absolute path", proc.stderr)
        self.assertFalse(self.capture.exists())


if __name__ == "__main__":
    unittest.main()
