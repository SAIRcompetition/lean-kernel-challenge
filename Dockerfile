# Lean Kernel Challenge — kernel-computation track evaluation image.
#
# Reproduces the official evaluation environment: Linux, pinned Lean toolchain,
# the pinned verification tools (comparator, lean4export, timer-kernel), perf for
# instruction counting, and landrun for sandboxing untrusted submissions.
#
# Build:  docker build -t lean-kernel-judge .
# Judge one untrusted submission — the container IS the sandbox boundary. Run each job
# with resource + isolation limits (the judge process does not enforce these itself):
#   docker run --rm \
#     --network none --memory 4g --cpus 2 --pids-limit 512 \
#     --cap-add PERFMON --security-opt no-new-privileges \
#     --user judge \
#     -v "$PWD/examples:/work/examples:ro" lean-kernel-judge \
#     python3 judge/judge.py run --problem fib --submission examples/submissions/fib/doubling
# --network none stops exfiltration; --memory/--cpus/--pids-limit bound the job and let
# the runtime kill EVERY process in it (a setsid escape cannot outlive the container);
# --cap-add PERFMON exposes PMU counters for perf; run one job per container.
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

# Point the judge at the image-built tools (override of the repo-relative defaults) and
# switch to the production timing metric + sandbox policy.
ENV COMPARATOR_BIN=/work/tools/comparator/.lake/build/bin/comparator \
    LEAN4EXPORT_BIN=/work/tools/lean4export/.lake/build/bin \
    TIMER_BIN=/work/lean-kernel-challenge/judge/timer-kernel/.lake/build/bin/kernel \
    TIMING_METRIC=perf_instructions \
    SANDBOX_MODE=container

# Green-gate on build so a broken image fails fast (needs PMU access at build time).
# RUN TIMING_METRIC=wall_time python3 scripts/run_harness.py --quick

# Non-root user for running untrusted submissions (a same-UID descendant must not be
# able to chmod/replace image files or the tools). The judge writes only under results/.
RUN useradd -m -u 10001 judge && chown -R judge:judge /work
USER judge

# CMD (not ENTRYPOINT) so `docker run IMAGE python3 judge/judge.py ...` works as shown
# in the header, while a bare `docker run IMAGE` still drops into a shell.
CMD ["/bin/bash"]
