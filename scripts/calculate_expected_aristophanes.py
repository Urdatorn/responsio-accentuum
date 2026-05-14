"""
Calculate Aristophanes baseline expected statistics with multiprocessing.

This is the script version of the expected-statistic cells in
nb/aristophanes_baselines.ipynb. It uses the triadic strophicity distribution
from Pindar, reads the pre-generated Aristophanes permutation XML files, and
saves the resulting statistics to data/cache/aristophanes_bl_statistics.pkl.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import os
from pathlib import Path
import pickle
import time
from collections import defaultdict

from lxml import etree
from tqdm import tqdm

os.environ.setdefault("MPLCONFIGDIR", "/tmp/responsio-accentuum-matplotlib")

from responsio_accentuum import compatibility_play, get_strophicity


def find_project_root(start: Path, markers=("pyproject.toml", ".git")):
    for p in [start] + list(start.parents):
        if any((p / m).exists() for m in markers):
            return p
    raise RuntimeError("Project root not found")


ROOT = find_project_root(Path.cwd())
TEMP_DIR = ROOT / "data" / "compiled" / "baselines" / "baseline_aristophanes" / "temp_permutations"
OUTPUT_PATH = ROOT / "data" / "cache" / "aristophanes_bl_statistics.pkl"

FOLDERS = {
    "triads": ROOT / "data" / "compiled" / "triads",
    "strophes": ROOT / "data" / "compiled" / "strophes",
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


def get_fully_triadic_odes() -> set[str]:
    tri = collect_ids(FOLDERS["triads"])
    stro = collect_ids(FOLDERS["strophes"])
    return tri & stro


def get_strophicity_counts() -> dict[int, int]:
    fully_triadic_odes = get_fully_triadic_odes()
    responsion_counts = get_strophicity(responsion_type="triadic-simple")
    responsion_counts = {
        rid: count for rid, count in responsion_counts.items() if rid in fully_triadic_odes
    }

    strophicity_counts = defaultdict(int)
    for strophicity in responsion_counts.values():
        strophicity_counts[strophicity] += 1
    return dict(strophicity_counts)


def flatten_ratios(xs):
    for x in xs:
        if isinstance(x, list):
            yield from flatten_ratios(x)
        else:
            yield x


@lru_cache(maxsize=None)
def baseline_sum_count(path: Path):
    try:
        if not path.exists():
            raise FileNotFoundError(path)
        if path.stat().st_size == 0:
            raise ValueError("file is empty")
        flat = list(flatten_ratios(compatibility_play(path)))
        if not flat:
            raise ValueError("no compatibility ratios found")
        return sum(flat), len(flat)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to process permutation XML {path}: {type(exc).__name__}: {exc}"
        ) from None


def calculate_one_task(task):
    flavour, n, strophicity_counts_items, expected_pool_size = task

    total = 0
    total_count = 0
    by_song_statistics = []

    for strophicity, count in strophicity_counts_items:
        start = (n - 1) * count + 1
        for m in range(start, start + count):
            path = TEMP_DIR / f"{flavour}_{strophicity}" / f"{flavour}_{strophicity}_perm_{m:05d}.xml"
            subtotal, subtotal_count = baseline_sum_count(path)
            total += subtotal
            total_count += subtotal_count
            by_song_statistics.append(subtotal / subtotal_count)

    if len(by_song_statistics) != expected_pool_size:
        raise ValueError(
            f"Expected {expected_pool_size} baselines in pool for {flavour} n={n}, "
            f"but got {len(by_song_statistics)}"
        )

    return flavour, n, total / total_count, by_song_statistics


def validate_permutation_files(strophicity_counts: dict[int, int], randomizations: int):
    missing = []
    empty = []
    for flavour in ("tetrameter", "trimeter"):
        for strophicity, count in sorted(strophicity_counts.items()):
            required = randomizations * count
            directory = TEMP_DIR / f"{flavour}_{strophicity}"
            if not directory.exists():
                missing.append(str(directory))
                continue
            for i in range(1, required + 1):
                path = directory / f"{flavour}_{strophicity}_perm_{i:05d}.xml"
                if not path.exists():
                    missing.append(str(path))
                elif path.stat().st_size == 0:
                    empty.append(str(path))

    problems = []
    if missing:
        preview = "\n".join(f"  - {path}" for path in missing[:20])
        more = "" if len(missing) <= 20 else f"\n  ... and {len(missing) - 20} more"
        problems.append(f"Missing required permutation files:\n{preview}{more}")
    if empty:
        preview = "\n".join(f"  - {path}" for path in empty[:20])
        more = "" if len(empty) <= 20 else f"\n  ... and {len(empty) - 20} more"
        problems.append(f"Empty permutation files:\n{preview}{more}")
    if problems:
        raise FileNotFoundError("\n\n".join(problems))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Calculate Aristophanes expected baseline statistics with multiprocessing."
    )
    parser.add_argument("--randomizations", type=int, default=10_000)
    parser.add_argument("--workers", type=int, default=7)
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument(
        "--skip-file-check",
        action="store_true",
        help="Skip the preflight check that all required permutation files exist and are non-empty.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    t0 = time.time()

    strophicity_counts = get_strophicity_counts()
    strophicity_counts_items = tuple(sorted(strophicity_counts.items()))
    expected_pool_size = sum(strophicity_counts.values())

    print(f"Project root: {ROOT}")
    print(f"Permutation directory: {TEMP_DIR}")
    print(f"Strophicity counts: {dict(strophicity_counts_items)}")
    print(f"Expected baselines per statistic: {expected_pool_size}")
    print(f"Randomizations: {args.randomizations}")
    print(f"Workers: {args.workers}")
    print()

    if not args.skip_file_check:
        validate_permutation_files(strophicity_counts, args.randomizations)

    tasks = [
        (flavour, n, strophicity_counts_items, expected_pool_size)
        for flavour in ("tetrameter", "trimeter")
        for n in range(1, args.randomizations + 1)
    ]

    expected_statistics_tetrameter_by_position = {}
    expected_statistics_trimeter_by_position = {}
    expected_statistics_tetrameter_by_song = {}
    expected_statistics_trimeter_by_song = {}

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        results = executor.map(calculate_one_task, tasks, chunksize=args.chunk_size)
        for flavour, n, by_position, by_song in tqdm(results, total=len(tasks)):
            if flavour == "tetrameter":
                expected_statistics_tetrameter_by_position[n] = by_position
                expected_statistics_tetrameter_by_song[n] = by_song
            elif flavour == "trimeter":
                expected_statistics_trimeter_by_position[n] = by_position
                expected_statistics_trimeter_by_song[n] = by_song
            else:
                raise ValueError(f"Unexpected flavour: {flavour}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as f:
        pickle.dump(
            {
                "tetrameter_by_position": expected_statistics_tetrameter_by_position,
                "trimeter_by_position": expected_statistics_trimeter_by_position,
                "tetrameter_by_song": expected_statistics_tetrameter_by_song,
                "trimeter_by_song": expected_statistics_trimeter_by_song,
            },
            f,
        )

    t1 = time.time()
    print()
    print(f"Saved Aristophanes expected statistics to {args.output}")
    print(f"Completed in {t1 - t0:.2f} seconds with {args.workers} workers.")
    print(
        "Tetrameter mean by position: "
        f"{sum(expected_statistics_tetrameter_by_position.values()) / len(expected_statistics_tetrameter_by_position):.4f}"
    )
    print(
        "Trimeter mean by position: "
        f"{sum(expected_statistics_trimeter_by_position.values()) / len(expected_statistics_trimeter_by_position):.4f}"
    )


if __name__ == "__main__":
    main()
