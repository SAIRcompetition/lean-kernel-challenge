# Lean Competition — kernel-computation track evaluation image.
#
# Reproduces the official evaluation environment: Linux, pinned Lean toolchain,
# the pinned verification tools (comparator, lean4export, timer-kernel), perf for
# instruction counting, and landrun for sandboxing untrusted submissions.
#
# Build:  docker build -t lean-kernel-judge .
# Judge:  docker run --rm -v "$PWD/examples:/work/examples:ro" lean-kernel-judge \
#           python3 judge/judge.py run --problem fib --submission examples/submissions/fib/doubling
# Note: instruction counting needs a host that exposes PMU counters to the container
#       (bare-metal Linux; --privileged or --cap-add PERFMON may be required).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates build-essential python3 python3-minimal \
      linux-tools-generic golang-go \
    && rm -rf /var/lib/apt/lists/*

# --- elan + pinned Lean toolchain ---
ENV ELAN_HOME=/opt/elan
ENV PATH=/opt/elan/bin:$PATH
ARG LEAN_TOOLCHAIN=leanprover/lean4:v4.32.0-rc1
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

# Point the judge at the image-built tools (override of the repo-relative defaults).
ENV COMPARATOR_BIN=/work/tools/comparator/.lake/build/bin/comparator \
    LEAN4EXPORT_BIN=/work/tools/lean4export/.lake/build/bin \
    TIMER_BIN=/work/lean-kernel-challenge/judge/timer-kernel/.lake/build/bin/kernel

# Green-gate on build so a broken image fails fast.
# RUN python3 scripts/run_harness.py --quick   # (enable once perf/PMU is available in CI)

ENTRYPOINT ["/bin/bash"]
