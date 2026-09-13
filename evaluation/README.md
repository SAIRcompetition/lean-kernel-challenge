# Optional local evaluation

You do not need the evaluator to develop or submit a solution. Follow the
[participant guide](../rules/problems/README.md) to build your code with `lake build`.
Checking the locked interface and permitted axioms is the evaluator's job.

The eight Stage 1 tasks are `fib`, `partition`, `mertens`, `primecount`,
`permanent`, `ca-rule110`, `sha256`, and `polydisc`. Their fixed workspaces live
in `evaluation/problems/<id>/`, separate from editable `problems/<id>/Submission.lean`.
Shared judge code remains in the root `judge/` and `scripts/` directories.

## Run from the repository root

Install Python 3.9+, Git, and [elan](https://github.com/leanprover/elan). Initial
setup builds the pinned judge tools and prepares evaluation dependencies.
The `fib`, `mertens`, and `primecount` specifications use pinned Mathlib;
the other five are core-Lean-only. On macOS, also install GNU coreutils
(`brew install coreutils`).

```sh
bash evaluation/setup.sh --problem partition
python3 evaluation/run.py --problem partition --submission problems/partition/Submission.lean
```

Replace `partition` with the chosen task. Omit `--problem` from setup to prepare
all eight tasks. To evaluate another file or adjust the local timeout:

```sh
python3 evaluation/run.py --problem partition --submission path/to/Submission.lean --timeout 120
```

`--timeout` is not a total runtime limit. It sets the correctness-replay limit and
each case's shared build/export budget. The target-replay limit is the smaller of
this value and the group's published limit. The comparator keeps its 3,600-second
limit, and axiom audits keep their 300-second limit. Cases have independent budgets,
so the complete run can take longer than `--timeout`.

`--submission` defaults to `problems/<id>/Submission.lean`. The wrapper copies
only that file into a temporary payload and delegates to the canonical judge.
It does not modify your source or submit anything. Results are written to
`results/local-evaluation/<id>/`. Rejection, infrastructure error, and retry
return nonzero exit codes.

## What this measures

Each task uses its complete unseeded public input plan with one wall-time
measurement per case. The output reports correctness and per-case outcomes,
not an official score or Linux instruction-count ranking. An accepted
correctness proof does not mean every performance case passed.

This entrypoint has no official, private-seed, or reduced-plan mode. Unset
`PERF_COUNT`, official seed, cohort, remote-executor, and non-wall-time settings.
See the [problem statements](../rules/problems/README.md) for specifications,
case counts, and scoring rules.
