#!/usr/bin/env python3

# Copyright © Albin Ruben Johannes Thörn Cleland 2026, Lunds universitet, albin.thorn_cleland@klass.lu.se
# https://orcid.org/0009-0003-3731-4038
# This file is part of responsio-accentuum, licensed under the GNU General Public License v3.0.
# See the LICENSE file in the project root for full details.

'''
Script to prepare both lyric and prose baselines for Pindar's odes. 

LYRIC BASELINE FALLBACK SYSTEM (Configurable):
The lyric baseline generation uses a comprehensive configurable fallback system to find lines 
of the required syllable length, maintaining statistical independence and authenticity.

Current configuration (easily adjustable via variables at top of script):
- PINDAR_MAX_TRIMMING = 10 (trim up to 10 syllables from Pindar corpus lines)
- EXTERNAL_MAX_TRIMMING = 10 (trim up to 10 syllables from external corpus lines)  
- PINDAR_MAX_PADDING = 4 (add up to 4 syllables to Pindar corpus lines)
- EXTERNAL_MAX_PADDING = 4 (add up to 4 syllables to external corpus lines)

FALLBACK SEQUENCE:
1. Exact length match - Find lines with exactly the target syllable count
2-(1+PINDAR_MAX_TRIMMING). Pindar trimming - Remove 1 to PINDAR_MAX_TRIMMING syllables from longer Pindar lines
(2+PINDAR_MAX_TRIMMING). External exact length - Aristophanes corpus exact match
(3+PINDAR_MAX_TRIMMING)-(2+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING). External trimming - Remove 1 to EXTERNAL_MAX_TRIMMING syllables from external lines
(3+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING)-(2+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING+PINDAR_MAX_PADDING). Pindar padding - Add 1 to PINDAR_MAX_PADDING syllables to shorter Pindar lines
(3+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING+PINDAR_MAX_PADDING)-(2+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING+PINDAR_MAX_PADDING+EXTERNAL_MAX_PADDING). External padding - Add 1 to EXTERNAL_MAX_PADDING syllables to shorter external lines
(final). Paired-line fallback - Pair two Pindar lines and trim the first to fit

STATISTICAL INDEPENDENCE CONSTRAINTS:
The system enforces three levels of statistical independence to ensure robust baselines:

1. ODE CONTAMINATION PREVENTION:
   - Lines from the target ode (e.g., is01) are excluded from baseline generation
   - Lines from other odes in the same file are allowed, e.g. is02 can be used in a baseline for is01.
   - Prevents circular dependency where a text is compared against itself

2. METRICAL POSITION INDEPENDENCE:
   - No two lines can come from the exact same metrical position
   - Position defined as: (file, canticum_idx, strophe_idx, line_idx)
   - Ensures no duplicate source material across the entire baseline

3. RESPONSION INDEPENDENCE PER LINE POSITION:
   - Within each baseline sample (e.g., is01_000), the same relative line position 
     across different strophes cannot use the same responsion_id
   - Example: if line 16 (pos 1 of strophe 1) is from ol10, then line 33 (pos 1 of strophe 2) 
     cannot also be from ol10
   - Prevents correlation between strophes within the same baseline sample

SOURCE ATTRIBUTION:
Each generated line includes enhanced source attribution for transparency:
- Pindar lines: source="py11, strophe 2, line 4" (responsion_id, strophe index, relative line index)
- External lines: source="external_aristophanes"
This enables easy verification of independence constraints and contamination prevention.

PERFORMANCE OPTIMIZATION:
- Preprocessed corpus caching for fast repeated access
- Comprehensive fallback system reduces failure rates
- Systematic length progression maximizes success probability
'''

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
from functools import lru_cache
import math
import os
from pathlib import Path
import pickle
import random
import re
import shutil
from statistics import mean

from grc_utils import lower_grc, syllabifier
from lxml import etree
from tqdm import tqdm

from .compile import compile_scan, process_file
from .utils.prose import anabasis
from .utils.utils import canticum_with_at_least_two_strophes
from .scan import rule_scansion
from .stats import canonical_sylls, metrically_responding_lines_polystrophic
from .stats_comp import compatibility_canticum, compatibility_corpus, compatibility_ratios_to_stats

#############
### PATHS ###
#############


def find_project_root(start: Path, markers=("pyproject.toml", ".git")):
    for p in [start] + list(start.parents):
        if any((p / m).exists() for m in markers):
            return p
    raise RuntimeError("Project root not found")


ROOT = find_project_root(Path(__file__))


def resolve_path(path_like):
    """Resolve relative paths against the repository root."""
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


PROSE_CACHE_PATH = ROOT / "data/cache/cached_prose_corpus.pkl"
LYRIC_CACHE_PATH = ROOT / "data/cache/cached_lyric_corpus.pkl"

# =============================================================================
# CONFIGURATION VARIABLES - Adjust these to control fallback system behavior
# =============================================================================

# Trimming configuration (how many syllables to remove from longer lines)
PINDAR_MAX_TRIMMING = 10        # Max syllables to trim from Pindar corpus lines
EXTERNAL_MAX_TRIMMING = 10      # Max syllables to trim from external corpus lines

# Padding configuration (how many syllables to add to shorter lines)  
PINDAR_MAX_PADDING = 4          # Max syllables to add to Pindar corpus lines
EXTERNAL_MAX_PADDING = 4        # Max syllables to add to external corpus lines

# Retry configuration (how many times to re-roll a failed baseline)
BASELINE_MAX_RETRIES = 5        # Max retries for a single baseline before failing
BASELINE_RETRY_SEED_STRIDE = 10_000  # Seed offset stride for retry attempts
LYRIC_POSITION_MAX_RETRIES = 10  # Max retries per line position for metrical response

# =============================================================================


punctuation_except_period = r'[\u0387\u037e\u00b7,!?;:\"()\[\]{}<>«»\-—…|⏑⏓†×]'


def get_test_statistics_cache_dir(responsion_type_folder: Path) -> Path:
    """Return the chunk cache directory for a responsion-type corpus folder."""
    responsion_type_folder = resolve_path(responsion_type_folder)
    return ROOT / f"data/cache/test_statistics_chunks_{responsion_type_folder.name}"


###########################
### TEST STATISTICS API ###
###########################


def expected_statistics(odes: set, responsion_type_folder: Path = ROOT / "data" / "compiled" / "triads", randomizations=10_000, workers: int = 1, chunk_size: int | None = None, include_lyric_stats: bool = False, use_cache: bool = True) -> tuple[list[Fraction], list[Fraction], list[Fraction], list[Fraction], dict | None]:
    '''
    Generates randomizations of prose and lyric baselines and collects test statistics.
    Results are cached per chunk to allow recovery from crashes.

    Args:
        odes: set of odes whose shapes the baselines mirror 
        responsion_type_folder: path to the folder containing the XMLs with the canticum with the desired responsion type (e.g., triads or strophes)
        randomizations: total number of random draws
        workers: number of parallel worker processes (1 for sequential)
        chunk_size: optional chunk size per worker; defaults to ceil(randomizations / workers)
        include_lyric_stats: whether to collect lyric baseline composition statistics
        use_cache: whether to use cached chunk results and save new chunks (default True)

    Return: (T_pos_prose_list, T_song_prose_list, T_pos_lyric_list, T_song_lyric_list, lyric_stats_summary)
    where each list contains Fractions corresponding to the test statistics calculated in one_t_prose and one_t_lyric respectively.
    lyric_stats_summary is a dict aggregating lyric baseline composition stats if include_lyric_stats is True, else None.
    
    CACHING BEHAVIOR:
    - Each chunk is saved to data/cache/test_statistics_chunks_{responsion_type_folder.name}/chunk_{start}_{end}.pkl after completion
    - On restart, existing chunks are loaded from cache and skipped
    - Cached chunks are reused even if a new run uses a different chunk_size; only missing ranges are recomputed
    - This allows recovery from crashes without recomputing all randomizations
    - To start fresh, call clear_test_statistics_cache() or set use_cache=False
    - Cache files can be safely deleted manually if needed
    
    EXAMPLE USAGE:
        # Run with crash recovery enabled (default)
        results = test_statistics(randomizations=10_000, workers=8, chunk_size=1_000)
        
        # If it crashes, simply run again—completed chunks will be loaded from cache
        results = test_statistics(randomizations=10_000, workers=8, chunk_size=1_000)
        
        # To start completely fresh
        clear_test_statistics_cache(responsion_type_folder)
        results = test_statistics(randomizations=10_000, workers=8, chunk_size=1_000)
    '''
    responsion_type_folder = resolve_path(responsion_type_folder)
    cache_dir = get_test_statistics_cache_dir(responsion_type_folder)

    # Setup cache directory
    if use_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
    
    if workers <= 1:
        # For sequential execution, treat the entire run as one chunk
        chunk_id = f"0_{randomizations}"
        chunk_file = cache_dir / f"chunk_{chunk_id}.pkl" if use_cache else None
        
        # Check if cached result exists
        if use_cache and chunk_file and chunk_file.exists():
            print(f"Loading cached results from {chunk_file}")
            with open(chunk_file, 'rb') as f:
                cached_result = pickle.load(f)
            return cached_result
        
        T_pos_prose_list: list[Fraction] = []
        T_song_prose_list: list[Fraction] = []
        T_pos_lyric_list: list[Fraction] = []
        T_song_lyric_list: list[Fraction] = []
        lyric_stats_summary = _empty_lyric_stats_summary() if include_lyric_stats else None

        for i in tqdm(range(randomizations), desc="Test statistics"):
            T_pos_prose, T_song_prose, T_pos_lyric, T_song_lyric, stats_summary = _run_one_t_with_retries(
                odes=odes,
                responsion_type_folder=responsion_type_folder,
                seed_offset=i,
                collect_lyric_stats=include_lyric_stats,
            )
            if include_lyric_stats and stats_summary is not None:
                _merge_lyric_stats_summary(lyric_stats_summary, stats_summary)
            T_pos_prose_list.append(T_pos_prose)
            T_song_prose_list.append(T_song_prose)
            T_pos_lyric_list.append(T_pos_lyric)
            T_song_lyric_list.append(T_song_lyric)

        result = (T_pos_prose_list, T_song_prose_list, T_pos_lyric_list, T_song_lyric_list, lyric_stats_summary)
        
        # Save result to cache
        if use_cache and chunk_file:
            with open(chunk_file, 'wb') as f:
                pickle.dump(result, f)
            print(f"Saved results to {chunk_file}")
        
        return result

    # Parallel execution
    workers = max(1, workers)
    if chunk_size is None:
        chunk_size = math.ceil(randomizations / workers)
    chunk_size = max(1, chunk_size)

    def _load_cached_chunks_within_range(max_randomizations: int):
        """Load cached chunks regardless of chunk size, skipping overlaps and invalid data."""
        if not use_cache or not cache_dir.exists():
            return {}

        pattern = re.compile(r"chunk_(\d+)_(\d+)\.pkl$")
        discovered: list[tuple[int, int, Path]] = []
        for path in cache_dir.glob("chunk_*_*.pkl"):
            match = pattern.match(path.name)
            if not match:
                continue
            start, end = map(int, match.groups())
            if start < 0 or end <= start or end > max_randomizations:
                continue
            discovered.append((start, end, path))

        discovered.sort(key=lambda x: x[0])
        cached: dict[tuple[int, int], tuple[list[Fraction], list[Fraction], list[Fraction], list[Fraction], dict | None]] = {}
        for start, end, path in discovered:
            if any(not (end <= s or start >= e) for s, e in cached.keys()):
                continue  # Skip overlapping cached ranges
            try:
                with open(path, 'rb') as f:
                    result = pickle.load(f)
            except Exception as exc:  # pragma: no cover - defensive against corrupt cache
                print(f"Skipping cached chunk {path} (read failed: {exc})")
                continue

            expected_len = end - start
            if not (isinstance(result, (list, tuple)) and len(result) >= 4):
                print(f"Skipping cached chunk {path} (unexpected format)")
                continue
            if not (len(result[0]) == len(result[1]) == len(result[2]) == len(result[3]) == expected_len):
                print(f"Skipping cached chunk {path} (length mismatch)")
                continue

            cached[(start, end)] = result
            print(f"Loaded cached chunk {start}_{end} ({expected_len} iterations)")

        return cached

    cached_results = _load_cached_chunks_within_range(randomizations)
    cached_chunks_loaded = len(cached_results)

    # Identify missing ranges after accounting for any cached coverage
    missing_ranges: list[tuple[int, int]] = []
    cursor = 0
    for start, end in sorted(cached_results.keys()):
        if cursor < start:
            missing_ranges.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < randomizations:
        missing_ranges.append((cursor, randomizations))

    chunks_to_compute: list[tuple[int, int]] = []
    for missing_start, missing_end in missing_ranges:
        current = missing_start
        while current < missing_end:
            end = min(current + chunk_size, missing_end)
            chunks_to_compute.append((current, end))
            current = end

    max_workers = min(workers, len(chunks_to_compute)) if chunks_to_compute else 0

    futures = []
    results: list[tuple[list[Fraction], list[Fraction], list[Fraction], list[Fraction], dict | None]] = []

    if chunks_to_compute:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for worker_id, (start, end) in enumerate(chunks_to_compute):
                chunk_id = f"{start}_{end}"
                futures.append((start, end, chunk_id, executor.submit(_run_test_statistics_chunk, start, end, worker_id, odes, responsion_type_folder, include_lyric_stats)))

            with tqdm(total=sum(end - start for start, end in chunks_to_compute), desc="Test statistics (computing)", leave=True) as pbar:
                for start, end, chunk_id, future in sorted(futures, key=lambda x: x[0]):
                    result = future.result()
                    cached_results[(start, end)] = result

                    if use_cache:
                        chunk_file = cache_dir / f"chunk_{chunk_id}.pkl"
                        with open(chunk_file, 'wb') as f:
                            pickle.dump(result, f)
                        print(f"\nSaved chunk {chunk_id} to {chunk_file}")

                    pbar.update(end - start)

    for start, end in sorted(cached_results.keys()):
        results.append(cached_results[(start, end)])

    total_chunks = cached_chunks_loaded + len(chunks_to_compute)
    if use_cache and total_chunks > 1:
        print(f"\nCompleted: {cached_chunks_loaded} chunks from cache, {len(chunks_to_compute)} chunks computed ({randomizations} total iterations)")

    T_pos_prose_list: list[Fraction] = []
    T_song_prose_list: list[Fraction] = []
    T_pos_lyric_list: list[Fraction] = []
    T_song_lyric_list: list[Fraction] = []
    lyric_stats_summary = _empty_lyric_stats_summary() if include_lyric_stats else None

    for chunk_result in results:
        prose_pos, prose_song, lyric_pos, lyric_song, stats_summary = chunk_result
        T_pos_prose_list.extend(prose_pos)
        T_song_prose_list.extend(prose_song)
        T_pos_lyric_list.extend(lyric_pos)
        T_song_lyric_list.extend(lyric_song)
        if include_lyric_stats and stats_summary is not None:
            _merge_lyric_stats_summary(lyric_stats_summary, stats_summary)

    return T_pos_prose_list, T_song_prose_list, T_pos_lyric_list, T_song_lyric_list, lyric_stats_summary


######################################
### TEST STATISTICS DIRECT HELPERS ###
######################################


def clear_test_statistics_cache(responsion_type_folder: Path = ROOT / "data" / "compiled" / "triads"):
    """
    Remove cached test statistics chunks for one responsion-type corpus folder.
    Call this if you want to recompute from scratch.
    """
    cache_dir = get_test_statistics_cache_dir(responsion_type_folder)
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print(f"Cleared test statistics cache: {cache_dir}")
    else:
        print(f"No cache to clear at {cache_dir}")


def _empty_lyric_stats_summary():
    return {
        'total_lines': 0,
        'pindar_lines': 0,
        'external_lines': 0,
        'prose_lines': 0,
        'unaltered_lines': 0,
        'trimmed_lines': 0,
        'padded_lines': 0,
        'paired_fallbacks': 0,
        'prose_fallback_details': [],
    }


def _merge_lyric_stats_summary(dest: dict, src: dict):
    for key in dest.keys():
        if isinstance(dest[key], list):
            dest[key].extend(src.get(key, []))
        else:
            dest[key] += src.get(key, 0)


def _run_one_t_with_retries(
    odes: set,
    responsion_type_folder: Path,
    seed_offset: int,
    prose_dir: Path | None = None,
    lyric_dir: Path | None = None,
    collect_lyric_stats: bool = False,
) -> tuple[Fraction, Fraction, Fraction, Fraction, dict | None]:
    prose_dir = prose_dir or (ROOT / "tmp_stats" / "prose")
    lyric_dir = lyric_dir or (ROOT / "tmp_stats" / "lyric")

    last_exc: Exception | None = None
    for attempt in range(BASELINE_MAX_RETRIES + 1):
        retry_seed = seed_offset + attempt * BASELINE_RETRY_SEED_STRIDE
        try:
            T_pos_prose, T_song_prose = one_t_prose(
                odes=odes,
                responsion_type_folder=responsion_type_folder,
                seed_offset=retry_seed,
                temp_dir=prose_dir,
            )

            if collect_lyric_stats:
                T_pos_lyric, T_song_lyric, stats_summary = one_t_lyric(
                    odes=odes,
                    responsion_type_folder=responsion_type_folder,
                    seed_offset=retry_seed,
                    temp_dir=lyric_dir,
                    collect_stats=True,
                )
            else:
                T_pos_lyric, T_song_lyric = one_t_lyric(
                    odes=odes,
                    responsion_type_folder=responsion_type_folder,
                    seed_offset=retry_seed,
                    temp_dir=lyric_dir,
                    collect_stats=False,
                )
                stats_summary = None

            return T_pos_prose, T_song_prose, T_pos_lyric, T_song_lyric, stats_summary
        except (ValueError, RuntimeError) as exc:
            last_exc = exc
            if attempt >= BASELINE_MAX_RETRIES:
                break
            print(
                "Retrying baseline for seed_offset "
                f"{seed_offset} (attempt {attempt + 1}/{BASELINE_MAX_RETRIES}) "
                f"after error: {type(exc).__name__}: {exc}"
            )

    assert last_exc is not None
    raise last_exc


def _run_test_statistics_chunk(start: int, end: int, worker_id: int, odes: set, responsion_type_folder: Path, collect_lyric_stats: bool = False) -> tuple[list[Fraction], list[Fraction], list[Fraction], list[Fraction], dict | None]:
    """Run a slice of test statistics in an isolated temp workspace (used for multiprocessing)."""

    T_pos_prose_list: list[Fraction] = []
    T_song_prose_list: list[Fraction] = []
    T_pos_lyric_list: list[Fraction] = []
    T_song_lyric_list: list[Fraction] = []
    lyric_stats_summary = _empty_lyric_stats_summary() if collect_lyric_stats else None

    base_dir = ROOT / "tmp_stats" / f"worker_{worker_id}"
    prose_dir = base_dir / "prose"
    lyric_dir = base_dir / "lyric"

    for seed_offset in range(start, end):
        T_pos_prose, T_song_prose, T_pos_lyric, T_song_lyric, stats_summary = _run_one_t_with_retries(
            odes=odes,
            responsion_type_folder=responsion_type_folder,
            seed_offset=seed_offset,
            prose_dir=prose_dir,
            lyric_dir=lyric_dir,
            collect_lyric_stats=collect_lyric_stats,
        )

        if collect_lyric_stats and stats_summary is not None:
            _merge_lyric_stats_summary(lyric_stats_summary, stats_summary)

        T_pos_prose_list.append(T_pos_prose)
        T_song_prose_list.append(T_song_prose)
        T_pos_lyric_list.append(T_pos_lyric)
        T_song_lyric_list.append(T_song_lyric)

    shutil.rmtree(base_dir, ignore_errors=True)

    return T_pos_prose_list, T_song_prose_list, T_pos_lyric_list, T_song_lyric_list, lyric_stats_summary


##############################
### SINGLE TEST STATISTICS ###
##############################


def one_t_prose(odes: set, responsion_type_folder: Path, seed_offset: int = 0, temp_dir: Path = ROOT / "tmp_stats" / "prose") -> tuple[Fraction, Fraction]:
    r'''
    Creates exactly one baseline for each of the odes, storing the xmls in a tmp folder.

    We then calculate the Fraction mean
        compatibility_ratios_to_stats(compatibility_canticum(ROOT / 'tmp_stats/....xml', 'responsion_id'))
    on each of the xmls and then in turn take the statistics.mean T_song_prose of these Fractions.

    We then calculate the Fraction mean $T_pos_prose = \frac{1}{N} \sum_{i=1}^N$
        compatibility_ratios_to_stats(compatibility_corpus(ROOT / 'tmp_stats'))
    on the entire corpus folder of xmls.

    Then the tmp is deleted.
    
    Args:
        odes: set of ode IDs to generate baselines for
        responsion_type_folder: path to folder containing XML files with the canticum elements of the desired responsion type (e.g., triads or strophes)
        seed_offset: integer offset to ensure different randomization across calls (e.g., for parallel execution)
        temp_dir: path to temporary directory for storing intermediate XML files; will be created if it doesn't exist and deleted after use

    Return: (T_pos_prose, T_song_prose)
    '''

    prefix_to_xml = {
        "ol": responsion_type_folder / f"ht_olympians_{responsion_type_folder.name}.xml",
        "py": responsion_type_folder / f"ht_pythians_{responsion_type_folder.name}.xml",
        "ne": responsion_type_folder / f"ht_nemeans_{responsion_type_folder.name}.xml",
        "is": responsion_type_folder / f"ht_isthmians_{responsion_type_folder.name}.xml",
    }
    
    scan_dir = temp_dir / "scan"
    compiled_dir = temp_dir / "compiled"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    scan_dir.mkdir(parents=True, exist_ok=True)
    compiled_dir.mkdir(parents=True, exist_ok=True)

    cached_corpus = load_cached_prose_corpus(PROSE_CACHE_PATH)

    song_stats = []

    try:
        for responsion_id in tqdm(sorted(odes), leave=False, desc="Prose baselines"):
            prefix = responsion_id[:2]
            if prefix not in prefix_to_xml:
                raise RuntimeError(f"Unknown ode prefix for {responsion_id}, expected one of {list(prefix_to_xml.keys())}")
            xml_file = prefix_to_xml[prefix]
            if not canticum_with_at_least_two_strophes(xml_file, responsion_id):
                continue

            strophe_scheme = get_shape_canticum(str(xml_file), responsion_id)

            tree = etree.parse(str(xml_file))
            root = tree.getroot()
            strophes = root.findall(f".//strophe[@responsion='{responsion_id}']")
            sample_size = len(strophes)
            if sample_size == 0:
                continue

            lines_by_position = []
            for line_idx, line_length in enumerate(strophe_scheme):
                position_lines = []
                used_lines = set()
                attempts = 0
                max_attempts = sample_size * 10

                while len(position_lines) < sample_size and attempts < max_attempts:
                    line_seed = 1453 + seed_offset * 1000 + line_idx * 10000 + attempts
                    sample_lines = prose_end_sample_cached(cached_corpus, line_length, 1, line_seed)
                    if sample_lines:
                        line_text = sample_lines[0]
                        if line_text not in used_lines:
                            position_lines.append(line_text)
                            used_lines.add(line_text)
                    attempts += 1

                if len(position_lines) < sample_size:
                    raise RuntimeError(f"Could not find {sample_size} unique prose lines for position {line_idx+1} (length {line_length}). Only found {len(position_lines)} unique lines after {max_attempts} attempts.")

                lines_by_position.append(position_lines)

            strophe_sample_lists = []
            for strophe_idx in range(sample_size):
                strophe_lines = []
                for line_idx in range(len(strophe_scheme)):
                    strophe_lines.append(lines_by_position[line_idx][strophe_idx])
                strophe_sample_lists.append(strophe_lines)

            responsion_key = f"{responsion_id}_000"
            outfile_scan = scan_dir / f"baseline_prose_{responsion_id}.xml"
            outfile_compiled = compiled_dir / f"baseline_prose_{responsion_id}.xml"

            dummy_xml_strophe({responsion_key: strophe_sample_lists}, str(outfile_scan), type="Prose")
            process_file(str(outfile_scan), str(outfile_compiled), make_print=False)

            song_stat = compatibility_ratios_to_stats(compatibility_canticum(str(outfile_compiled), responsion_key))
            song_stats.append(song_stat)

        T_song_prose = mean(song_stats) if song_stats else Fraction(0, 1)
        T_pos_prose = compatibility_ratios_to_stats(compatibility_corpus(str(compiled_dir), progress=False)) if compiled_dir.exists() else Fraction(0, 1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return T_pos_prose, T_song_prose


def one_t_lyric(odes: set, responsion_type_folder: Path, seed_offset: int = 0, temp_dir: Path = ROOT / "tmp_stats" / "lyric", collect_stats: bool = False) -> tuple[Fraction, Fraction] | tuple[Fraction, Fraction, dict]:
    '''
    Mutatis mutandis to one_t_prose, but for lyric baselines instead of prose baselines.
    
    Args: 
    - odes: set of ode IDs to generate baselines for
    - responsion_type_folder: path to folder containing XML files with the canticum elements of the desired responsion type (e.g., triads or strophes)
    - seed_offset: integer offset to ensure different randomization across calls (e.g., for parallel execution)
    - temp_dir: path to temporary directory for storing intermediate XML files; will be created if it doesn't exist and deleted after use
    - collect_stats: whether to collect detailed lyric baseline composition statistics (line source attribution, modifications, etc.) in a dict returned as the third element of the result tuple; if False, only returns (T_pos_lyric, T_song_lyric)
    '''
    
    prefix_to_xml = {
        "ol": responsion_type_folder / f"ht_olympians_{responsion_type_folder.name}.xml",
        "py": responsion_type_folder / f"ht_pythians_{responsion_type_folder.name}.xml",
        "ne": responsion_type_folder / f"ht_nemeans_{responsion_type_folder.name}.xml",
        "is": responsion_type_folder / f"ht_isthmians_{responsion_type_folder.name}.xml",
    }
    
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    song_stats = []
    summary_stats = _empty_lyric_stats_summary() if collect_stats else None

    try:
        for responsion_id in tqdm(sorted(odes), leave=False, desc="Lyric baselines"):
            prefix = responsion_id[:2]
            if prefix not in prefix_to_xml:
                raise RuntimeError(f"Unknown ode prefix for {responsion_id}, expected one of {list(prefix_to_xml.keys())}")
            xml_file = prefix_to_xml[prefix]
            if not canticum_with_at_least_two_strophes(xml_file, responsion_id):
                raise RuntimeError(f"Ode {responsion_id} does not have at least two strophes.")

            last_exc: Exception | None = None
            for attempt in range(BASELINE_MAX_RETRIES + 1):
                try:
                    stats = _make_lyric_baseline(
                        xml_file,
                        responsion_id,
                        corpus_folder=responsion_type_folder,
                        outfolder=temp_dir,
                        cache_file=LYRIC_CACHE_PATH,
                        randomizations=1,
                        debug=False,
                        seed_base=1453 + seed_offset * 1000 + attempt * BASELINE_RETRY_SEED_STRIDE,
                    )

                    if collect_stats and isinstance(stats, dict):
                        _merge_lyric_stats_summary(summary_stats, stats)

                    outfile = temp_dir / f"baseline_lyric_{responsion_id}.xml"
                    responsion_key = f"{responsion_id}_000"
                    song_stat = compatibility_ratios_to_stats(compatibility_canticum(str(outfile), responsion_key))
                    song_stats.append(song_stat)
                    last_exc = None
                    break
                except (ValueError, RuntimeError) as exc:
                    last_exc = exc
                    if attempt >= BASELINE_MAX_RETRIES:
                        break
                    print(
                        "Retrying lyric baseline for responsion "
                        f"{responsion_id} (attempt {attempt + 1}/{BASELINE_MAX_RETRIES}) "
                        f"after error: {type(exc).__name__}: {exc}"
                    )

            if last_exc is not None:
                raise last_exc

        T_song_lyric = mean(song_stats) if song_stats else Fraction(0, 1)
        T_pos_lyric = compatibility_ratios_to_stats(compatibility_corpus(str(temp_dir), progress=False)) if temp_dir.exists() else Fraction(0, 1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    if collect_stats:
        return T_pos_lyric, T_song_lyric, summary_stats
    return T_pos_lyric, T_song_lyric


def _make_lyric_baseline(xml_file: str, responsion_id: str, corpus_folder: str, 
                           outfolder: str = "data/compiled/baselines/triads/lyric", 
                           cache_file: str = LYRIC_CACHE_PATH, randomizations=10_000, debug: bool = False, seed_base: int = 1453):
    """
    Fast lyric baseline generation using cached preprocessed corpus.
    Helper for one_t_lyric.
    
    Args:
        xml_file: path to XML file containing the original strophe structure
        responsion_id: the responsion ID to generate baseline for
        corpus_folder: folder containing XML files for lyric line sampling
        outfolder: folder to write the baseline XML file to
        cache_file: path to cached corpus data
        debug: whether to print debug information
        
    Returns:
        dict: diagnostic statistics about the baseline generation including:
            - total_lines: total number of lines generated
            - pindar_lines: number of lines from Pindar corpus
            - external_lines: number of lines from external corpus
            - unaltered_lines: number of lines used without modification
            - trimmed_lines: number of lines with syllables removed
            - padded_lines: number of lines with syllables added
            - paired_fallbacks: number of lines produced by paired-line fallback
    """
    
    xml_file = resolve_path(xml_file)
    corpus_folder = resolve_path(corpus_folder)
    outfolder = resolve_path(outfolder)
    cache_file = resolve_path(cache_file)

    # Load cached corpus data
    cached_corpus = load_cached_lyric_corpus(cache_file, corpus_folder)
    
    strophe_scheme = get_shape_canticum(str(xml_file), responsion_id)

    # Count the number of strophes with the given responsion_id in the original file
    tree = etree.parse(str(xml_file))
    root = tree.getroot()
    strophes = root.findall(f".//strophe[@responsion='{responsion_id}']")
    sample_size = len(strophes)
    
    # Get the filename of the input XML to exclude from external file-level sampling.
    # Internal lyric contamination is responsion-based because corpus files contain
    # multiple odes; an is01 baseline may use is02, but not is01.
    input_filename = os.path.basename(xml_file)

    def _apply_baseline_anceps(line_element):
        for syll in line_element.xpath(".//syll"):
            if syll.get("resolution") != "True" and syll.get("anceps") != "True":
                syll.set("anceps", "True")
        return line_element
    
    if debug:
        print(f"Found {sample_size} strophes with responsion '{responsion_id}' in original file")
        print(f"Strophe scheme: {strophe_scheme}")
        print(f"Excluding {input_filename} from corpus sampling")
        print(f"Generating 100 baseline samples...")
    
    # Initialize diagnostic statistics tracking
    total_lines = 0
    pindar_lines = 0
    external_lines = 0
    prose_lines = 0
    unaltered_lines = 0
    trimmed_lines = 0
    padded_lines = 0
    paired_fallbacks = 0
    prose_fallback_details = []
    
    # Generate different baseline samples with different seeds
    strophe_samples_dict = {}
    
    for i in range(randomizations):
        seed = seed_base + i  # Different seed for each sample
        responsion_key = f"{responsion_id}_{i:03d}"  # e.g., "is01_000", "is01_001", etc.

        cached_prose = None
        prose_used_lines = set()

        def _prose_fallback_line(target_len: int, fallback_seed: int, line_idx: int):
            nonlocal cached_prose
            if cached_prose is None:
                cached_prose = load_cached_prose_corpus(PROSE_CACHE_PATH)

            prose_samples = prose_end_sample_cached(cached_prose, target_len, 1, fallback_seed)
            if not prose_samples:
                return None

            prose_text = prose_samples[0]
            if prose_text in prose_used_lines:
                return None

            raw_xml = f"<l>{prose_text}</l>"
            compiled_xml = compile_scan(raw_xml)
            try:
                line_element = etree.fromstring(compiled_xml)
            except etree.XMLSyntaxError:
                return None

            if len(canonical_sylls(line_element)) != target_len:
                return None

            line_element.set('source', 'prose_fallback')
            line_element.set('prose_text', prose_text)
            line_element.set('prose_seed', str(fallback_seed))
            return line_element
        
        # Track used metrical positions across ALL line positions for this sample to ensure independence
        sample_used_metrical_positions = set()

        # Track used responsion_ids per relative line position to prevent correlation between strophes
        used_responsions_per_position = [set() for _ in range(len(strophe_scheme))]

        lines_by_position = []

        def _matches_pattern(target, candidate):
            if len(target) != len(candidate):
                return False
            for s1, s2 in zip(target, candidate):
                if s1 == 'anceps' or s2 == 'anceps':
                    continue
                if s1 != s2:
                    return False
            return True
        
        for line_idx, line_length in enumerate(strophe_scheme):
            position_lines = []
            used_lines = set()  # Track used lines for this position
            target_pattern = None

            attempts = 0
            max_attempts = sample_size * 10  # Allow multiple attempts to find unique lines
            position_attempts = 0
            base_used_metrical_positions = set(sample_used_metrical_positions)

            while position_attempts <= LYRIC_POSITION_MAX_RETRIES:
                while len(position_lines) < sample_size and attempts < max_attempts:
                    line_seed = seed + line_idx * 10000 + attempts
                    sample_line = lyric_line_sample_cached(
                        line_length,
                        cached_corpus,
                        seed=line_seed,
                        debug=debug,
                        exclude_responsion_id=responsion_id,
                        used_metrical_positions=sample_used_metrical_positions,
                        used_responsions_this_position=used_responsions_per_position[line_idx],
                    )

                    if sample_line is not None:
                        sample_line = _apply_baseline_anceps(sample_line)
                        line_text = etree.tostring(sample_line, encoding='unicode', method='xml')
                        if line_text not in used_lines:
                            candidate_pattern = canonical_sylls(sample_line)
                            if target_pattern is None:
                                target_pattern = candidate_pattern
                            elif not _matches_pattern(target_pattern, candidate_pattern):
                                continue
                            source_attr = sample_line.get('source', '')
                            if ',' in source_attr:
                                responsion_from_source = source_attr.split(',')[0].strip()
                            else:
                                responsion_from_source = source_attr

                            used_responsions_per_position[line_idx].add(responsion_from_source)
                            position_lines.append(line_text)
                            used_lines.add(line_text)

                    attempts += 1

                if len(position_lines) < sample_size:
                    needed = sample_size - len(position_lines)

                    def paired_line_fallback(target_len):
                        nonlocal target_pattern
                        candidates = []
                        for length_key, lines_list in cached_corpus['lines_by_length'].items():
                            for item in lines_list:
                                if item['responsion_id'] == responsion_id:
                                    continue
                                position_key = (item['file'], item['canticum_idx'], item['strophe_idx'], item['line_idx'])
                                if position_key in sample_used_metrical_positions:
                                    continue
                                if item['responsion_id'] in used_responsions_per_position[line_idx]:
                                    continue
                                candidates.append((length_key, item))

                        if len(candidates) < 2:
                            return None

                        max_pairs = min(500, len(candidates) ** 2)
                        for _ in range(max_pairs):
                            length1, item1 = random.choice(candidates)
                            length2, item2 = random.choice(candidates)
                            pos1 = (item1['file'], item1['canticum_idx'], item1['strophe_idx'], item1['line_idx'])
                            pos2 = (item2['file'], item2['canticum_idx'], item2['strophe_idx'], item2['line_idx'])
                            if pos1 == pos2 or pos2 in sample_used_metrical_positions:
                                continue
                            if item2['responsion_id'] in used_responsions_per_position[line_idx]:
                                continue
                            if length1 + length2 < target_len:
                                continue

                            line1 = etree.fromstring(item1['xml'])
                            line2 = etree.fromstring(item2['xml'])
                            sylls1 = line1.xpath(".//syll")
                            sylls2 = line2.xpath(".//syll")
                            total_len = len(sylls1) + len(sylls2)
                            trim_needed = total_len - target_len
                            if trim_needed < 0 or trim_needed > len(sylls1):
                                continue

                            trimmed_sylls1 = sylls1[trim_needed:] if trim_needed else sylls1
                            combined_sylls = trimmed_sylls1 + sylls2
                            if len(combined_sylls) != target_len:
                                continue

                            new_line = etree.Element("l")
                            for attr, value in line1.attrib.items():
                                if attr != 'source':
                                    new_line.set(attr, value)
                            source_info = (
                                f"paired:{item1['responsion_id']}+{item2['responsion_id']}, "
                                f"trimmed_first -{trim_needed}"
                            )
                            new_line.set('source', source_info)
                            for syll in combined_sylls:
                                new_line.append(syll)

                            if len(canonical_sylls(new_line)) != target_len:
                                continue

                            new_line = _apply_baseline_anceps(new_line)

                            candidate_pattern = canonical_sylls(new_line)
                            if target_pattern is None:
                                target_pattern = candidate_pattern
                            elif not _matches_pattern(target_pattern, candidate_pattern):
                                continue

                            sample_used_metrical_positions.add(pos1)
                            sample_used_metrical_positions.add(pos2)
                            used_responsions_per_position[line_idx].add(item1['responsion_id'])
                            used_responsions_per_position[line_idx].add(item2['responsion_id'])
                            return new_line

                        return None

                    for _ in range(needed):
                        fallback_line = paired_line_fallback(line_length)
                        if fallback_line is not None:
                            line_text = etree.tostring(fallback_line, encoding='unicode', method='xml')
                            if line_text not in used_lines:
                                position_lines.append(line_text)
                                used_lines.add(line_text)
                        else:
                            break

                if len(position_lines) < sample_size:
                    prose_attempts = 0
                    max_prose_attempts = max_attempts

                    while len(position_lines) < sample_size and prose_attempts < max_prose_attempts:
                        prose_seed = seed + line_idx * 10000 + 500000 + prose_attempts
                        prose_line = _prose_fallback_line(line_length, prose_seed, line_idx)
                        if prose_line is not None:
                            prose_line = _apply_baseline_anceps(prose_line)
                            candidate_pattern = canonical_sylls(prose_line)
                            if target_pattern is None:
                                target_pattern = candidate_pattern
                            elif not _matches_pattern(target_pattern, candidate_pattern):
                                prose_attempts += 1
                                continue
                            prose_text = etree.tostring(prose_line, encoding='unicode', method='xml')
                            if prose_text not in used_lines:
                                prose_raw_text = prose_line.get('prose_text', '')
                                if prose_raw_text:
                                    prose_used_lines.add(prose_raw_text)
                                prose_fallback_details.append({
                                    'responsion_id': responsion_id,
                                    'responsion_key': responsion_key,
                                    'line_idx': line_idx + 1,
                                    'line_length': line_length,
                                    'seed': int(prose_line.get('prose_seed', prose_seed)),
                                    'prose_text': prose_raw_text,
                                })
                                prose_line.attrib.pop('prose_text', None)
                                prose_line.attrib.pop('prose_seed', None)
                                prose_text = etree.tostring(prose_line, encoding='unicode', method='xml')
                                position_lines.append(prose_text)
                                used_lines.add(prose_text)
                        prose_attempts += 1

                if len(position_lines) < sample_size:
                    position_attempts += 1
                    position_lines = []
                    used_lines = set()
                    target_pattern = None
                    attempts = 0
                    used_responsions_per_position[line_idx].clear()
                    sample_used_metrical_positions.clear()
                    sample_used_metrical_positions.update(base_used_metrical_positions)
                    continue

                try:
                    line_elements = [etree.fromstring(line) for line in position_lines]
                except etree.XMLSyntaxError:
                    line_elements = []

                if not line_elements or not metrically_responding_lines_polystrophic(*line_elements):
                    position_attempts += 1
                    position_lines = []
                    used_lines = set()
                    target_pattern = None
                    attempts = 0
                    used_responsions_per_position[line_idx].clear()
                    sample_used_metrical_positions.clear()
                    sample_used_metrical_positions.update(base_used_metrical_positions)
                    continue

                for line in line_elements:
                    source_attr = line.get('source', '')
                    total_lines += 1
                    if source_attr.startswith('prose_fallback'):
                        prose_lines += 1
                    elif source_attr.startswith('external'):
                        external_lines += 1
                    else:
                        pindar_lines += 1

                    if source_attr.startswith('paired:'):
                        paired_fallbacks += 1

                    if 'trimmed' in source_attr:
                        trimmed_lines += 1
                    elif 'padded' in source_attr:
                        padded_lines += 1
                    else:
                        unaltered_lines += 1

                break

            if len(position_lines) < sample_size:
                raise RuntimeError(
                    f"Could not find {sample_size} unique lines for position {line_idx+1} "
                    f"(length {line_length}). Only found {len(position_lines)} unique lines after "
                    f"{max_attempts} attempts including paired-line and prose fallback."
                )

            lines_by_position.append(position_lines)
        
        # Now assemble strophes from the position-specific lines
        strophe_sample_lists = []
        
        for strophe_idx in range(sample_size):
            strophe_lines = []
            
            for line_idx in range(len(strophe_scheme)):
                strophe_lines.append(lines_by_position[line_idx][strophe_idx])
            
            strophe_sample_lists.append(strophe_lines)
        
        strophe_samples_dict[responsion_key] = strophe_sample_lists
    
    outdir = outfolder
    outdir.mkdir(parents=True, exist_ok=True)
    if debug:
        print(f"Writing lyric baseline for responsion {responsion_id} to {outdir}")

    filename = f"baseline_lyric_{responsion_id}.xml"
    filepath = outdir / filename
    
    # Add anceps="True" to syllables that don't have resolution or anceps attributes
    for responsion_key, strophe_sample_lists in strophe_samples_dict.items():
        for strophe_idx, strophe_sample_list in enumerate(strophe_sample_lists):
            for line_idx, line in enumerate(strophe_sample_list):
                try:
                    line_element = etree.fromstring(line)
                    # Find all syllable elements
                    for syll in line_element.xpath(".//syll"):
                        # Check if syllable already has resolution="True" or anceps="True"
                        if syll.get("resolution") != "True" and syll.get("anceps") != "True":
                            syll.set("anceps", "True")
                    
                    # Convert back to string and update the list
                    updated_line = etree.tostring(line_element, encoding='unicode', method='xml')
                    strophe_samples_dict[responsion_key][strophe_idx][line_idx] = updated_line
                    
                except etree.XMLSyntaxError:
                    # Skip malformed XML lines
                    continue
    
    dummy_xml_strophe(strophe_samples_dict, str(filepath), type="Lyric")

    if debug:
        # Debug first sample only
        first_key = list(strophe_samples_dict.keys())[0]
        print(f"Debug: First strophe sample for {first_key}:")
        for i, line in enumerate(strophe_samples_dict[first_key][0]):
            print(f"  Line {i+1} (length {strophe_scheme[i]}): {line}")
    
    # Return diagnostic statistics
    return {
        'responsion_id': responsion_id,
        'total_lines': total_lines,
        'pindar_lines': pindar_lines,
        'external_lines': external_lines,
        'prose_lines': prose_lines,
        'unaltered_lines': unaltered_lines,
        'trimmed_lines': trimmed_lines,
        'padded_lines': padded_lines,
        'paired_fallbacks': paired_fallbacks,
        'prose_fallback_details': prose_fallback_details,
    }

#####################
# PREPROCESS CORPUS #
#####################

def preprocess_and_cache_prose_corpus(corpus: str, cache_file: str = PROSE_CACHE_PATH):
    """
    Preprocess the entire prose corpus once and cache results by number of syllables.
    
    Args:
        corpus: the prose text to preprocess
        cache_file: path to save the cached results
        
    Returns:
        dict: syllable_length -> list of processed sentences
    """
    cache_file = resolve_path(cache_file)

    print("Preprocessing prose corpus...")
    
    # Initial corpus processing (done once)
    corpus = re.sub(punctuation_except_period, '', corpus)
    corpus = lower_grc(corpus)
    sentences = corpus.split(".")
    
    # Group processed sentences by syllable count
    sentences_by_length = defaultdict(list)
    
    for sentence in tqdm(sentences, desc="Processing sentences"):
        if not sentence:
            continue
            
        # Get syllables once
        sentence_sylls = syllabifier(sentence)
        if len(sentence_sylls) < 1:  # Skip empty sentences
            continue
            
        # Process for different n_sylls values (we'll cache up to reasonable max length)
        max_length = min(len(sentence_sylls), 50)  # Cache up to 50 syllables
        
        for n_sylls in range(1, max_length + 1):
            if len(sentence_sylls) >= n_sylls:
                # Extract last n syllables
                end_sylls = "".join(sentence_sylls[-n_sylls:])
                
                # Apply rule scansion
                scanned = rule_scansion(end_sylls, correption=False)
                if not scanned:
                    continue
                    
                # Add # after opening brackets
                processed = re.sub(r'([\[{])', r'\1#', scanned)
                
                # Check syllable count matches
                sylls = re.split(r'[\[\]{}]', processed)
                sylls = [syll for syll in sylls if syll]
                
                if len(sylls) == n_sylls:
                    sentences_by_length[n_sylls].append(processed)
    
    # Save cache
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'wb') as f:
        pickle.dump(dict(sentences_by_length), f)
    
    print(f"Cached {sum(len(v) for v in sentences_by_length.values())} processed sentences")
    print(f"Syllable lengths available: {sorted(sentences_by_length.keys())}")
    print(f"Cache saved to: {cache_file}")
    
    return dict(sentences_by_length)

def load_cached_prose_corpus(cache_file: str = PROSE_CACHE_PATH):
    """
    Load cached prose corpus data.
    
    Args:
        cache_file: path to the cached results
        
    Returns:
        dict: syllable_length -> list of processed sentences
    """
    cache_file = resolve_path(cache_file)

    if not cache_file.exists():
        print(f"Cache file {cache_file} not found. Preprocessing corpus...")
        return preprocess_and_cache_prose_corpus(anabasis, cache_file)
    
    with open(cache_file, 'rb') as f:
        return pickle.load(f)
    
def preprocess_and_cache_lyric_corpus(corpus_folder: str, cache_file: str = LYRIC_CACHE_PATH):
    """
    Preprocess the entire lyric corpus once and cache results by canonical syllable length.
    
    Args:
        corpus_folder: folder containing XML files to process
        cache_file: path to save the cached results
        
    Returns:
        dict: canonical_length -> list of XML line elements (as strings) with metadata
    """
    corpus_folder = resolve_path(corpus_folder)
    cache_file = resolve_path(cache_file)

    print("Preprocessing lyric corpus...")
    
    xml_files = [f for f in os.listdir(corpus_folder) if f.endswith('.xml')]
    
    # Group lines by canonical syllable count
    lines_by_length = defaultdict(list)
    syllables_by_file = {}  # Store all syllables by file for fallback cases
    syllables_by_responsion = defaultdict(list)
    
    for xml_file in tqdm(xml_files, desc="Processing XML files"):
        file_path = Path(corpus_folder) / xml_file
        tree = etree.parse(str(file_path))
        root = tree.getroot()
        
        # Store syllables for this file (for fallback operations)
        file_syllables = []
        for syll in root.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]"):
            file_syllables.append(etree.tostring(syll, encoding='unicode', method='xml'))
        syllables_by_file[xml_file] = file_syllables
        
        # Process all canticum elements in this file
        for canticum_idx, canticum in enumerate(root.findall(".//canticum")):
            # Process all strophes within this canticum
            for strophe_idx, strophe in enumerate(canticum.findall(".//strophe")):
                responsion_id = strophe.get('responsion', 'unknown')
                for syll in strophe.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]"):
                    syllables_by_responsion[responsion_id].append(etree.tostring(syll, encoding='unicode', method='xml'))
                
                # Process all lines within this strophe
                for line_idx, l in enumerate(strophe.findall("l")):
                    try:
                        canonical_length = len(canonical_sylls(l))
                        
                        # Store line as XML string with metadata for contamination checking
                        line_xml = etree.tostring(l, encoding='unicode', method='xml')
                        lines_by_length[canonical_length].append({
                            'xml': line_xml,
                            'file': xml_file,
                            'canticum_idx': canticum_idx,
                            'strophe_idx': strophe_idx,
                            'line_idx': line_idx,
                            'responsion_id': responsion_id
                        })
                    except:
                        # Skip lines that cause errors in canonical_sylls
                        continue
    
    # Also cache the syllables for random selection in fallback cases
    all_syllables = []
    for file_syllables in syllables_by_file.values():
        all_syllables.extend(file_syllables)
    
    cached_data = {
        'lines_by_length': dict(lines_by_length),
        'all_syllables': all_syllables,
        'syllables_by_file': syllables_by_file,
        'syllables_by_responsion': dict(syllables_by_responsion),
    }
    
    # Save cache
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'wb') as f:
        pickle.dump(cached_data, f)
    
    print(f"Cached {sum(len(v) for v in lines_by_length.values())} lines")
    print(f"Line lengths available: {sorted(lines_by_length.keys())}")
    print(f"Total syllables cached: {len(all_syllables)}")
    print(f"Cache saved to: {cache_file}")
    
    return cached_data

def load_cached_lyric_corpus(cache_file: str, corpus_folder: str):
    """
    Load cached lyric corpus data.
    
    Args:
        cache_file: path to the cached results
        corpus_folder: folder containing XML files (for regenerating cache if needed)
        
    Returns:
        dict: cached corpus data
    """
    cache_file = resolve_path(cache_file)
    corpus_folder = resolve_path(corpus_folder)

    if not cache_file.exists():
        print(f"Cache file {cache_file} not found. Preprocessing corpus...")
        return preprocess_and_cache_lyric_corpus(corpus_folder, cache_file)
    
    with open(cache_file, 'rb') as f:
        cached_data = pickle.load(f)
    
    # Check if cache has the new metadata structure
    if 'lines_by_length' in cached_data and cached_data['lines_by_length']:
        # Get a sample line to check structure
        first_length = next(iter(cached_data['lines_by_length']))
        sample_lines = cached_data['lines_by_length'][first_length]
        if sample_lines and isinstance(sample_lines[0], dict):
            # Check if new metadata fields exist
            if 'canticum_idx' not in sample_lines[0]:
                print(f"Cache file {cache_file} is outdated (missing metadata). Regenerating...")
                return preprocess_and_cache_lyric_corpus(corpus_folder, cache_file)
            if 'syllables_by_responsion' not in cached_data:
                print(f"Cache file {cache_file} is outdated (missing responsion syllable metadata). Regenerating...")
                return preprocess_and_cache_lyric_corpus(corpus_folder, cache_file)
        else:
            print(f"Cache file {cache_file} has old format. Regenerating...")
            return preprocess_and_cache_lyric_corpus(corpus_folder, cache_file)
    
    return cached_data


@lru_cache(maxsize=None)
def load_external_lyric_corpus(corpus_folder: str):
    """
    Preprocess an external XML corpus once per process.

    The lyric fallback may ask the Aristophanes corpus for many different
    line lengths while building one baseline. Parsing those files on every
    miss dominates test runtime, so keep the same by-length structure used
    for the main lyric corpus in memory.
    """
    corpus_path = resolve_path(corpus_folder)
    lines_by_length = defaultdict(list)
    all_syllables = []

    if not corpus_path.exists():
        return {'lines_by_length': {}, 'all_syllables': []}

    for xml_file in sorted(f for f in os.listdir(corpus_path) if f.endswith('.xml')):
        try:
            file_path = corpus_path / xml_file
            tree = etree.parse(str(file_path))
            root = tree.getroot()
        except Exception:
            continue

        for syll in root.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]"):
            all_syllables.append(etree.tostring(syll, encoding='unicode', method='xml'))

        for canticum_idx, canticum in enumerate(root.findall(".//canticum")):
            for strophe_idx, strophe in enumerate(canticum.findall(".//strophe")):
                responsion_id = strophe.get('responsion', 'unknown')
                for line_idx, l in enumerate(strophe.findall("l")):
                    try:
                        canonical_length = len(canonical_sylls(l))
                    except Exception:
                        continue

                    lines_by_length[canonical_length].append({
                        'xml': etree.tostring(l, encoding='unicode', method='xml'),
                        'file': xml_file,
                        'canticum_idx': canticum_idx,
                        'strophe_idx': strophe_idx,
                        'line_idx': line_idx,
                        'responsion_id': responsion_id,
                    })

    return {
        'lines_by_length': dict(lines_by_length),
        'all_syllables': all_syllables,
    }
    
########################
# BASELINE AUXILIARIES #
########################

def prose_end_sample_cached(cached_corpus: dict, n_sylls: int, sample_size: int, seed=1453):
    """
    Fast version of prose_end_sample using cached preprocessed corpus.
    
    Args:
        cached_corpus: dict from load_cached_prose_corpus()
        n_sylls: number of syllables to sample
        sample_size: how many samples to return
        seed: random seed for reproducibility
        
    Returns:
        list of processed sentence strings or None if insufficient data
    """
    random.seed(seed)
    
    if n_sylls not in cached_corpus:
        print(f"Warning: No sentences with exactly {n_sylls} syllables found in cached corpus.")
        return []
    
    available_sentences = cached_corpus[n_sylls]
    
    if len(available_sentences) < sample_size:
        print(f"Warning: Only {len(available_sentences)} sentences with exactly {n_sylls} syllables found in corpus, less than requested {sample_size}.")
        return available_sentences  # Return all available sentences
    
    if len(available_sentences) >= sample_size:
        sample = random.sample(available_sentences, sample_size)  # Use sample instead of choices to avoid duplicates
        return sample
    else:
        return None

def lyric_line_sample_cached(length: int, cached_corpus: dict, seed=1453, debug=False, exclude_file=None, exclude_responsion_id=None, used_metrical_positions=None, used_responsions_this_position=None):
    """
    Fast version of lyric_line_sample using cached preprocessed corpus.
    
    Args:
        length: target canonical syllable length
        cached_corpus: dict from load_cached_lyric_corpus()
        seed: random seed for reproducibility
        debug: whether to print debug information
        exclude_file: filename to exclude from corpus sampling (to avoid contamination)
        exclude_responsion_id: responsion ID to exclude from corpus sampling (to avoid contamination)
        used_metrical_positions: set of used (file, canticum_idx, strophe_idx, line_idx) tuples
        used_responsions_this_position: set of responsion_ids already used for this line position
        
    Returns:
        XML element as string, or None if not found
    """
    random.seed(seed)
    
    lines_by_length = cached_corpus['lines_by_length']
    all_syllables = cached_corpus['all_syllables']
    
    if used_metrical_positions is None:
        used_metrical_positions = set()
    
    if used_responsions_this_position is None:
        used_responsions_this_position = set()
    
    if debug:
        print(f"Searching for lines of length {length}")
        if exclude_file:
            print(f"Excluding {exclude_file} from sampling")
        if exclude_responsion_id:
            print(f"Excluding responsion {exclude_responsion_id} from sampling")
        if used_responsions_this_position:
            print(f"Excluding responsions already used in this position: {used_responsions_this_position}")
    
    # Filter out lines from excluded file, ensure metrical independence, and responsion independence per position
    def filter_lines_with_all_independence_checks(lines_data, exclude_file, exclude_responsion_id, used_positions, used_responsions, current_position_idx):
        """
        Filter lines ensuring:
        1. Not from excluded file
        2. Statistical independence (no two lines from same metrical position)
        3. Responsion independence per line position (no same responsion_id for same relative line position)
        
        Args:
            lines_data: list of line dictionaries with metadata
            exclude_file: filename to exclude
            used_positions: set of (file, canticum_idx, strophe_idx, line_idx) tuples already used
            used_responsions: set of responsion_ids already used for this line position
            current_position_idx: the current line position we're filling (for logging)
        """
        filtered = []
        for item in lines_data:
            # Skip excluded file
            if exclude_file and item['file'] == exclude_file:
                continue

            # Skip target responsion while allowing other odes in the same corpus file
            if exclude_responsion_id and item['responsion_id'] == exclude_responsion_id:
                continue
                
            # Create position key for independence checking
            position_key = (item['file'], item['canticum_idx'], item['strophe_idx'], item['line_idx'])
            
            # Skip if we've already used a line from this exact metrical position
            if position_key in used_positions:
                continue
                
            # Skip if we've already used this responsion_id for this line position
            if item['responsion_id'] in used_responsions:
                continue
            
            filtered.append(item)
        
        return filtered
    
    # Try exact length first
    if length in lines_by_length:
        candidate_lines = filter_lines_with_all_independence_checks(
            lines_by_length[length], exclude_file, exclude_responsion_id, used_metrical_positions, used_responsions_this_position, length
        )
        if candidate_lines:
            if debug:
                print(f"Found {len(candidate_lines)} candidate lines of length {length}.")
            selected_item = random.choice(candidate_lines)
            
            # Add this position to used positions
            position_key = (selected_item['file'], selected_item['canticum_idx'], 
                          selected_item['strophe_idx'], selected_item['line_idx'])
            used_metrical_positions.add(position_key)
            
            selected_xml = selected_item['xml']
            line_element = etree.fromstring(selected_xml)
            # Add enhanced source attribute to show contamination prevention
            source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}"
            line_element.set('source', source_info)
            return line_element
    
    if debug:
        print(f"\033[93mWarning: No lines found with length {length}. Trying trimming from Pindar corpus.\033[0m")
    
    # Try length + 1 through + MAX and trim syllables (Pindar corpus)
    for extra_length in range(1, PINDAR_MAX_TRIMMING + 1):
        target_length = length + extra_length
        if target_length in lines_by_length:
            candidate_lines = filter_lines_with_all_independence_checks(
                lines_by_length[target_length], exclude_file, exclude_responsion_id, used_metrical_positions, used_responsions_this_position, length
            )
            if candidate_lines:
                if debug:
                    print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {target_length}, trimming {extra_length} syllables.\033[0m")
                
                selected_item = random.choice(candidate_lines)
                
                # Add this position to used positions
                position_key = (selected_item['file'], selected_item['canticum_idx'], 
                              selected_item['strophe_idx'], selected_item['line_idx'])
                used_metrical_positions.add(position_key)
                
                selected_xml = selected_item['xml']
                line = etree.fromstring(selected_xml)
                sylls = line.xpath(".//syll")  # Use all syllables, not just non-anceps/non-resolution
                if len(sylls) >= extra_length:
                    trimmed_sylls = sylls[:-extra_length]  # remove last syllables
                    
                    # Create new <l> element and copy attributes from original
                    new_line = etree.Element("l")
                    # Copy attributes from original line
                    for attr, value in line.attrib.items():
                        if attr != 'source':  # Don't copy source if it exists
                            new_line.set(attr, value)
                    # Add enhanced source attribute to show contamination prevention
                    source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}, trimmed -{extra_length}"
                    new_line.set('source', source_info)
                    for syll in trimmed_sylls:
                        new_line.append(syll)
                    
                    return new_line
    
    # Final fallback: search external Aristophanes corpus
    if debug:
        print(f"\033[93mTrying external Aristophanes corpus for length {length}...\033[0m")
    
    external_line = search_external_corpus_for_line(length, cached_corpus, all_syllables, exclude_file, exclude_responsion_id, used_metrical_positions, used_responsions_this_position, corpus_folder = "data/compiled/aristophanes/", debug=debug)
    if external_line is not None:
        if debug:
            print(f"\033[92mFound line of length {length} in external corpus.\033[0m")
        return external_line
    
    if debug:
        print(f"Warning: No lines found with lengths {length}, {length+1}, {length-1}, {length-2}, or in external corpus.")
    return None

def search_external_corpus_for_line(length: int, cached_corpus: dict, all_syllables: list, exclude_file: str, exclude_responsion_id: str, used_metrical_positions: set, used_responsions_this_position: set, corpus_folder: str = "data/compiled/aristophanes/", debug=False):
    """
    Search external corpus (Aristophanes' 11 plays) for lines of given length.
    This is a final fallback when the main Pindar corpus doesn't have enough lines.
    
    Args:
        length: target canonical syllable length
        cached_corpus: dict from load_cached_lyric_corpus() 
        all_syllables: list of all syllables from cached corpus
        exclude_file: filename to exclude
        exclude_responsion_id: responsion ID to exclude from internal lyric sampling
        used_metrical_positions: set of used metrical positions
        used_responsions_this_position: set of responsion_ids already used for this line position
        corpus_folder: folder containing external XML files
        debug: whether to print debug information
        
    Returns:
        XML element or None if not found
    """
    
    def filter_lines_with_all_independence_checks(lines_data, exclude_file, exclude_responsion_id, used_positions, used_responsions, current_position_idx):
        """
        Filter lines ensuring:
        1. Not from excluded file
        2. Statistical independence (no two lines from same metrical position)
        3. Responsion independence per line position (no same responsion_id for same relative line position)
        """
        filtered = []
        for item in lines_data:
            # Skip excluded file
            if exclude_file and item['file'] == exclude_file:
                continue

            # Skip target responsion while allowing sibling odes in the same XML file
            if exclude_responsion_id and item['responsion_id'] == exclude_responsion_id:
                continue
                
            # Create position key for independence checking
            position_key = (item['file'], item['canticum_idx'], item['strophe_idx'], item['line_idx'])
            
            # Skip if we've already used a line from this exact metrical position
            if position_key in used_positions:
                continue
                
            # Skip if we've already used this responsion_id for this line position
            if item['responsion_id'] in used_responsions:
                continue
            
            filtered.append(item)
        
        return filtered

    def select_external_line(target_length: int):
        candidate_lines = external_lines_by_length.get(target_length, [])
        if not candidate_lines:
            return None
        filtered_lines = filter_lines_with_all_independence_checks(
            candidate_lines, exclude_file, exclude_responsion_id, used_metrical_positions, used_responsions_this_position, target_length
        )
        if not filtered_lines:
            return None
        return random.choice(filtered_lines)

    def mark_external_line_used(selected_metadata):
        position_key = (
            selected_metadata['file'],
            selected_metadata['canticum_idx'],
            selected_metadata['strophe_idx'],
            selected_metadata['line_idx'],
        )
        used_metrical_positions.add(position_key)
        used_responsions_this_position.add(selected_metadata['responsion_id'])

    try:
        external_corpus = load_external_lyric_corpus(str(resolve_path(corpus_folder)))
        external_lines_by_length = external_corpus['lines_by_length']
        all_external_syllables = external_corpus['all_syllables']

        if not external_lines_by_length:
            if debug:
                print(f"External corpus folder {corpus_folder} not found or empty.")
            return None

        # Try exact length first
        selected_metadata = select_external_line(length)
        if selected_metadata is not None:
            if debug:
                print(f"Found candidate line of length {length} in external corpus after filtering.")

            selected_line = etree.fromstring(selected_metadata['xml'])
            source_info = f"external:{selected_metadata['responsion_id']}, strophe {selected_metadata['strophe_idx'] + 1}, line {selected_metadata['line_idx'] + 1}"
            selected_line.set('source', source_info)
            mark_external_line_used(selected_metadata)
            return selected_line

        # Try external corpus length + 1 through + MAX and trim syllables
        for extra_length in range(1, EXTERNAL_MAX_TRIMMING + 1):
            target_length = length + extra_length
            selected_metadata = select_external_line(target_length)
            if selected_metadata is None:
                continue
            if debug:
                print(f"Found candidate line of length {target_length} in external corpus, trimming {extra_length} syllables.")

            line = etree.fromstring(selected_metadata['xml'])
            sylls = line.xpath(".//syll")
            if len(sylls) < extra_length:
                continue

            new_line = etree.Element("l")
            source_info = f"external:{selected_metadata['responsion_id']}, strophe {selected_metadata['strophe_idx'] + 1}, line {selected_metadata['line_idx'] + 1}, trimmed -{extra_length}"
            new_line.set('source', source_info)
            for syll in sylls[:-extra_length]:
                new_line.append(syll)

            mark_external_line_used(selected_metadata)
            return new_line
        
        # Try Pindar corpus with padding (length - 1 through length - MAX_PADDING)
        lines_by_length = cached_corpus['lines_by_length']
        for padding_amount in range(1, PINDAR_MAX_PADDING + 1):
            target_length = length - padding_amount
            if target_length in lines_by_length:
                candidate_lines = filter_lines_with_all_independence_checks(
                    lines_by_length[target_length], exclude_file, exclude_responsion_id, used_metrical_positions, used_responsions_this_position, length
                )
                if candidate_lines:
                    if debug:
                        print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {target_length} in Pindar corpus, appending {padding_amount} random syllables.\033[0m")
                    
                    selected_item = random.choice(candidate_lines)
                    
                    # Add this position to used positions
                    position_key = (selected_item['file'], selected_item['canticum_idx'], 
                                  selected_item['strophe_idx'], selected_item['line_idx'])
                    used_metrical_positions.add(position_key)
                    
                    selected_xml = selected_item['xml']
                    line = etree.fromstring(selected_xml)
                    sylls = line.xpath(".//syll")  # Use all syllables, not just non-anceps/non-resolution
                    
                    # Filter syllables to exclude target responsion material while allowing sibling odes in the same file.
                    available_syllables = all_syllables
                    if exclude_responsion_id:
                        syllables_by_responsion = cached_corpus.get('syllables_by_responsion', {})
                        excluded_syllables = set(syllables_by_responsion.get(exclude_responsion_id, []))
                        available_syllables = [s for s in all_syllables if s not in excluded_syllables]
                    elif exclude_file:
                        syllables_by_file = cached_corpus['syllables_by_file']
                        excluded_syllables = set(syllables_by_file.get(exclude_file, []))
                        available_syllables = [s for s in all_syllables if s not in excluded_syllables]
                    
                    if available_syllables and len(available_syllables) >= padding_amount:
                        # Append the required number of random syllables
                        for i in range(padding_amount):
                            random_syllable_xml = random.choice(available_syllables)
                            random_syllable = etree.fromstring(random_syllable_xml)
                            sylls.append(random_syllable)
                    
                    # Create new <l> element and copy attributes from original
                    new_line = etree.Element("l")
                    # Copy attributes from original line
                    for attr, value in line.attrib.items():
                        if attr != 'source':  # Don't copy source if it exists
                            new_line.set(attr, value)
                    # Add enhanced source attribute to show contamination prevention
                    source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}, padded +{padding_amount}"
                    new_line.set('source', source_info)
                    for syll in sylls:
                        new_line.append(syll)
                    
                    return new_line
        
        # Try external corpus with padding (length - 1 through length - MAX_PADDING)
        for padding_amount in range(1, EXTERNAL_MAX_PADDING + 1):
            target_length = length - padding_amount
            if len(all_external_syllables) < padding_amount:
                continue
            selected_metadata = select_external_line(target_length)
            if selected_metadata is None:
                continue
            if debug:
                print(f"Found candidate line of length {target_length} in external corpus, appending {padding_amount} syllables.")

            line = etree.fromstring(selected_metadata['xml'])
            sylls = line.xpath(".//syll")
            for _ in range(padding_amount):
                random_syllable = etree.fromstring(random.choice(all_external_syllables))
                sylls.append(random_syllable)

            new_line = etree.Element("l")
            source_info = f"external:{selected_metadata['responsion_id']}, strophe {selected_metadata['strophe_idx'] + 1}, line {selected_metadata['line_idx'] + 1}, padded +{padding_amount}"
            new_line.set('source', source_info)
            for syll in sylls:
                new_line.append(syll)

            mark_external_line_used(selected_metadata)
            return new_line
            
    except Exception as e:
        if debug:
            print(f"Error searching external corpus: {e}")
    
    return None

#######
# XML #
#######

def dummy_xml_single_line(string_list: list, outfile: str):
    """
    Generate TEI XML from a list of strings, with each string in an <l> element
    nested inside its own <strophe> element.
    """
    xml_content = '''<?xml version='1.0' encoding='UTF-8'?>
<TEI>
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Baseline</title>
        <author>Prose</author>
      </titleStmt>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <canticum>
'''
    
    for i, text in enumerate(string_list, 1):
        xml_content += f'''        <strophe type="strophe" responsion="ba01">
          <l n="{i}">{text}</l>
        </strophe>
'''
    
    xml_content += '''      </canticum>
    </body>
  </text>
</TEI>'''
    
    with open(outfile, 'w', encoding='utf-8') as f:
        f.write(xml_content)

def dummy_xml_strophe(strophe_sample_lists_dict, outfile, type="Prose"):
    """
    Generate TEI XML from a dictionary of strophe lists.
    
    Args:
        strophe_sample_lists_dict: dict with responsion_id as key and list of strophe lists as value
        outfile: output file path
        type: type of baseline (default "Prose")
    """
    xml_content = f'''<?xml version='1.0' encoding='UTF-8'?>
<TEI>
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Baseline</title>
        <author>{type}</author>
      </titleStmt>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
'''
    
    for responsion_id, strophe_sample_lists in strophe_sample_lists_dict.items():
        xml_content += f'''      <canticum>
'''
        
        index = 1
        for strophe_sample_list in strophe_sample_lists:
            xml_content += f'''        <strophe type="strophe" responsion="{responsion_id}">
'''
            
            for line in strophe_sample_list:
                # Parse the line to extract syllable content and source attribute
                try:
                    line_element = etree.fromstring(line)
                    # Extract source attribute if present
                    source_attr = line_element.get('source', '')
                    source_part = f' source="{source_attr}"' if source_attr else ''
                    
                    # Extract all syllable elements as strings
                    syll_content = ""
                    for syll in line_element.xpath(".//syll"):
                        syll_str = etree.tostring(syll, encoding='unicode', method='xml')
                        syll_content += syll_str
                    
                    xml_content += f'''          <l n="{index}"{source_part}>{syll_content}</l>
'''
                except etree.XMLSyntaxError:
                    # Fallback for malformed XML - just use the content as-is
                    xml_content += f'''          <l n="{index}">{line}</l>
'''
                index += 1

            xml_content += '''        </strophe>
'''
        
        xml_content += '''      </canticum>
'''
    
    xml_content += '''    </body>
  </text>
</TEI>'''
    
    with open(outfile, 'w', encoding='utf-8') as f:
        f.write(xml_content)

###################
# SHAPE AUX       #
###################

def get_shape(xml_filepath):
    '''
    Prepare for making a text matrix overlay on a heatmap.
    '''
    # Load XML
    tree = etree.parse(xml_filepath)
    root = tree.getroot()

    # Get first <strophe>, because the all have the same shape
    first_strophe = root.find(".//strophe[1]")

    text_matrix = []

    # Iterate over <l> children
    for l in first_strophe.findall("l"):
        line_sylls = []
        buffer = ""
        prev_resolved = False
        
        for syll in l.findall("syll"):
            resolved = syll.get("resolution") == "True"
            content = syll.text or ""
            
            if prev_resolved and resolved:
                # join with previous
                buffer += content
            else:
                # flush previous buffer if any
                if buffer:
                    line_sylls.append(buffer)
                buffer = content
            
            prev_resolved = resolved
        
        # Append any remaining buffer
        if buffer:
            line_sylls.append(buffer)
        
        text_matrix.append(line_sylls)

    row_lengths = [len(row) for row in text_matrix]
    
    return row_lengths

def get_shape_canticum(xml_filepath: str, responsion_id: str) -> list:
    '''
    Prepare for making a text matrix overlay on a heatmap.

    Returns a list of ints like:
    [11, 23, 20, 15, ... ]
    representing the number of canonical syllables per line in the strophe with given responsion_id.
    '''
    # Load XML
    tree = etree.parse(xml_filepath)
    root = tree.getroot()

    # Get first <strophe> with matching responsion attribute
    first_strophe = root.find(f".//strophe[@responsion='{responsion_id}']")

    text_matrix = []

    # Iterate over <l> children
    for l in first_strophe.findall("l"):
        line_sylls = []
        buffer = ""
        prev_resolved = False
        
        for syll in l.findall("syll"):
            resolved = syll.get("resolution") == "True"
            content = syll.text or ""
            
            if prev_resolved and resolved:
                # join with previous
                buffer += content
            else:
                # flush previous buffer if any
                if buffer:
                    line_sylls.append(buffer)
                buffer = content
            
            prev_resolved = resolved
        
        # Append any remaining buffer
        if buffer:
            line_sylls.append(buffer)
        
        text_matrix.append(line_sylls)

    row_lengths = [len(row) for row in text_matrix]
    
    return row_lengths
