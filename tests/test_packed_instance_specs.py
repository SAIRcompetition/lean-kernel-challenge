#!/usr/bin/env python3
"""Known-answer checks for the packed, seed-specific Lean specs and polydisc.

The reference functions below intentionally do not import judge or duplicate
Lean output files.  They implement the public generators in Python, while the
test asks Lean to evaluate the trusted `Spec` modules on the same small inputs.
Frozen answers make an accidental matching change on both sides visible.
"""

import hashlib
import importlib.util
import itertools
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from problem_layout import evaluation_problem_dir

MASK32 = (1 << 32) - 1


def packed(scale, seed):
    return (scale << 32) | seed


def mix32(value):
    value = ((value ^ (value >> 16)) * 0x7FEB352D) & MASK32
    value = ((value ^ (value >> 15)) * 0x846CA68B) & MASK32
    return (value ^ (value >> 16)) & MASK32


def permanent_matrix_reference(dimension, seed):
    def skip_one(excluded, index):
        return index if index < excluded else index + 1

    def skip_two(a, b, index):
        lo, hi = sorted((a, b))
        value = index if index < lo else index + 1
        return value if value < hi else value + 1

    def entry(i, j):
        if dimension < 3:
            return 1
        row_key = seed ^ (i * 0x9E3779B9)
        first = skip_one(i, mix32(row_key ^ 0x85EBCA6B) % (dimension - 1))
        second = skip_two(
            i, first, mix32(row_key ^ 0xC2B2AE35) % (dimension - 2)
        )
        return int(j in (i, first, second))

    return [
        [entry(i, j) for j in range(dimension)]
        for i in range(dimension)
    ]


def permanent_reference(dimension, seed):
    matrix = permanent_matrix_reference(dimension, seed)
    return sum(
        all(matrix[i][permutation[i]] for i in range(dimension))
        for permutation in itertools.permutations(range(dimension))
    )


def _encode_int(value):
    return 2 * abs(value) - 1 if value < 0 else 2 * value


def saw_reference(length, seed):
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def blocked(point):
        x, y = point
        if y == 0 and x >= 0:
            return False
        mixed = (
            seed
            ^ (_encode_int(x) * 0x9E3779B9)
            ^ (_encode_int(y) * 0x85EBCA6B)
            ^ 0xC2B2AE35
        )
        return mix32(mixed) % 11 == 0

    def count(steps, point, visited):
        if steps == 0:
            return 1
        total = 0
        for dx, dy in directions:
            next_point = (point[0] + dx, point[1] + dy)
            if next_point in visited or blocked(next_point):
                continue
            visited.add(next_point)
            total += count(steps - 1, next_point, visited)
            visited.remove(next_point)
        return total

    return count(length, (0, 0), {(0, 0)})


def ca_reference(steps, seed):
    row = [
        True if i == 0 else
        False if i == 1 else
        bool((mix32(seed + (i + 1) * 0x9E3779B9) >> 31) & 1)
        for i in range(256)
    ]

    def rule110(left, center, right):
        return (left, center, right) not in {
            (True, True, True),
            (True, False, False),
            (False, False, False),
        }

    for _ in range(steps):
        row = [
            rule110(row[(i - 1) % 256], row[i], row[(i + 1) % 256])
            for i in range(256)
        ]
    return sum(int(bit) << i for i, bit in enumerate(row))


def sha256_reference(steps, seed):
    words = []
    state = seed & MASK32
    for _ in range(8):
        state = (1664525 * state + 1013904223) & MASK32
        words.append(state)
    digest = b"".join(word.to_bytes(4, "big") for word in words)
    for _ in range(steps):
        digest = hashlib.sha256(digest).digest()
    return int.from_bytes(digest, "big")


CASES = {
    "permanent": {
        "spec": "permanentSpecN",
        "reference": permanent_reference,
        "vectors": [
            (0, MASK32, 1),
            (1, 0, 1),
            (2, MASK32, 2),
            (3, 1, 6),
            (4, MASK32, 9),
        ],
    },
    "saw": {
        "spec": "sawSpec",
        "reference": saw_reference,
        "vectors": [
            (0, MASK32, 1),
            (1, 0, 4),
            (4, 1, 62),
            (5, MASK32, 162),
        ],
    },
    "ca-rule110": {
        "spec": "caSpecN",
        "reference": ca_reference,
        "vectors": [
            (0, MASK32,
             39182519112023866544536036211526227574914928668350269117402648292207235003753),
            (1, 0,
             28790360432100359675900384225747522345744538390329335443481557656821485535085),
            (3, 1,
             50446023508594522752218378513672912399469115759546551205210818808364694200440),
            (3, MASK32,
             57946779343320518290994834605164800604358144145646316131344707774039196456965),
        ],
    },
    "sha256": {
        "spec": "sha256Spec",
        "reference": sha256_reference,
        "vectors": [
            (0, MASK32,
             27289928277517450473726143143723056889608837264336340939145516705529457565575),
            (1, 0,
             4221607917069570966164243239090007043043907574719640821053522951032627001827),
            (2, 1,
             12951784694840770977245544593908270174466873362802972520527567559343483793530),
            (2, MASK32,
             26532797636208419703597189387299034950736569895671931202685968991573420836534),
        ],
    },
}


# Frozen known answers for `problems/polydisc/Spec.lean` (`discSpec`).  The
# input is a plain seed, not a packed (scale, seed) pair; the six seeds cover
# coefficient-width bands 0-2 with two seeds each, taken from the sampling
# ranges of evaluation groups D1-D3 in `problems/polydisc/config.json`.  The
# expected discriminants were computed with the repository's own Python mirror
# (`scripts/check_polydisc_candidate.py`) plus SymPy, then cross-checked
# against Lean's `discSpec` before freezing.  They are stored as decimal
# strings and compared as strings, so the check is independent of the large
# int-to-str conversion cap introduced in Python 3.11.
POLYDISC_VECTORS = [
    (262144,
     "303470771677018177369005898145299643300756168039600225712837245485675610"
     "833541547159974155910628760906731568524596851222880317456424130550525844"
     "8863391462091221629670401872"),
    (1000000,
     "774450076976763970289981171935720156100320768149556884603860012639247956"
     "998179843714529217570082463678577925226542135066320961613139761299413650"
     "2997168963583488275591760"),
    (33554432,
     "197013343885744768115510819017207977490899712029982582272230983471177382"
     "930036076197648725756511092166112706526382118851509361828945511897665348"
     "29577395859417632849712892"),
    (134217728,
     "281782084634836190461375724093769489386541170871120134232992999404747145"
     "768273915782492720866778022694222351499111290573767786431114775327854045"
     "115968132567215779536916455361038668868633862494334753245352856823762968"
     "077187490604140918987851734261023395530388526978844739863288069191543257"
     "512685767288715612489127818522074552017533236743648296638523182621176401"
     "9462746171857063206955796998079592085505617"),
    (8589934592,
     "-10657192124258122220446968542379213370714136580090626631136935169826761"
     "347555405348785468852188221664779131161541238666189973677147285080105256"
     "448224119124589207300774537449638663426457271410826453637787422374710229"
     "207886388057430555867529798500473902148939748845979575112835402645178415"
     "676587212912752526578126188154830984535023483056184846331508918888695036"
     "671447544225762147603416908877128389009808489704841799"),
    (137438953472,
     "-12658129311832010785654853595940986334136841195745883811214013830751306"
     "786638075428802878854791562775522054895197993247999428978504780973245696"
     "139535055422421809508789978531417105109550575856238156499052676546693241"
     "903621991728304915018435154103173145995360372951132856680863154081238642"
     "508441484702325391075877395011953491666802877623592008670104771999186683"
     "074936172561493060539022215002593415364482318425164568230790526487523864"
     "143843109781153222675567336917274844862928732512487004081305047190010471"
     "907668265252329227867174974195685571552481291995386024000176877298312533"
     "598746300478742948259315566885672618447524073153310618182447074955099003"
     "738172937167644275560339362228213253902599109256279954159848876811544194"
     "229191532763221972963960963138377027051340578446178568414344006687191848"
     "746878472965046275673790980839446867170462449744054694203354835695917611"
     "593830286210403850112901803506128829219129828393504134271205811190441178"
     "070694965229583817821931875826628765763533443310684499130034332189916581"
     "177191661407772144565451743292835895549955152308634572584213269464620522"
     "492577568486446835330599272950505012930582257773039496640521203018565631"
     "810572873727531274745773118388540940655420784397642276155555746700638952"
     "144688864056248995823408551644865376841052778861222137461548385987861433"
     "698114492822344611124763449973273886501994384176069342519485762637627528"
     "908069362441422470363425620035983570038935477519386165283515906557363748"
     "2798903075630841609516571983323"),
]


def load_polydisc_mirror():
    """Load the repository's Python mirror of the polydisc construction.

    The module imports sympy at top level, so callers must gate on sympy
    availability before invoking this helper.
    """
    location = ROOT / "scripts" / "check_polydisc_candidate.py"
    spec = importlib.util.spec_from_file_location(
        "check_polydisc_candidate", location
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lean_values(problem, spec_name, vectors):
    workspace = evaluation_problem_dir(ROOT, problem)
    subprocess.run(
        ["lake", "build", "Spec"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    source = "import Spec\n" + "\n".join(
        f"#eval {spec_name} {packed(scale, seed)}"
        for scale, seed, _ in vectors
    ) + "\n"
    result = subprocess.run(
        ["lake", "env", "lean", "--stdin"],
        cwd=workspace,
        input=source,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    values = [
        int(line)
        for line in result.stdout.splitlines()
        if re.fullmatch(r"[0-9]+", line)
    ]
    if len(values) != len(vectors):
        raise AssertionError(
            f"Lean printed {len(values)} values for {problem}, expected {len(vectors)}; "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        )
    return values


def lean_int_values(problem, spec_name, inputs):
    workspace = evaluation_problem_dir(ROOT, problem)
    subprocess.run(
        ["lake", "build", "Spec"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    source = "import Spec\n" + "\n".join(
        f"#eval {spec_name} {value}" for value in inputs
    ) + "\n"
    result = subprocess.run(
        ["lake", "env", "lean", "--stdin"],
        cwd=workspace,
        input=source,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    values = [
        line
        for line in result.stdout.splitlines()
        if re.fullmatch(r"-?[0-9]+", line)
    ]
    if len(values) != len(inputs):
        raise AssertionError(
            f"Lean printed {len(values)} values for {problem}, expected {len(inputs)}; "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        )
    return values


class PackedInstanceKnownAnswerTests(unittest.TestCase):
    def test_permanent_generator_has_fixed_row_degree_and_diagonal(self):
        for dimension in (3, 4, 8, 12):
            for seed in (0, 1, MASK32, 0x12345678):
                matrix = permanent_matrix_reference(dimension, seed)
                with self.subTest(dimension=dimension, seed=seed):
                    self.assertTrue(all(sum(row) == 3 for row in matrix))
                    self.assertTrue(all(matrix[i][i] == 1 for i in range(dimension)))

    def test_packing_covers_zero_scale_and_seed_boundaries(self):
        for problem, case_set in CASES.items():
            with self.subTest(problem=problem):
                self.assertTrue(any(scale == 0 for scale, _, _ in case_set["vectors"]))
                self.assertTrue(any(seed == 0 for _, seed, _ in case_set["vectors"]))
                self.assertTrue(any(seed == MASK32 for _, seed, _ in case_set["vectors"]))
                for scale, seed, _ in case_set["vectors"]:
                    value = packed(scale, seed)
                    self.assertEqual(value >> 32, scale)
                    self.assertEqual(value & MASK32, seed)

    def test_independent_references_match_frozen_answers(self):
        for problem, case_set in CASES.items():
            reference = case_set["reference"]
            for scale, seed, expected in case_set["vectors"]:
                with self.subTest(problem=problem, scale=scale, seed=seed):
                    self.assertEqual(reference(scale, seed), expected)

    def test_polydisc_frozen_discriminants_are_nonzero(self):
        for n, expected in POLYDISC_VECTORS:
            with self.subTest(n=n):
                self.assertRegex(expected, r"^-?[1-9][0-9]*$")

    @unittest.skipUnless(
        importlib.util.find_spec("sympy") is not None,
        "sympy not on this interpreter (the repository mirror imports it)",
    )
    def test_polydisc_mirror_matches_frozen_answers(self):
        import sympy

        mirror = load_polydisc_mirror()
        x = sympy.symbols("x")
        for n, expected in POLYDISC_VECTORS:
            with self.subTest(n=n):
                coefficients, _, _ = mirror.candidate_polynomial(n)
                polynomial = sympy.Poly.from_list(
                    coefficients, gens=x, domain=sympy.ZZ
                )
                self.assertEqual(str(int(polynomial.discriminant())), expected)

    @unittest.skipUnless(shutil.which("lake"), "lake (Lean toolchain) not on PATH")
    def test_lean_specs_match_independent_references(self):
        for problem, case_set in CASES.items():
            with self.subTest(problem=problem):
                expected = [value for _, _, value in case_set["vectors"]]
                self.assertEqual(
                    lean_values(problem, case_set["spec"], case_set["vectors"]),
                    expected,
                )

    @unittest.skipUnless(shutil.which("lake"), "lake (Lean toolchain) not on PATH")
    def test_polydisc_lean_spec_matches_frozen_answers(self):
        inputs = [n for n, _ in POLYDISC_VECTORS]
        expected = [value for _, value in POLYDISC_VECTORS]
        self.assertEqual(lean_int_values("polydisc", "discSpec", inputs), expected)


if __name__ == "__main__":
    unittest.main()
