# Lean Kernel Challenge — kernel-computation track evaluation image.
#
# Reproduces the official evaluation environment: Linux, pinned Lean toolchain,
# the pinned verification tools (comparator, lean4export, timer-kernel), perf for
# instruction counting, and landrun for sandboxing untrusted submissions.
#
# Build:  docker build -t lean-kernel-judge .
# Judge one untrusted submission ONLY through scripts/run_isolated.sh.  The host-side
# wrapper supplies the mandatory network/resource/user restrictions, mounts exactly one
# submission read-only, mounts results read/write, and injects the official PERF_SEED once
# over stdin (never into the untrusted elaborator environment) with a public cohort id.
# `--perfmon` on that wrapper adds CAP_PERFMON on hosts that require it for PMU counting.
#
# Multi-stage layout: the builder stage carries everything the tool builds need
# (Go toolchain for landrun, git clones, lake build products); the runtime stage
# keeps only what judging needs.  Build-time-only content (Go, tool-repo checkouts,
# .git metadata) never enters the published image.  The builder's package set and
# the elan/landrun RUN lines are kept byte-identical to the historical single-stage
# layout so per-toolchain-version layers stay Docker-cache-reusable.

FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates build-essential python3 python3-minimal \
      linux-tools-generic golang-go \
    && rm -rf /var/lib/apt/lists/*

# --- elan + pinned Lean toolchain ---
ENV ELAN_HOME=/opt/elan
ENV PATH=/opt/elan/bin:$PATH
ARG LEAN_TOOLCHAIN=leanprover/lean4:v4.33.1
RUN curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
      | sh -s -- -y --default-toolchain "$LEAN_TOOLCHAIN" \
    && elan toolchain install "$LEAN_TOOLCHAIN"

# --- landrun sandbox (Linux Landlock) at the pin used by lean-eval ---
ARG LANDRUN_REV=5ed4a3db3a4ad930d577215c6b9abaa19df7f99f
RUN GOBIN=/usr/local/bin go install github.com/zouuup/landrun/cmd/landrun@${LANDRUN_REV}

WORKDIR /work
COPY . /work/lean-kernel-challenge
WORKDIR /work/lean-kernel-challenge

# --- build the pinned verification tools into fixed image paths ---
ENV TOOLS_DIR=/work/tools
RUN bash scripts/setup.sh

# Drop build-time-only content: every cloned git repository (tool repos and lake
# package checkouts) keeps only its working tree.  Nothing at runtime reads .git;
# judge containers run with --network none and never fetch.
RUN find /work/tools /work/lean-kernel-challenge/judge/timer-kernel/.lake \
      -type d -name .git -exec rm -rf {} +

# --- runtime stage: only what the judge executes ---
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
# gcc/build-essential stays: the judge compiles generated Submission.lean C
# output with lake at runtime.  linux-tools-generic provides perf for the
# container-local instruction-counting path.  git stays for lake workspace
# tooling.  Go is build-only and does not ship here.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates build-essential python3 linux-tools-generic \
    && rm -rf /var/lib/apt/lists/*

ENV ELAN_HOME=/opt/elan
ENV PATH=/opt/elan/bin:$PATH
ENV TOOLS_DIR=/work/tools
ENV COMPARATOR_BIN=/work/tools/comparator/.lake/build/bin/comparator \
    LEAN4EXPORT_BIN=/work/tools/lean4export/.lake/build/bin \
    TIMER_BIN=/work/lean-kernel-challenge/judge/timer-kernel/.lake/build/bin/kernel \
    TIMING_METRIC=perf_instructions \
    SANDBOX_MODE=container

COPY --from=builder /opt/elan /opt/elan
COPY --from=builder /usr/local/bin/landrun /usr/local/bin/landrun
COPY --from=builder /work/tools /work/tools
COPY --from=builder /work/lean-kernel-challenge /work/lean-kernel-challenge
WORKDIR /work/lean-kernel-challenge

# Green-gate every problem and example during the image build.  Wall time avoids
# requiring PMU access in the Docker build sandbox; official runs still use the
# metric configured above.  Running this gate in the runtime stage proves the
# trimmed image (not the builder) can judge end to end.
RUN TIMING_METRIC=wall_time SANDBOX_MODE=none \
      python3 scripts/run_harness.py --quick --count 2 --timeout 120 \
    && rm -rf results

# Non-root user for running untrusted submissions.  Verification tools, problem
# templates, and the repository remain root-owned; only the generated-results tree is
# writable by the judge UID.  The official wrapper shadows this directory with its
# persistent read/write results bind mount.
RUN useradd -m -u 10001 judge \
    && mkdir -p /work/lean-kernel-challenge/results \
    && chown -R judge:judge /work/lean-kernel-challenge/results
USER judge

# The supported host entry point is scripts/run_isolated.sh.  CMD remains a shell
# solely for image diagnostics; it is not an evaluation command.
CMD ["/bin/bash"]
