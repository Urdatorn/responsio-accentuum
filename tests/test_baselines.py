from fractions import Fraction
from lxml import etree
from pathlib import Path
import shutil

#from responsio_accentuum import one_t_lyric, one_t_prose, _make_lyric_baseline
from responsio_accentuum.baseline import (
    one_t_lyric,
    one_t_prose,
    _make_lyric_baseline,
    lyric_line_sample_cached,
    get_test_statistics_cache_dir,
)


def find_project_root(start: Path, markers=("pyproject.toml", ".git")):
    for p in [start] + list(start.parents):
        if any((p / m).exists() for m in markers):
            return p
    raise RuntimeError("Project root not found")

ROOT = find_project_root(Path.cwd())

FOLDERS = {
    "triads": ROOT / "data" / "compiled" / "triads",
    "strophes": ROOT / "data" / "compiled" / "strophes"
}


def collect_ids(folder: Path) -> set[str]:
    ids: set[str] = set()
    for xml_path in folder.glob("*.xml"):
        try:
            tree = etree.parse(xml_path)
            for elem in tree.iter():
                resp_id = elem.attrib.get("responsion")
                if resp_id:
                    ids.add(resp_id)
        except Exception as exc:
            print(f"Warning: failed to parse {xml_path}: {exc}")
    return ids


results: dict[str, set[str]] = {}
for name, folder in FOLDERS.items():
    ids = collect_ids(folder)
    results[name] = ids

tri = results["triads"]
stro = results["strophes"]

fully_triadic_odes = (tri & stro)   # odes that are in both responsion type folders
smoke_test_odes = {sorted(fully_triadic_odes)[0]}


def cached_line(responsion_id: str, file: str, canticum_idx: int, strophe_idx: int, line_idx: int) -> dict:
    return {
        "xml": '<l><syll weight="heavy">τα</syll><syll weight="light">δε</syll></l>',
        "file": file,
        "canticum_idx": canticum_idx,
        "strophe_idx": strophe_idx,
        "line_idx": line_idx,
        "responsion_id": responsion_id,
    }


def tiny_cached_corpus(lines: list[dict]) -> dict:
    return {
        "lines_by_length": {2: lines},
        "all_syllables": [],
        "syllables_by_file": {},
        "syllables_by_responsion": {},
    }


def test_one_t():
    
    (T_pos_prose_test, T_song_prose_test) = one_t_prose(odes=smoke_test_odes, responsion_type_folder=FOLDERS["strophes"])
    (T_pos_lyric_test, T_song_lyric_test) = one_t_lyric(odes=smoke_test_odes, responsion_type_folder=FOLDERS["strophes"])

    assert isinstance(T_pos_prose_test, Fraction)
    assert isinstance(T_song_prose_test, Fraction)
    assert isinstance(T_pos_lyric_test, Fraction)
    assert isinstance(T_song_lyric_test, Fraction)


def test_test_statistics_cache_dir_depends_on_responsion_type_folder():
    """
    Expected-statistics chunk caches are separated by the responsion type being
    mirrored, so triadic and strophic runs cannot accidentally reuse each
    other's chunk files.
    """
    assert get_test_statistics_cache_dir(FOLDERS["triads"]).name == "test_statistics_chunks_triads"
    assert get_test_statistics_cache_dir(FOLDERS["strophes"]).name == "test_statistics_chunks_strophes"


def test_lyric_sampling_excludes_target_responsion_not_whole_file():
    """
    File-contamination prevention is responsion-level for anthology XMLs:
    an is01 baseline must not sample is01 lines, but it may sample is02 lines
    even when both odes are stored in the same source XML file.
    """
    corpus = tiny_cached_corpus([
        cached_line("is01", "ht_isthmians_strophes.xml", 0, 0, 0),
        cached_line("is02", "ht_isthmians_strophes.xml", 0, 0, 1),
    ])

    line = lyric_line_sample_cached(2, corpus, seed=1453, exclude_responsion_id="is01")

    assert line is not None
    assert line.get("source").startswith("is02,")


def test_lyric_sampling_excludes_used_metrical_position():
    """
    Metrical-position independence means a baseline sample cannot reuse the
    same exact (file, canticum_idx, strophe_idx, line_idx), even if another
    candidate with the same length is available from the same responsion.
    """
    used_position = ("ht_olympians_strophes.xml", 0, 0, 0)
    corpus = tiny_cached_corpus([
        cached_line("ol02", *used_position),
        cached_line("ol02", "ht_olympians_strophes.xml", 0, 0, 1),
    ])

    line = lyric_line_sample_cached(2, corpus, seed=1453, used_metrical_positions={used_position})

    assert line is not None
    assert line.get("source") == "ol02, strophe 1, line 2"


def test_lyric_sampling_excludes_used_responsion_per_line_position():
    """
    Responsion independence per line position means that, while filling one
    relative line position across strophes, the sampler cannot draw twice from
    the same responsion_id; it must choose a different ode when one exists.
    """
    corpus = tiny_cached_corpus([
        cached_line("ol10", "ht_olympians_strophes.xml", 0, 0, 0),
        cached_line("ol11", "ht_olympians_strophes.xml", 0, 0, 1),
    ])

    line = lyric_line_sample_cached(2, corpus, seed=1453, used_responsions_this_position={"ol10"})

    assert line is not None
    assert line.get("source").startswith("ol11,")


def test_lyric_baseline_no_duplicates():
    responsion_id = sorted(fully_triadic_odes)[0]
    prefix_to_xml = {
        "ol": FOLDERS["strophes"] / "ht_olympians_strophes.xml",
        "py": FOLDERS["strophes"] / "ht_pythians_strophes.xml",
        "ne": FOLDERS["strophes"] / "ht_nemeans_strophes.xml",
        "is": FOLDERS["strophes"] / "ht_isthmians_strophes.xml",
    }
    xml_file = prefix_to_xml[responsion_id[:2]]
    outfolder = ROOT / "tmp_stats" / "lyric_test"

    try:
        _make_lyric_baseline(
            xml_file,
            responsion_id,
            corpus_folder=FOLDERS["strophes"],
            outfolder=outfolder,
            randomizations=1,
            seed_base=1453,
        )

        outfile = outfolder / f"baseline_lyric_{responsion_id}.xml"
        tree = etree.parse(str(outfile))
        root = tree.getroot()
        strophes = root.findall(f".//strophe[@responsion='{responsion_id}_000']")
        assert strophes

        line_count = len(strophes[0].findall("l"))
        for line_idx in range(line_count):
            line_texts = []
            for strophe in strophes:
                line = strophe.findall("l")[line_idx]
                line_texts.append(etree.tostring(line, encoding="unicode", method="xml"))
            assert len(line_texts) == len(set(line_texts))
    finally:
        shutil.rmtree(outfolder, ignore_errors=True)
