from pathlib import Path

from responsio_accentuum import compatibility_canticum, flatten_recursive


def test_compatibility_canticum_nu01_regression_normalized_scores():
    repo_root = Path(__file__).resolve().parents[1]
    xml_path = repo_root / "data/compiled/extra/test_nu01.xml"

    fractions = compatibility_canticum(xml_path, "nu01")
    normalized_scores = [int(value) for value in flatten_recursive(fractions)]

    expected_scores = [
        1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 0, 0, 1,
        1, 0, 0, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 0, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1,
    ]

    assert normalized_scores == expected_scores
