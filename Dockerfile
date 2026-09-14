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
# Prefer host-prebuilt tools (staged by scripts/prebuild-tools.sh, gitignored);
# fall back to compiling them inside the image.  Both paths produce the same
# pinned tool binaries; the runtime image content is identical either way.
ENV TOOLS_DIR=/work/tools
RUN if [ -d prebuilt-tools/tools ]; then \
      mkdir -p /work/tools evaluation/judge/timer-kernel/.lake/build \
      && cp -a prebuilt-tools/tools/. /work/tools/ \
      && cp -a prebuilt-tools/timer-kernel/.lake/build/bin evaluation/judge/timer-kernel/.lake/build/ \
      && echo "using host-prebuilt verification tools"; \
    else \
      bash scripts/setup.sh; \
    fi

# Problem dependencies are required even when verification tools came from the
# host-prebuilt branch. Prepare them while networking is available; evaluation
# stages only each problem's pinned import closure and never fetches packages.
# Participant builds run from a developer checkout, not the evaluator image;
# package source trees and their git history need not enter the runtime image.
RUN python3 scripts/prepare_problem_dependencies.py \
    && rm -rf /work/lean-kernel-challenge/evaluation/problems/fib/.lake/packages \
              /work/lean-kernel-challenge/evaluation/problems/mertens/.lake/packages \
              /work/lean-kernel-challenge/evaluation/problems/primecount/.lake/packages

# Drop build-time-only content: every cloned git repository (tool repos and lake
# package checkouts) keeps only its working tree.  Nothing at runtime reads .git;
# judge containers run with --network none and never fetch.
RUN find /work/tools /work/lean-kernel-challenge/evaluation/judge/timer-kernel/.lake \
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

# Ubuntu's /usr/bin/perf launcher selects a tools directory using uname -r,
# which is the host kernel inside a container. Use the image's packaged binary
# directly so a host/image kernel-package patch mismatch cannot hide it. Require
# exactly one candidate; PMU permissions and full instructions counting are
# still checked by the judge on the actual execution host.
RUN set -eu; set -- /usr/lib/linux-tools-*/perf; \
    if [ "$#" -ne 1 ] || [ ! -f "$1" ] || [ ! -x "$1" ]; then \
      echo "expected one executable packaged perf binary under /usr/lib/linux-tools-*/perf" >&2; \
      exit 1; \
    fi; \
    ln -s "$1" /usr/local/bin/perf

ENV ELAN_HOME=/opt/elan
ENV PATH=/opt/elan/bin:$PATH
ENV TOOLS_DIR=/work/tools
ENV COMPARATOR_BIN=/work/tools/comparator/.lake/build/bin/comparator \
    LEAN4EXPORT_BIN=/work/tools/lean4export/.lake/build/bin \
    TIMER_BIN=/work/lean-kernel-challenge/evaluation/judge/timer-kernel/.lake/build/bin/kernel \
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
# HARNESS_JOBS controls only cross-submission parallelism. The regression check
# caps each group's samples at two and uses the explicit development time budget
# below. It checks the manifest's verdict and coverage requirements; individual
# performance-input timeouts may be expected, particularly for slow baselines.
# This local-mode build check does not enforce official per-problem memory limits.
# Validate those limits in wrapper-launched containers after the policy is configured.
# A worker can consume several GiB (the heaviest cases peak at 2.3-4.9 GiB
# each), so the gate runs two workers everywhere: the one setting measured to
# fit a 16 GiB builder such as the hosted CI runner, with the worst pair near
# 8 GiB. Deployment builds use this default rather than their own
# counts; a smaller builder can pass `--build-arg HARNESS_JOBS=1`.
# HARNESS_ONLY is the one explicit narrowing: when set, the gate judges only
# the manifest cases whose problem contains the substring (run_harness.py
# --only; no match fails the build). It exists for development builds and for
# test-environment rehearsals of a pin advance, where the full gate's wall
# time dominates every iteration. An image built with it has NOT been proven
# on every problem: a deployment pipeline that passes it must label the image
# as partially gated and must never promote such an image beyond its test
# environment. Empty (the default) keeps the full gate.
# HARNESS_SKIP is the full opt-out: when set to "1", the gate does not run at
# all (HARNESS_ONLY is not consulted). It exists for non-production deployment
# builds (test and beta environments) whose iteration time the serial gate
# dominates. This option supplies no substitute validation of the pinned commit.
# An image built with it has NOT been green-gated at build time: a deployment
# pipeline that consumes it must label the image as not gated and must never
# promote it to a production environment, whose builds always run the full
# gate. Empty (the default) keeps the gate.
ARG HARNESS_JOBS=2
ARG HARNESS_ONLY=
ARG HARNESS_SKIP=
RUN if [ "$HARNESS_SKIP" = "1" ]; then \
        echo "HARNESS_SKIP=1: build-time green gate skipped"; \
    else \
        TIMING_METRIC=wall_time SANDBOX_MODE=none \
          python3 scripts/run_harness.py --quick --count 2 --timeout 120 --jobs "$HARNESS_JOBS" \
            ${HARNESS_ONLY:+--only "$HARNESS_ONLY"}; \
    fi \
    && rm -rf results

# Non-root user for running untrusted submissions.  Verification tools, problem
# templates, and the repository remain root-owned; only the generated-results tree is
# writable by the judge UID.  The official wrapper shadows this directory with its
# persistent read/write results bind mount.
RUN useradd -m -u 10001 judge \
    && mkdir -p /work/lean-kernel-challenge/results \
    && chown -R judge:judge /work/lean-kernel-challenge/results
USER judge

# Verify the runtime user's PATH reaches the packaged binary, not the Ubuntu
# host-kernel dispatcher. This is a launch check, not PMU host acceptance.
RUN test "$(command -v perf)" = /usr/local/bin/perf && perf --version

# Exercise the complete pinned bundle read/copy path with the runtime UID.
# A root-only build gate cannot detect inaccessible dependency directories.
RUN for problem in fib mertens primecount; do \
      python3 -c 'import sys, tempfile; from pathlib import Path; sys.path.insert(0, "scripts"); from problem_dependencies import stage_problem_dependencies; work = tempfile.TemporaryDirectory(); result = stage_problem_dependencies(Path("evaluation/problems") / sys.argv[1], Path(work.name)); print("non-root dependency staging:", sys.argv[1], result.artifact_count, "verified artifacts"); work.cleanup()' "$problem" || exit 1; \
    done

# The supported host entry point is scripts/run_isolated.sh.  CMD remains a shell
# solely for image diagnostics; it is not an evaluation command.
CMD ["/bin/bash"]
