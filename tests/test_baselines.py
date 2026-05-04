from fractions import Fraction
from lxml import etree
from pathlib import Path
import shutil

#from responsio_accentuum import one_t_lyric, one_t_prose, _make_lyric_baseline
from responsio_accentuum.baseline import one_t_lyric, one_t_prose, _make_lyric_baseline


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


def test_one_t():
    
    (T_pos_prose_test, T_song_prose_test) = one_t_prose(odes=smoke_test_odes, responsion_type_folder=FOLDERS["strophes"])
    (T_pos_lyric_test, T_song_lyric_test) = one_t_lyric(odes=smoke_test_odes, responsion_type_folder=FOLDERS["strophes"])

    assert isinstance(T_pos_prose_test, Fraction)
    assert isinstance(T_song_prose_test, Fraction)
    assert isinstance(T_pos_lyric_test, Fraction)
    assert isinstance(T_song_lyric_test, Fraction)


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
