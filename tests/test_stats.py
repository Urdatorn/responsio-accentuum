from pathlib import Path

from responsio_accentuum import accentual_responsion_metric_canticum


def test_orth_example_two_strophes():
    '''
    Counted example from my paper "Hidden Choral Stimuli".
    The text is seven lines from the beginning and end of the parodos of Nubes.
    '''
    
    repo_root = Path(__file__).resolve().parents[1]
    folder_path = repo_root / "data/compiled/extra/test/test_nu01.xml"

    score_dict = accentual_responsion_metric_canticum(folder_path, "nu01")

    score = score_dict["acute_circumflex"]

    expected_score = float((2*6)/41)

    assert score == expected_score


def test_orth_ach01_two_strophes():
    '''
    The first polystrophic song of the Acharnians
    manually checked.
    '''
    
    repo_root = Path(__file__).resolve().parents[1]
    folder_path = repo_root / "data/compiled/extra/test/test_ach.xml"

    score_dict = accentual_responsion_metric_canticum(folder_path, "ach01")

    score = score_dict["acute_circumflex"] # 0.5454545454545454

    expected_score = float(26/94) # (18 acutes + 8 circumflexes)/(62 total acutes + 32 total circumflexes) = 26/94 = 0.2765957446808511

    assert score == expected_score


def test_orth_mockup_polystrophic():
    '''
    An artificial mockup 4-strophic song 
    with a single responding syll 'χλαῖ' in each strophe.
    Total 43 acutes and 30 circumflexes so expected score is (4 * 1)/73 = 0.0547945205479452
    '''
    
    repo_root = Path(__file__).resolve().parents[1]
    folder_path = repo_root / "data/compiled/extra/test/mockup_polystrophic.xml"

    score_dict = accentual_responsion_metric_canticum(folder_path, "test01")

    score = score_dict["acute_circumflex"] # 0.0547945205479452

    expected_score = float(4/73)

    assert score == expected_score