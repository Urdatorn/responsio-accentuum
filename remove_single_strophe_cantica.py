#!/usr/bin/env python3

"""Remove cantica with only one strophe and report their responsion IDs.

This script scans all XML files under data/compiled/{triads,strophes,epodes},
removes cantica that have only one strophe, and overwrites the files.
It prints the responsion IDs it removed per file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
from lxml import etree

ROOT = Path(__file__).resolve().parent


def find_single_strophe_responsions(tree: etree._ElementTree) -> Dict[str, int]:
    """Return responsion counts and collect those with only one strophe."""
    root = tree.getroot()
    counts: Dict[str, int] = {}
    for strophe in root.xpath('//strophe[@responsion]'):
        resp = strophe.get('responsion')
        if resp:
            counts[resp] = counts.get(resp, 0) + 1
    return counts


def remove_single_strophe_cantica(input_path: Path) -> List[str]:
    tree = etree.parse(str(input_path))
    root = tree.getroot()

    counts = find_single_strophe_responsions(tree)
    singletons = {resp for resp, count in counts.items() if count == 1}

    if not singletons:
        return []

    # Remove strophes that belong to singleton responsions
    for strophe in root.xpath('//strophe[@responsion]'):
        resp = strophe.get('responsion')
        if resp in singletons:
            parent = strophe.getparent()
            parent.remove(strophe)

    # Drop empty canticum elements
    for canticum in root.xpath('//canticum'):
        if len(canticum.findall('strophe')) == 0:
            parent = canticum.getparent()
            parent.remove(canticum)

    # Overwrite input file
    tree.write(str(input_path), encoding='utf-8', xml_declaration=True, pretty_print=True)

    return sorted(singletons)


def process_all_compiled():
    bases = [ROOT / "data/compiled/epodes", ROOT / "data/compiled/strophes", ROOT / "data/compiled/triads"]
    for base in bases:
        if not base.exists():
            continue
        xml_files = sorted(p for p in base.glob("*.xml") if p.is_file())
        for xml_file in xml_files:
            removed = remove_single_strophe_cantica(xml_file)
            if removed:
                print(f"{xml_file}: removed single-strophe responsions: {', '.join(removed)}")
            else:
                print(f"{xml_file}: no single-strophe responsions")


if __name__ == '__main__':
    process_all_compiled()
