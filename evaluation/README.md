# Local evaluation

This optional, unsandboxed evaluator checks submissions and kernel computation.
Run only code you trust. The
[participant workflow](../rules/problems/README.md) does not require it.

## Requirements

Install Python 3.9+, Git, [elan](https://github.com/leanprover/elan), and a C/C++
toolchain; on macOS, install GNU coreutils (`brew install coreutils`). Setup needs
network access, and builds may use several GiB. Lean and the three Mathlib tasks
are pinned to **4.33.1**. Local runs do not enforce container memory limits; the
[official environment](../rules/evaluation.md#environment) still requires host
validation and has no published CPU model.

## Quick start

Run from the repository root:

```bash
bash evaluation/setup.sh --problem partition
python3 evaluation/run.py --problem partition
```

Replace `partition` with any [problem ID](../rules/problems/README.md). Setup
prepares its tools and dependencies; omit `--problem` for all eight tasks. It
hard-resets managed checkouts `../repro/comparator` and `../repro/lean4export`
to pinned revisions, so keep other work elsewhere or use the custom locations
described in [maintenance](maintainers.md).

The default input is `problems/<id>/Submission.lean`; `--problem` defaults to `fib`.
To use another file:

```bash
python3 evaluation/run.py --problem partition --submission /path/to/Submission.lean --timeout 120
```

Only that file is copied; the source is neither changed nor submitted. Results
are printed and saved to `results/local-evaluation/<id>/<path-hash>.json`;
rerunning the same path replaces them. Rejection, error, and retry return nonzero.

## Results and time limits

The judge checks the interface, universal proof, and axioms, then runs the
**complete unseeded public plan** with **one wall-time repetition** per case.
Wall time is not an official instruction count. Accepted does not mean every
case passed: correctness `C` is verification only, and computation total `T`
exists only for a complete pass. `replay_report` includes failed and unattempted
cases; unavailable measurements are `null` (shown as `—`), never zero. See the
[ranking rule](../rules/problems/README.md#scoring).

`--timeout` defaults to 120 seconds and is **not a total runtime limit**. It sets
each local correctness replay, each case's shared build/export, and generic
timing/legacy value-evaluation budgets. Target replay gets the smaller of this
value and its group limit. Comparator, correctness-axiom, and per-case shared
binding/axiom limits remain 600, 60, and 300 seconds. Thus the default gives
each correctness replay and case build/export 120 seconds; independent case
budgets can make the whole run longer.

The underlying override is `TIMING_TIMEOUT_SECONDS`; official evaluation forbids
it and uses [sealed budgets](../rules/problems/README.md#limits). Unset
`PERF_COUNT`, official seed/cohort, remote-executor, and non-wall-time settings:
this command has no official, private-seed, or reduced-plan mode. A local pass
does not establish official full-plan completion or hosted adoption. See
[maintenance and deployment](maintainers.md).
