# Local evaluation

This optional evaluator checks submissions and measures kernel computation.
It is unsandboxed: run only code you trust. Development and submission need only
the [participant workflow](../rules/problems/README.md).

## Requirements

Install Python 3.9+, Git, [elan](https://github.com/leanprover/elan), and a C/C++ build
toolchain; on macOS, also install GNU coreutils (`brew install coreutils`). Setup needs
network access. Lean is pinned to **4.33.1**, as is Mathlib for the three tasks using it.
Builds and evaluation can use several GiB of memory.

Local runs do not enforce container memory limits. The
[official environment](../rules/evaluation.md#environment) remains subject to
production-host validation; the repository does not yet specify its CPU model.

## Quick start

Run from the repository root:

```bash
bash evaluation/setup.sh --problem partition
python3 evaluation/run.py --problem partition
```

Replace `partition` with any [problem ID](../rules/problems/README.md).
Setup prepares the tools and selected dependencies; omit `--problem` to prepare all
eight tasks. It resets managed checkouts `../repro/comparator` and `../repro/lean4export`
to pinned revisions. Keep unrelated work elsewhere. For custom tool locations,
see [maintenance](maintainers.md).

The default input is `problems/<id>/Submission.lean`; `--problem` defaults to `fib`.
To use another file:

```bash
python3 evaluation/run.py --problem partition --submission /path/to/Submission.lean --timeout 120
```

Only the selected file is copied; your source is neither modified nor submitted.
Per-case results are printed and saved to `results/local-evaluation/<id>/<path-hash>.json`.
Rerunning the same source path replaces that result. Rejection, error, and retry
return nonzero exit codes.

## Results and time limits

The judge checks the interface, universal proof, and permitted axioms, then uses the
complete unseeded public plan with **one wall-time repetition** per case. Accepted
does not mean every performance case passed. Wall time is not an official instruction
count. Current JSON reports apply `computation-total-v1` to that development metric:
correctness C is verification only, and T exists only for a complete pass.
`replay_report` lists every case, including failures and unattempted cases, with
separate phase measurements. Failed or unavailable measurements are `null` (shown
as `—`), never zero. See the [ranking rule](../rules/problems/README.md#scoring) and
[implementation status](../rules/problems/README.md#implementation-status).

`--timeout` defaults to 120 seconds and is **not a total runtime limit**. It
replaces the development budgets for correctness replay and each case's shared
build/export work; it also sets the legacy value-evaluation budget. A positive
override can increase or decrease those budgets. Target replay uses the smaller
of this value and the group's limit. The comparator remains fixed at 600 seconds,
the correctness axiom audit at 60 seconds, and each case's shared binding-plus-axiom
audit at 300 seconds. With the default, correctness replay and shared build/export
each have 120 seconds, while target replay retains its group's 30-, 60-, or
120-second limit. Cases have independent budgets, so a run can take longer.

This development override is `TIMING_TIMEOUT_SECONDS`; official evaluation
forbids it and uses the [sealed stage budgets](../rules/problems/README.md#limits).
Local quick checks do not demonstrate that a proof finishes under the complete
official plan or that a hosted platform has adopted the revised budgets.

Unset `PERF_COUNT`, official seed/cohort, remote-executor, and non-wall-time settings.
There is no official, private-seed, or reduced-plan mode. See
[maintenance and deployment](maintainers.md) for the image and fixed evaluator files.
