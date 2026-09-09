#!/usr/bin/env python3
"""Machine-check the public scoring contract in rules/problem-scoring.md.

rules/problem-scoring.md declares its per-problem tables to be the public
scoring contract. The same facts live in problems/<p>/config.json under the
"evaluation" key. These tests parse the hand-maintained markdown tables and
assert every row against the authoritative configs so the two copies cannot
silently drift apart.

A second TestCase asserts that every copy of the Lean toolchain pin in the
repository is identical.
"""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCORING_DOC = ROOT / "rules" / "problem-scoring.md"
PROBLEMS_DIR = ROOT / "problems"

# The sampler each problem's doc section declares in prose. Keys double as
# the closed list of scored Stage 1 problems (conv is explicitly excluded).
DOC_SAMPLER_KINDS = {
    "fib": "geometric_range",
    "partition": "geometric_range",
    "mertens": "geometric_range",
    "primecount": "geometric_range",
    "permanent": "packed",
    "saw": "packed",
    "ca-rule110": "packed",
    "sha256": "packed",
    "polydisc": "uniform_int",
}

EXPECTED_GROUP_COUNT = 3
EXPECTED_PROBLEM_COUNT = 9
EXPECTED_TOTAL_POINTS = 100

_SECTION_RE = re.compile(r"^## `([^`]+)`", re.MULTILINE)
_SEPARATOR_CELL_RE = re.compile(r":?-{3,}:?")
_LIMIT_RE = re.compile(r"^([\d,]+)\s*s$")
_POW2_RE = re.compile(r"^2\^(\d+)$")


def _parse_scalar(text):
    """Parse an integer cell: '1,200,000' or a power of two like '2^57'."""
    text = text.replace(",", "").strip()
    match = _POW2_RE.match(text)
    if match:
        return 2 ** int(match.group(1))
    return int(text)


def _parse_range(text):
    """Parse a 'lo-hi' cell (the doc uses an en dash) into (lo, hi)."""
    for dash in ("–", "-"):
        if dash in text:
            lo, hi = text.split(dash, 1)
            return _parse_scalar(lo), _parse_scalar(hi)
    raise ValueError("not a range cell: %r" % text)


def _parse_doc_sections(text):
    """Split the doc on '## `name`' headings; return {name: section_text}."""
    matches = list(_SECTION_RE.finditer(text))
    sections = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def _parse_table(section_text):
    """Extract the first markdown table; return (header_cells, row_cells)."""
    header = None
    rows = []
    for line in section_text.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            if header is not None and rows:
                break  # table ended
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells):
            continue
        if header is None:
            header = cells
        else:
            rows.append(cells)
    return header, rows


def _doc_row(problem, header, cells):
    """Normalize one table row into a comparable dict.

    Column layout (all nine tables): group id first, the scale/range second,
    the per-repetition limit last. The case count is explicit in the
    'Cases' or 'Hidden seeds' column.
    """
    named = dict(zip(header, cells))
    kind = DOC_SAMPLER_KINDS[problem]

    row = {"group": cells[0], "kind": kind}
    if kind == "packed":
        row["scale"] = _parse_scalar(cells[1])
    else:
        row["min"], row["max"] = _parse_range(cells[1])

    count_cell = named.get("Cases", named.get("Hidden seeds"))
    row["count"] = int(count_cell) if count_cell is not None else None

    limit_match = _LIMIT_RE.match(cells[-1])
    if limit_match is None:
        raise ValueError(
            "%s row %s: unparseable limit cell %r" % (problem, cells[0], cells[-1])
        )
    row["timeout_seconds"] = int(limit_match.group(1).replace(",", ""))
    return row


def _load_doc_rows():
    """Parse the scoring doc into {problem: [normalized row dicts]}."""
    sections = _parse_doc_sections(SCORING_DOC.read_text(encoding="utf-8"))
    doc = {}
    for problem, section in sections.items():
        header, rows = _parse_table(section)
        if header is None:
            continue  # heading without a table is not a problem section
        doc[problem] = [_doc_row(problem, header, cells) for cells in rows]
    return doc


def _load_config_evaluations():
    """Load {problem: evaluation dict} for every config declaring one."""
    evaluations = {}
    for config_path in sorted(PROBLEMS_DIR.glob("*/config.json")):
        with open(str(config_path), "r", encoding="utf-8") as handle:
            config = json.load(handle)
        if "evaluation" in config:
            evaluations[config_path.parent.name] = config["evaluation"]
    return evaluations


class TestScoringContractDocs(unittest.TestCase):
    """rules/problem-scoring.md tables must match problems/*/config.json."""

    @classmethod
    def setUpClass(cls):
        cls.doc = _load_doc_rows()
        cls.configs = _load_config_evaluations()

    def _pairs(self):
        """Yield (problem, doc_row, config_group) for every aligned group."""
        for problem in sorted(DOC_SAMPLER_KINDS):
            doc_rows = self.doc[problem]
            config_groups = self.configs[problem]["groups"]
            self.assertEqual(
                len(doc_rows),
                len(config_groups),
                "%s: doc has %d table rows but config has %d groups"
                % (problem, len(doc_rows), len(config_groups)),
            )
            for doc_row, config_group in zip(doc_rows, config_groups):
                yield problem, doc_row, config_group

    def test_doc_lists_exactly_nine_problems_with_three_groups_each(self):
        self.assertEqual(
            sorted(self.doc),
            sorted(DOC_SAMPLER_KINDS),
            "doc problem sections do not match the expected nine problems",
        )
        self.assertEqual(len(self.doc), EXPECTED_PROBLEM_COUNT)
        for problem, rows in sorted(self.doc.items()):
            self.assertEqual(
                len(rows),
                EXPECTED_GROUP_COUNT,
                "doc table for %s has %d rows, expected %d"
                % (problem, len(rows), EXPECTED_GROUP_COUNT),
            )

    def test_configs_list_exactly_nine_problems_with_three_groups_each(self):
        self.assertEqual(
            sorted(self.configs),
            sorted(DOC_SAMPLER_KINDS),
            "configs with an 'evaluation' key do not match the expected nine "
            "problems",
        )
        self.assertEqual(len(self.configs), EXPECTED_PROBLEM_COUNT)
        for problem, evaluation in sorted(self.configs.items()):
            self.assertEqual(
                len(evaluation["groups"]),
                EXPECTED_GROUP_COUNT,
                "config for %s has %d groups, expected %d"
                % (problem, len(evaluation["groups"]), EXPECTED_GROUP_COUNT),
            )

    def test_group_ids_and_order_match(self):
        for problem, doc_row, group in self._pairs():
            with self.subTest(problem=problem, group=doc_row["group"]):
                self.assertEqual(
                    doc_row["group"],
                    group["id"],
                    "%s: doc row %s aligned with config group %s"
                    % (problem, doc_row["group"], group["id"]),
                )
        for problem in sorted(DOC_SAMPLER_KINDS):
            orders = [g["order"] for g in self.configs[problem]["groups"]]
            self.assertEqual(
                orders,
                list(range(1, EXPECTED_GROUP_COUNT + 1)),
                "%s: config group 'order' fields are not 1..%d in sequence"
                % (problem, EXPECTED_GROUP_COUNT),
            )

    def test_sampling_matches(self):
        for problem, doc_row, group in self._pairs():
            sampling = group["sampling"]
            with self.subTest(problem=problem, group=group["id"]):
                self.assertEqual(
                    doc_row["kind"],
                    sampling["kind"],
                    "%s %s: doc declares sampler %s, config uses %s"
                    % (problem, group["id"], doc_row["kind"], sampling["kind"]),
                )
                if doc_row["kind"] == "packed":
                    self.assertEqual(
                        doc_row["scale"],
                        sampling["scale"],
                        "%s %s field 'scale': doc says %d, config says %d"
                        % (problem, group["id"], doc_row["scale"], sampling["scale"]),
                    )
                    self.assertEqual(
                        sampling["seed_bits"],
                        32,
                        "%s %s field 'seed_bits': doc prose promises 32-bit "
                        "instance seeds, config says %r"
                        % (problem, group["id"], sampling.get("seed_bits")),
                    )
                else:
                    for bound in ("min", "max"):
                        self.assertEqual(
                            doc_row[bound],
                            sampling[bound],
                            "%s %s field '%s': doc says %d, config says %d"
                            % (
                                problem,
                                group["id"],
                                bound,
                                doc_row[bound],
                                sampling[bound],
                            ),
                        )
                if doc_row["kind"] == "geometric_range":
                    self.assertEqual(
                        sampling["jitter"],
                        0.15,
                        "%s %s field 'jitter': doc prose promises 15%% jitter, "
                        "config says %r"
                        % (problem, group["id"], sampling.get("jitter")),
                    )

    def test_case_counts_match(self):
        for problem, doc_row, group in self._pairs():
            with self.subTest(problem=problem, group=group["id"]):
                config_count = group["sampling"]["count"]
                if doc_row["count"] is not None:
                    self.assertEqual(
                        doc_row["count"],
                        config_count,
                        "%s %s field 'count': doc says %d, config says %d"
                        % (problem, group["id"], doc_row["count"], config_count),
                    )
                self.assertIsNotNone(doc_row["count"])

    def test_groups_have_no_partial_awards_or_prerequisites(self):
        for problem, evaluation in self.configs.items():
            with self.subTest(problem=problem):
                self.assertEqual(evaluation["ranking"]["contract"], "full-plan-v1")
                self.assertNotIn("profile", evaluation["ranking"])
                for group in evaluation["groups"]:
                    self.assertNotIn("award", group)
                    self.assertNotIn("requires", group)

    def test_watchdog_timeouts_match(self):
        for problem, doc_row, group in self._pairs():
            with self.subTest(problem=problem, group=group["id"]):
                self.assertEqual(
                    doc_row["timeout_seconds"],
                    group["limits"]["timeout_seconds"],
                    "%s %s field 'timeout_seconds': doc says %d s, config "
                    "says %d s"
                    % (
                        problem,
                        group["id"],
                        doc_row["timeout_seconds"],
                        group["limits"]["timeout_seconds"],
                    ),
                )

    def test_total_points_are_100(self):
        for problem, evaluation in self.configs.items():
            with self.subTest(problem=problem):
                self.assertEqual(evaluation["ranking"]["max_points"], EXPECTED_TOTAL_POINTS)


class TestLeanToolchainConsistency(unittest.TestCase):
    """Every copy of the Lean toolchain pin must be identical."""

    def test_all_toolchain_copies_identical(self):
        copies = {}

        copies["lean-toolchain"] = (
            (ROOT / "lean-toolchain").read_text(encoding="utf-8").strip()
        )
        copies["judge/timer-kernel/lean-toolchain"] = (
            (ROOT / "judge" / "timer-kernel" / "lean-toolchain")
            .read_text(encoding="utf-8")
            .strip()
        )

        problem_toolchains = sorted(PROBLEMS_DIR.glob("*/lean-toolchain"))
        self.assertTrue(
            problem_toolchains, "no problems/*/lean-toolchain files found"
        )
        for path in problem_toolchains:
            rel = path.relative_to(ROOT).as_posix()
            copies[rel] = path.read_text(encoding="utf-8").strip()

        with open(str(ROOT / "pipeline" / "config.json"), "r", encoding="utf-8") as f:
            pipeline_config = json.load(f)
        copies["pipeline/config.json toolchain.lean"] = pipeline_config[
            "toolchain"
        ]["lean"]

        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        match = re.search(
            r"^ARG\s+LEAN_TOOLCHAIN=(\S+)\s*$", dockerfile, re.MULTILINE
        )
        self.assertIsNotNone(
            match, "Dockerfile has no 'ARG LEAN_TOOLCHAIN=' default"
        )
        copies["Dockerfile ARG LEAN_TOOLCHAIN"] = match.group(1)

        reference = copies["lean-toolchain"]
        self.assertTrue(reference, "root lean-toolchain is empty")
        mismatched = {
            name: value for name, value in copies.items() if value != reference
        }
        self.assertEqual(
            mismatched,
            {},
            "toolchain copies differ from root lean-toolchain (%s): %r"
            % (reference, mismatched),
        )


if __name__ == "__main__":
    unittest.main()
