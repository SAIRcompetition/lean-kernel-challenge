# Maintainer regression and image builds

These checks are separate from the [participant workflow](../README.md#quick-start).
For prerequisites and local single-file evaluation, see the [evaluation guide](README.md).
Run the commands below from the repository root.

## Source and regression checks

```bash
python3 scripts/sync_participants.py --check
python3 -m unittest discover -s tests
bash evaluation/setup.sh
python3 scripts/run_harness.py
```

The synchronization check compares participant specifications and dependency pins
with the fixed evaluator workspaces without changing submissions. The unit suite
reports any tests skipped because their optional tools are unavailable.

The harness checks the examples registered in `tests/harness_manifest.json`. For a
shorter development run:

```bash
python3 scripts/run_harness.py --quick --jobs 2
```

Each worker can use several GiB; the default is one worker. Raise concurrency only
after measuring available memory. A harness pass means its expected verdicts,
measurement records, and declared minimum performance coverage match. It does not
mean every input passed: a slow but correct baseline can meet the manifest's
requirements despite performance timeouts. Local wall-time results are not official
instruction-count scores.

## Evaluation image

```bash
docker build -t lean-kernel-judge .
```

The image-build gate uses two workers and `--quick --count 2 --timeout 120`.
For a smaller builder, reduce concurrency without reducing coverage:

```bash
docker build --build-arg HARNESS_JOBS=1 -t lean-kernel-judge .
```

Development-only options are:

- `--build-arg HARNESS_ONLY=mertens`: check only matching manifest problems.
- `--build-arg HARNESS_SKIP=1`: skip the gate entirely.

Neither option is valid for a production release build. Label those images as
partially gated or not gated, respectively, and do not promote them to production.
CI and release builds must run the full gate.

The build gate does not establish full-plan performance or official per-problem
memory enforcement. Validate both using the built image through the official wrapper
on the production host. Passing a container test on another machine is not production
PMU acceptance.

## Official evaluation

Use [reference-answer preparation and the isolated wrapper](../docs/reference-answers.md).
The local evaluator uses an unsandboxed development path; never use it for untrusted
submissions. The production wrapper runs one submission per non-root container with
networking disabled, read-only submission files, and bounded CPU, memory, and processes.

Each fixed `evaluation/problems/<id>/config.json` supplies its own memory limit.
The wrapper applies that limit to memory and memory-plus-swap, allowing no additional
swap, and checks agreement with the image policy and cgroup. Command-line memory
options can assert the published limit but cannot override it.

Matrix permanent uses 8192 MiB; the other seven problems retain provisional 4096 MiB
limits pending confirmation. Changing a limit requires a rebuilt image, a new cohort,
and a complete rescore of that problem's comparison set. Track official PMU, resource,
and full-cohort acceptance in the [launch checklist](../docs/pre-launch-checklist.md).
