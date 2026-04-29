from pathlib import Path

from responsio_accentuum import barys_oxys_metric_corpus


def test_barys_corpus_two_strophes():
    repo_root = Path(__file__).resolve().parents[1]
    folder_path = repo_root / "data/compiled/extra/test_corpus"

    corpus_dict = barys_oxys_metric_corpus(folder_path)

    score = corpus_dict["barys_metric"] # 0.5454545454545454

    expected_score = 0.5454545454545454

    assert score == expected_score
