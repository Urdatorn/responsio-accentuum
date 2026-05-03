'''
Calculate all test statistics with multiprocessing.

The shape of each permuted baseline corpus is modelled after the 33 fully triadic odes, 
so that the expected test statistics can be compared both with triadic-strophic and strophic-antistrophic observed corpora.
'''

from lxml import etree
from pathlib import Path
import pickle
import time

from responsio_accentuum import expected_statistics


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


# ========================
# CONFIGURATION VARIABLES 
# ========================

odes = fully_triadic_odes
randomizations = 10000
workers = 12
chunk_size = 100

if __name__ == "__main__":
    t0 = time.time()
    T_exp_pos_prose_list, T_exp_song_prose_list, T_exp_pos_lyric_list, T_exp_song_lyric_list, lyric_stats_summary = expected_statistics(
        odes=odes,
        randomizations=randomizations,
        workers=workers,
        chunk_size=chunk_size,
        include_lyric_stats=True,
        use_cache=True
    )
    t1 = time.time()
    print(f"Expected statistics calculated in {t1 - t0:.2f} seconds with {workers} workers and chunk size {chunk_size}.")
    
    print("\nFirst sample in each test statistic series:\n")
    print(f"T_pos_prose_list: \033[1;32m{T_exp_pos_prose_list[0]:.3f}\033[0m")
    print(f"T_song_prose_list: \033[1;32m{T_exp_song_prose_list[0]:.3f}\033[0m")
    print(f"T_pos_lyric_list: \033[1;32m{T_exp_pos_lyric_list[0]:.3f}\033[0m")
    print(f"T_song_lyric_list: \033[1;32m{T_exp_song_lyric_list[0]:.3f}\033[0m")

    if lyric_stats_summary:
        print("\nLyric baseline composition (aggregated):")
        for k, v in lyric_stats_summary.items():
            print(f"  {k}: {v}")

    pickle_output = ROOT / "data/cache/test_statistics.pkl"
    with open(pickle_output, "wb") as f:
        pickle.dump((T_exp_pos_prose_list, T_exp_song_prose_list, T_exp_pos_lyric_list, T_exp_song_lyric_list, lyric_stats_summary), f)

    