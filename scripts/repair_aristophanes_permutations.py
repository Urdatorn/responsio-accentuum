"""
Repair Aristophanes permutation XMLs after an interrupted/shifted generation run.

The notebook generator used to skip existing files without advancing the RNG.
If a zero-byte file was later regenerated, all following files in that directory
could be rewritten as duplicates of earlier permutations. This script overwrites
a selected inclusive range while advancing the RNG from permutation 1, so the
regenerated files again match their intended indices.
"""

from __future__ import annotations

import argparse
import random
import re
from pathlib import Path

from lxml import etree
from tqdm import tqdm


def find_project_root(start: Path, markers=("pyproject.toml", ".git")):
    for p in [start] + list(start.parents):
        if any((p / m).exists() for m in markers):
            return p
    raise RuntimeError("Project root not found")


ROOT = find_project_root(Path.cwd())
BASELINE_DIR = ROOT / "data" / "compiled" / "baselines" / "baseline_aristophanes"
TEMP_DIR = BASELINE_DIR / "temp_permutations"

canticum_re = re.compile(r"(<canticum\b[^>]*>)(.*?)(</canticum>)", re.S)
strophe_re = re.compile(r"(<strophe\b[^>]*>)(.*?)(</strophe>)", re.S)


def parse_source_key_from_l_line(l_line: str) -> tuple[str, int] | None:
    m = re.search(r'\bn="([^"]+)"', l_line)
    if not m:
        return None
    parts = m.group(1).split("_")
    if len(parts) < 2:
        return None
    try:
        return parts[0], int(parts[1].split("-")[1])
    except Exception:
        return None


def extract_strophe_structures(canticum_body: str):
    structures = []
    for sm in strophe_re.finditer(canticum_body):
        strophe_open, strophe_body, strophe_close = sm.groups()
        lines = strophe_body.splitlines(keepends=True)
        l_indices = [i for i, line in enumerate(lines) if re.search(r"<l\b", line)]
        structures.append(
            {
                "open": strophe_open,
                "close": strophe_close,
                "lines": lines,
                "l_indices": l_indices,
            }
        )
    return structures


def tetrameter_constraint_holds(text: str) -> bool:
    for c_match in canticum_re.finditer(text):
        strophes = extract_strophe_structures(c_match.group(2))
        max_positions = max((len(s["l_indices"]) for s in strophes), default=0)
        for pos_idx in range(max_positions):
            seen_keys = set()
            for s in strophes:
                if pos_idx >= len(s["l_indices"]):
                    continue
                l_line = s["lines"][s["l_indices"][pos_idx]]
                key = parse_source_key_from_l_line(l_line)
                if key is None:
                    continue
                if key in seen_keys:
                    return False
                seen_keys.add(key)
    return True


def shuffle_strophe_lines(strophe_body: str, rng: random.Random) -> str:
    lines = strophe_body.splitlines(keepends=True)
    l_indices = [i for i, line in enumerate(lines) if re.search(r"<l\b", line)]
    if len(l_indices) <= 1:
        return strophe_body
    l_lines = [lines[i] for i in l_indices]
    rng.shuffle(l_lines)
    for idx, new_line in zip(l_indices, l_lines):
        lines[idx] = new_line
    return "".join(lines)


def permute_tetrameter_once(text: str, rng: random.Random, max_attempts: int = 200) -> str:
    canticum_structs = []
    all_l_lines = []

    for c_match in canticum_re.finditer(text):
        c_open, c_body, c_close = c_match.groups()
        strophes = extract_strophe_structures(c_body)
        for s in strophes:
            for li in s["l_indices"]:
                all_l_lines.append(s["lines"][li])
        canticum_structs.append(
            {
                "open": c_open,
                "close": c_close,
                "body": c_body,
                "strophes": strophes,
            }
        )

    if len(all_l_lines) <= 1:
        return text

    source_keys = [parse_source_key_from_l_line(l) for l in all_l_lines]
    slots = [
        (c_idx, s_idx, pos_idx)
        for c_idx, c in enumerate(canticum_structs)
        for s_idx, s in enumerate(c["strophes"])
        for pos_idx in range(len(s["l_indices"]))
    ]

    for _ in range(max_attempts):
        remaining = list(range(len(all_l_lines)))
        rng.shuffle(remaining)
        used_source_keys = {}
        assignment = {}
        success = True

        for c_idx, s_idx, pos_idx in slots:
            group_used = used_source_keys.setdefault((c_idx, pos_idx), set())
            chosen_pos = None
            for rem_i, pool_idx in enumerate(remaining):
                src_key = source_keys[pool_idx]
                if src_key is not None and src_key in group_used:
                    continue
                chosen_pos = rem_i
                break
            if chosen_pos is None:
                success = False
                break
            chosen_pool_idx = remaining.pop(chosen_pos)
            assignment[(c_idx, s_idx, pos_idx)] = chosen_pool_idx
            src_key = source_keys[chosen_pool_idx]
            if src_key is not None:
                group_used.add(src_key)

        if not success:
            continue

        for (c_idx, s_idx, pos_idx), pool_idx in assignment.items():
            s = canticum_structs[c_idx]["strophes"][s_idx]
            s["lines"][s["l_indices"][pos_idx]] = all_l_lines[pool_idx]

        rebuilt_canticum_texts = []
        for c in canticum_structs:
            rebuilt_strophes = [
                s["open"] + "".join(s["lines"]) + s["close"]
                for s in c["strophes"]
            ]
            rebuilt_iter = iter(rebuilt_strophes)
            new_body = strophe_re.sub(lambda _m: next(rebuilt_iter), c["body"])
            rebuilt_canticum_texts.append(c["open"] + new_body + c["close"])

        c_iter = iter(rebuilt_canticum_texts)
        new_text = canticum_re.sub(lambda _m: next(c_iter), text)
        if not tetrameter_constraint_holds(new_text):
            raise AssertionError("Tetrameter anti-responsion constraint violated")
        return new_text

    raise RuntimeError("Could not find a tetrameter permutation satisfying constraints")


def permute_text_once(text: str, rng: random.Random, flavour: str) -> str:
    if flavour == "tetrameter":
        return permute_tetrameter_once(text, rng)

    def repl(match):
        open_tag, body, close_tag = match.groups()
        return open_tag + shuffle_strophe_lines(body, rng) + close_tag

    return strophe_re.sub(repl, text)


def write_xml_atomically(path: Path, text: str):
    if not text.strip():
        raise ValueError(f"Refusing to write empty XML: {path}")
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    try:
        etree.parse(str(tmp_path))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    tmp_path.replace(path)


def repair_range(stem: str, start: int, stop: int, seed: int):
    flavour = "tetrameter" if stem.startswith("tetrameter") else "trimeter"
    source_path = BASELINE_DIR / f"{stem}.xml"
    output_dir = TEMP_DIR / stem
    text = source_path.read_text(encoding="utf-8")
    rng = random.Random(seed)

    for i in tqdm(range(1, stop + 1), desc=stem):
        permuted = permute_text_once(text, rng, flavour)
        if i < start:
            continue
        write_xml_atomically(output_dir / f"{stem}_perm_{i:05d}.xml", permuted)


def parse_args():
    parser = argparse.ArgumentParser(description="Repair shifted Aristophanes permutation XMLs.")
    parser.add_argument("--seed", type=int, default=1453)
    parser.add_argument(
        "--range",
        dest="ranges",
        action="append",
        nargs=3,
        metavar=("STEM", "START", "STOP"),
        help="Inclusive repair range, e.g. --range tetrameter_3 45565 100000",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    ranges = args.ranges or [
        ("tetrameter_3", "45565", "100000"),
        ("trimeter_5", "52480", "120000"),
    ]
    for stem, start, stop in ranges:
        repair_range(stem, int(start), int(stop), args.seed)


if __name__ == "__main__":
    main()
