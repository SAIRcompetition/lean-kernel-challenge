# Lean Kernel Challenge Stage 1 — Problem Leaderboards

Stage 1 has eight independent 100-point problem leaderboards. There is no
cross-problem total or relative-placement aggregation. `conv` is an experimental
development task and is excluded.

For detailed task descriptions, input and output formats, worked examples, and starter code,
see the [Problem Statements](problems/README.md).

Every submission must pass the universal correctness and axiom gate. For each
problem, an otherwise scoreable submission receives **100 points only if every
case in the complete hidden plan passes**. Any failed case gives **0 points and
infinite ranking cost**. There is no partial credit, group-point comparison,
case-profile tie-break, or separate correctness-cost tie-break. Zero-point
submissions remain tied regardless of which or how many cases passed.

Among full-plan passes, lower instruction cost wins:

- **Target work (`T`):** the sum of all target-declaration replay medians.
- **Combined work (`T + C`):** target work plus the correctness-closure replay median once.

Equal costs remain tied. `ca-rule110` and `sha256` use combined work;
the other six problems use target work. A baseline that passes every case may
score 100; contestants compete by reducing instruction cost.

A case passes only when its preparation succeeds and all three target replays
finish within the published per-repetition watchdog. The cost is their median.
Any published instruction limit also applies to that median. All three correctness
replays must finish for the submission to be scoreable. Infrastructure failures
and incomplete evaluations require investigation or re-evaluation; they are not
scored as contestant failures. See [`evaluation.md`](evaluation.md) for the full
failure and measurement rules.

The groups below define inputs and resource limits, not separate awards or
prerequisites. Each problem's `evaluation.memory_mb` in its fixed `config.json`
defines its memory limit in MiB, published before official use. The configuration is
in `evaluation/problems/<id>/` for all eight tasks. Matrix permanent uses
8192 MiB (8 GiB); the other seven problems retain provisional 4096 MiB (4 GiB) limits.
Official-host acceptance remains pending. Organizers may revise a limit; a revision requires
a new cohort and a complete rescore of the problem's comparison set. Each target process has the table's
watchdog. Theorem build/export has a separate 1,800-second combined limit per
case, and its axiom audit has a 300-second limit. One case does not consume
another's time allowance. The correctness comparator has a 3,600-second limit,
its axiom audit a 300-second limit, and each correctness replay a 1,800-second
limit. Official standard outputs are prepared independently before judging and
are outside the measured work.

Exact official inputs stay hidden during evaluation. The final official cohort's
seed and complete plan are released after its evaluation. This commitment does
not apply to provisional reference inputs or seeds.

Sampler terms:

- **geometric range:** distinct, strictly increasing integers with deterministic
  15% seed-derived jitter within the inclusive range. With two cases, one starts
  at each endpoint and is jittered inward; unseeded local runs use the endpoints.
- **uniform integer:** distinct seed-derived integers sampled without bias from
  the inclusive range.
- **packed:** the public scale in the high bits and a distinct seed-derived
  32-bit instance seed in the low bits.

## `fib`

The input is the Fibonacci index. All six cases must pass; full-plan passes compare target work.

| Group | Hidden `n` range | Cases | Per-repetition limit |
| --- | ---: | ---: | ---: |
| F1 | 5,000–10,000 | 2 | 30 s |
| F2 | 20,000–40,000 | 2 | 60 s |
| F3 | 80,000–150,000 | 2 | 120 s |

## `partition`

The input is the integer whose partitions are counted. All six cases must pass; full-plan passes
compare target work.

| Group | Hidden `n` range | Cases | Per-repetition limit |
| --- | ---: | ---: | ---: |
| P1 | 14–18 | 2 | 30 s |
| P2 | 22–26 | 2 | 60 s |
| P3 | 32–36 | 2 | 120 s |

## `mertens`

The input is the upper bound of the Möbius sum. All six cases must pass; full-plan passes
compare target work.

| Group | Hidden `n` range | Cases | Per-repetition limit |
| --- | ---: | ---: | ---: |
| M1 | 25–50 | 2 | 30 s |
| M2 | 80–150 | 2 | 60 s |
| M3 | 300–500 | 2 | 120 s |

## `primecount`

The input is the inclusive prime-counting bound. All six cases must pass; full-plan passes
compare target work.

| Group | Hidden `n` range | Cases | Per-repetition limit |
| --- | ---: | ---: | ---: |
| Q1 | 50–100 | 2 | 30 s |
| Q2 | 150–300 | 2 | 60 s |
| Q3 | 600–1,000 | 2 | 120 s |

## `permanent`

Memory limit: **8192 MiB (8 GiB)**.

An input is `(dimension << 32) | seed`. The public generator produces a 0/1 matrix with exactly
three distinct ones per row: the diagonal and two seeded off-diagonal columns. All 15 cases must
pass; full-plan passes compare target work.

| Group | Dimension | Hidden seeds | Per-repetition limit |
| --- | ---: | ---: | ---: |
| R1 | 6 | 5 | 30 s |
| R2 | 12 | 5 | 60 s |
| R3 | 16 | 5 | 120 s |

## `ca-rule110`

An input is `(steps << 32) | seed`. Each seed determines a 256-cell initial row. All six cases
must pass; full-plan passes compare combined work.

| Group | Evolution steps | Hidden seeds | Per-repetition limit |
| --- | ---: | ---: | ---: |
| C1 | 2 | 2 | 30 s |
| C2 | 4 | 2 | 60 s |
| C3 | 8 | 2 | 120 s |

## `sha256`

An input is `(steps << 32) | seed`. The seed expands to a 256-bit initial digest for a SHA-256
chain. All six cases must pass; full-plan passes compare combined work.

| Group | Chain steps | Hidden seeds | Per-repetition limit |
| --- | ---: | ---: | ---: |
| H1 | 4 | 2 | 30 s |
| H2 | 32 | 2 | 60 s |
| H3 | 512 | 2 | 120 s |

## `polydisc`

The polynomial degree is always 24. Stage 1 samples three of the five width bands supported by
the specification: D1, D3, and D5 correspond to levels 0, 2, and 4. Each range fixes the maximum
coefficient width and uses the uniform-integer sampler. All six cases must pass; full-plan
passes compare target work.

| Group | Public input range | Max coefficient width | Cases | Per-repetition limit |
| --- | ---: | ---: | ---: | ---: |
| D1 | 2^18–2^25 | 15 bits | 2 | 30 s |
| D3 | 2^37–2^45 | 205 bits | 2 | 60 s |
| D5 | 2^57–2^63 | 3,484 bits | 2 | 120 s |
