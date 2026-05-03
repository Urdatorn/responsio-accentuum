from fractions import Fraction
from lxml import etree
from pathlib import Path

from responsio_accentuum import one_t_lyric, one_t_prose, _make_lyric_baseline


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


def test_one_t():
    
    (T_pos_prose_test, T_song_prose_test) = one_t_prose(odes=fully_triadic_odes)
    (T_pos_lyric_test, T_song_lyric_test) = one_t_lyric(odes=fully_triadic_odes)

    assert isinstance(T_pos_prose_test, Fraction)
    assert isinstance(T_song_prose_test, Fraction)
    assert isinstance(T_pos_lyric_test, Fraction)
    assert isinstance(T_song_lyric_test, Fraction)