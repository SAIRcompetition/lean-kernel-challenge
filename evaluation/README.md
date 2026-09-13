# Optional local evaluation

You do not need this directory to develop or submit a solution. For the short
participant workflow, use [problems/fib](../problems/fib/README.md).
Its `lake build` command only compiles the submitted code and proofs; the checks
against the locked interface and permitted axioms belong to the evaluator.

This fib pilot separates the fixed judge workspace in `evaluation/problems/fib`
from the editable `problems/fib/Submission.lean`. Shared judge code remains in
the root `judge/` and `scripts/` directories during the pilot.

## Run from the repository root

Install Python 3.9+, Git, and [elan](https://github.com/leanprover/elan). Initial
setup downloads the pinned Lean/Mathlib dependencies and builds the judge tools.
On macOS, also install GNU coreutils (`brew install coreutils`).

```sh
bash evaluation/setup.sh
python3 evaluation/run.py --problem fib --submission problems/fib/Submission.lean
```

To evaluate a different file or increase the local time budget:

```sh
python3 evaluation/run.py --problem fib --submission path/to/Submission.lean --timeout 120
```

`--submission` defaults to `problems/fib/Submission.lean`. The wrapper copies only
that file to a temporary payload and delegates to the
canonical judge. It does not modify your source or submit anything. Results are
written to `results/local-evaluation/fib/`. A rejected submission, infrastructure
error, or retry returns a nonzero exit code.

## What this measures

This is the unseeded, six-case public fib plan with one wall-time measurement per
case. The output reports correctness and per-case outcomes; it is **not an
official score** or the official Linux instruction-count ranking. Check each
case: an accepted correctness proof does not mean every performance case passed.

This entrypoint has no official, private-seed, or reduced-plan mode. Unset
`PERF_COUNT`, official seed, cohort, remote-executor, and non-wall-time settings before using it. See the
[fib statement](../rules/problems/fib.md) for the fixed specification and rules.
