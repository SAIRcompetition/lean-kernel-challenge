# Lean Kernel Challenge Stage 1 — Problem Leaderboards

Stage 1 has nine independent 100-point problem leaderboards. There is no
cross-problem total and no relative-placement aggregation. `conv` is not part
of these nine leaderboards.

Every submission must first pass the universal correctness and axiom gate. A
performance case passes when every configured target replay completes within
the case's published per-repetition watchdog. Stage 1 uses three repetitions
and records their median. If a group declares a
kernel-instruction limit, the median measurement must also stay within that
limit. Its required preparation must also complete under the common ceilings
described below. Exact official inputs are hidden during
the evaluation phase, but every group publishes its scale, generator, number
of cases, milestones, and limits. The cohort commits to the hidden seed and the
fully resolved plan; both are released after that cohort's evaluation.

Within a problem, ranking is determined by:

1. total problem points;
2. points in harder groups, from the highest group downward;
3. the problem's declared case profile, again from harder groups downward;
4. when eligible, the problem's declared kernel-work tie-break; and
5. where declared, correctness-closure work as the final tie-break.

Direct-range problems compare the exact pass/fail profile because later cases
have larger hidden inputs within the published ranges. Packed and uniformly
seeded cases within one group
are interchangeable: they compare only the number passed, never the arbitrary
hidden seed index. Equal partial seeded profiles remain tied; measured work
breaks ties after the complete seeded plan passes.

The tables below are the public scoring contract. A milestone such as `2/2 →
15` means that both hidden cases must pass to earn 15 points. `1/2 → 9, 2/2 →
18` awards the two cases independently. Every official job runs within the
common 4 GiB memory envelope; the tables give the watchdog for each target
timing repetition. A memory kill during a case's preparation or target replay
fails that case. Cases are independent in time: one case cannot consume
another's watchdog. Unscored value generation, theorem build/export, and axiom audit use
independent per-case ceilings of 1,800 seconds, 1,800 seconds combined, and
300 seconds, respectively.

The universal comparator has a 3,600-second watchdog and the correctness axiom
audit has a 300-second watchdog. A submission is scoreable only when all three
correctness-closure replays also finish; each replay has a 1,800-second
watchdog. A correctness-gate memory kill rejects the submission; a memory kill
during timed correctness replay leaves it accepted but unscored.

Sampler terms used below have these exact meanings:

- **geometric range:** distinct, strictly increasing integers selected across
  the inclusive published range, with deterministic 15% seed-derived jitter;
- **uniform integer:** distinct seed-derived integers sampled without bias from
  the inclusive published range; and
- **packed:** the published scale in the high bits and a distinct seed-derived
  32-bit instance seed in the low bits.

The `fib`, `partition`, `mertens`, and `primecount` tables use the geometric-range
sampler. Their two cases are ordered from the smaller resolved input to the larger.

## `fib` — scaling frontier

Both cases in a group must pass. Target-declaration work breaks ties;
correctness-closure work is the final tie-break.

| Group | Hidden `n` range | Cases | Points | Per-repetition limit |
|---|---:|---:|---:|---:|
| F1 | 10,000–30,000 | 2 | 2/2 → 5 | 15 s |
| F2 | 50,000–100,000 | 2 | 2/2 → 10 | 30 s |
| F3 | 150,000–300,000 | 2 | 2/2 → 15 | 60 s |
| F4 | 400,000–700,000 | 2 | 2/2 → 25 | 90 s |
| F5 | 800,000–1,200,000 | 2 | 2/2 → 45 | 120 s |

## `partition` — subtask frontier

Both cases in a group must pass. Target-declaration work breaks ties;
correctness-closure work is the final tie-break.

| Group | Hidden `n` range | Cases | Points | Per-repetition limit |
|---|---:|---:|---:|---:|
| P1 | 10–20 | 2 | 2/2 → 5 | 15 s |
| P2 | 25–35 | 2 | 2/2 → 10 | 30 s |
| P3 | 50–100 | 2 | 2/2 → 15 | 60 s |
| P4 | 200–500 | 2 | 2/2 → 25 | 120 s |
| P5 | 1,000–2,000 | 2 | 2/2 → 45 | 300 s |

## `mertens` — independent arithmetic cases

Cases score independently because arithmetic inputs can have different
factorization structure. Target-declaration work breaks ties;
correctness-closure work is the final tie-break.

| Group | Hidden `n` range | Cases | Milestones | Per-repetition limit |
|---|---:|---:|---:|---:|
| M1 | 50–100 | 2 | 1/2 → 3, 2/2 → 6 | 15 s |
| M2 | 200–500 | 2 | 1/2 → 6, 2/2 → 12 | 30 s |
| M3 | 1,000–3,000 | 2 | 1/2 → 9, 2/2 → 18 | 90 s |
| M4 | 10,000–30,000 | 2 | 1/2 → 13, 2/2 → 26 | 240 s |
| M5 | 100,000–300,000 | 2 | 1/2 → 19, 2/2 → 38 | 600 s |

## `primecount` — robust scaling frontier

Both cases in a group must pass. Target-declaration work breaks ties;
correctness-closure work is the final tie-break.

| Group | Hidden `n` range | Cases | Points | Per-repetition limit |
|---|---:|---:|---:|---:|
| Q1 | 1,000–3,000 | 2 | 2/2 → 5 | 30 s |
| Q2 | 5,000–10,000 | 2 | 2/2 → 10 | 60 s |
| Q3 | 30,000–100,000 | 2 | 2/2 → 15 | 120 s |
| Q4 | 300,000–1,000,000 | 2 | 2/2 → 25 | 300 s |
| Q5 | 3,000,000–10,000,000 | 2 | 2/2 → 45 | 600 s |

## `permanent` — seeded matrix groups

An input is `(dimension << 32) | seed`. The public generator produces a seeded
0/1 matrix with exactly three distinct ones per row: the diagonal and two
seeded off-diagonal columns. All five matrices in a group must pass. Seed
indices do not break partial ties. After the complete plan passes,
target-declaration work breaks ties and
correctness-closure work is the final tie-break.

| Group | Dimension | Hidden seeds | Points | Per-repetition limit |
|---|---:|---:|---:|---:|
| R1 | 4 | 5 | 5/5 → 5 | 2 s |
| R2 | 6 | 5 | 5/5 → 10 | 2 s |
| R3 | 8 | 5 | 5/5 → 15 | 2 s |
| R4 | 10 | 5 | 5/5 → 25 | 3 s |
| R5 | 12 | 5 | 5/5 → 45 | 3 s |

## `saw` — seeded-obstacle prefix frontier

An input is `(length << 32) | seed`. The public generator creates a sparse
obstacle field and leaves the non-negative x-axis open, so every instance has
at least one valid self-avoiding walk. Both cases in a group must pass. A group
scores only after every lower group has passed. Seed indices do not break
partial ties. An ineligible group earns no points and contributes zero to the
ranking case-count profile, even if its cases complete. After the complete
plan passes, the tie-break combines the correctness closure and target replays.

| Group | Walk length | Hidden seeds | Points | Per-repetition limit |
|---|---:|---:|---:|---:|
| S1 | 6 | 2 | 2/2 → 5 | 10 s |
| S2 | 7 | 2 | 2/2 → 10 | 20 s |
| S3 | 8 | 2 | 2/2 → 15 | 25 s |
| S4 | 9 | 2 | 2/2 → 25 | 60 s |
| S5 | 10 | 2 | 2/2 → 45 | 120 s |

## `ca-rule110` — seeded 256-cell evolution

An input is `(steps << 32) | seed`. Each seed creates a seed-specific,
approximately half-dense 256-cell initial row, eliminating the old fixed
32-cell short orbit. Cases score independently, but seed indices do not break
partial ties. After the complete plan passes, the tie-break combines the
correctness closure and target replays.

| Group | Evolution steps | Hidden seeds | Milestones | Per-repetition limit |
|---|---:|---:|---:|---:|
| C1 | 512 | 2 | 1/2 → 4, 2/2 → 8 | 30 s |
| C2 | 2,048 | 2 | 1/2 → 6, 2/2 → 12 | 45 s |
| C3 | 8,192 | 2 | 1/2 → 9, 2/2 → 18 | 60 s |
| C4 | 32,768 | 2 | 1/2 → 13, 2/2 → 26 | 90 s |
| C5 | 131,072 | 2 | 1/2 → 18, 2/2 → 36 | 120 s |

## `sha256` — independent seeded chains

An input is `(steps << 32) | seed`. The 32-bit seed deterministically expands
to a seed-specific 256-bit initial digest, so cases do not deliberately share
a chain prefix. Cases score independently, but seed indices do not break
partial ties. After the complete plan passes, the tie-break combines the
correctness closure and target replays.

| Group | Chain steps | Hidden seeds | Milestones | Per-repetition limit |
|---|---:|---:|---:|---:|
| H1 | 2 | 2 | 1/2 → 3, 2/2 → 6 | 30 s |
| H2 | 8 | 2 | 1/2 → 5, 2/2 → 10 | 30 s |
| H3 | 32 | 2 | 1/2 → 8, 2/2 → 16 | 45 s |
| H4 | 128 | 2 | 1/2 → 13, 2/2 → 26 | 60 s |
| H5 | 512 | 2 | 1/2 → 21, 2/2 → 42 | 120 s |

## `polydisc` — degree-24 coefficient bands

The degree is always 24. Each group uses the uniform-integer sampler to select
two distinct seed-derived polynomial inputs from a range that fixes the maximum coefficient width. Cases score
independently and every band is worth 20 points. Seed indices do not break
partial ties. After the complete plan passes, target-declaration work breaks
ties and correctness-closure work is the final tie-break.

| Group | Public input range | Max coefficient width | Milestones | Per-repetition limit |
|---|---:|---:|---:|---:|
| D1 | 2^18–2^25 | 15 bits | 1/2 → 10, 2/2 → 20 | 120 s |
| D2 | 2^27–2^35 | 36 bits | 1/2 → 10, 2/2 → 20 | 180 s |
| D3 | 2^37–2^45 | 205 bits | 1/2 → 10, 2/2 → 20 | 300 s |
| D4 | 2^47–2^55 | 1,001 bits | 1/2 → 10, 2/2 → 20 | 600 s |
| D5 | 2^57–2^63 | 3,484 bits | 1/2 → 10, 2/2 → 20 | 900 s |
