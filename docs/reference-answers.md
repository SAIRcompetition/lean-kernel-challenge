# Preparing official reference answers

Stage 1 obtains expected outputs independently of contestant implementations.
`judge/reference_answers.py` provides exact Python algorithms for all nine
problems, using only the standard library. Operators prepare each problem's
complete hidden plan once and reuse its private answer bundle across submissions
in that cohort. A separately produced table is also acceptable if it matches the
same schema, specification, and input plan.

## Prepare and evaluate

Use the same checked-out evaluator and problem definitions as the official image.
Pass the secret seed through stdin; do not commit answers or include them in logs:

```bash
python3 scripts/prepare_reference.py --problem fib --official \
  --output /private/evaluation/fib-answers.json < /private/evaluation/seed.txt

PERF_SEED="$(cat /private/evaluation/seed.txt)" scripts/run_isolated.sh \
  --problem fib --submission /absolute/path/to/submission \
  --results /absolute/path/to/results --cohort stage1-round1 \
  --reference-answers /private/evaluation/fib-answers.json --perfmon
```

The seed file contains one UTF-8 line. Preparation writes a new mode-0600 file
and refuses to overwrite an existing one. `--official` rejects `PERF_COUNT`
overrides. Preparation without `--official` uses the complete local plan;
ordinary local judge runs prepare their own submission-independent answers for
the selected development plan. Reduced development plans are not official scores.

The wrapper sends the seed line followed by the JSON bundle and EOF over Docker
stdin. The judge consumes both before starting contestant processes. The private
file is never mounted inside the container, and its content is not passed in
environment variables or command arguments. The maximum bundle size is 8 MiB.
Platform callers must provide this new `--reference-answers` argument for official
Stage 1 runs; a missing bundle fails closed as an evaluation error.

## Data and validation

The bundle has exactly these fields:

```json
{
  "schema": "reference-answers-v1",
  "problem": "fib",
  "spec_sha256": "<SHA-256 of the locked Spec.lean bytes>",
  "answers": [
    {"n": 3, "type": "Nat", "value": "2"}
  ]
}
```

This small example illustrates the format; an official bundle must cover the
complete resolved plan in order. Values are canonical decimal strings, allowing
large exact integers without JSON number rounding. `mertens` and `polydisc` use
`Int`; the other seven use `Nat`. Negative zero, signs on zero, leading zeros,
duplicate or missing inputs, wrong output types, and mismatched specifications
are rejected before contestant code executes.

The cohort seals the canonical JSON bundle's SHA-256, specification digest, and
answer count, alongside its input plan and scoring policy. A changed answer
bundle therefore creates a different cohort. These digests bind data; custody of
the private bundle and verdicts remains an organizer responsibility. Reference
implementation checks against trusted Lean specifications remain part of release
validation. Missing or malformed reference data is never a contestant timeout.

The kernel still checks the universal correctness proof and directly reduces
`Submission.impl n` against each literal output during the generated target check.
A numerically wrong reference answer cannot make an incorrect equality pass the
kernel; it causes an evaluation error requiring organizer investigation. Expected
answers do not become axioms, and the universal proof is not used to bypass the
measured target reduction. The legacy `conv` development task retains its separate
Lean value oracle and is outside the nine scored problems.
