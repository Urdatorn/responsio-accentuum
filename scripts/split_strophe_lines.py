"""
Split each TEI strophe into a strophe/antistrophe pair.

For every <strophe>, the last five direct <l> children are moved into a new
following <strophe>. The first of those moved lines is then removed so the
original and newly-created strophes have the same number of lines. Finally,
all sibling strophes are renumbered in document order via their n attributes.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

from lxml import etree


def local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def direct_line_children(strophe: etree._Element) -> list[etree._Element]:
    return [child for child in strophe if local_name(child) == "l"]


def renumber_sibling_strophes(parent: etree._Element) -> None:
    n = 1
    for child in parent:
        if local_name(child) == "strophe":
            child.attrib["n"] = str(n)
            n += 1


def split_strophes(tree: etree._ElementTree, split_count: int = 5) -> int:
    if split_count < 2:
        raise ValueError("split_count must be at least 2 so one moved line can be dropped")

    root = tree.getroot()
    original_strophes = [element for element in root.iter() if local_name(element) == "strophe"]
    split_total = 0

    for strophe in original_strophes:
        parent = strophe.getparent()
        if parent is None:
            raise ValueError("Cannot split a root <strophe> without a parent element")

        lines = direct_line_children(strophe)
        if len(lines) < split_count:
            raise ValueError(
                f"Strophe n={strophe.attrib.get('n', '<missing>')} has only "
                f"{len(lines)} direct <l> children; need at least {split_count}"
            )

        moved_lines = lines[-split_count:]
        original_tail = strophe.tail
        closing_tail = moved_lines[-1].tail
        sibling_tail = strophe.text[:-2] if strophe.text and strophe.text.endswith("  ") else strophe.tail
        new_strophe = deepcopy(strophe)
        for child in list(new_strophe):
            new_strophe.remove(child)

        for line in moved_lines:
            strophe.remove(line)

        remaining_lines = direct_line_children(strophe)
        if remaining_lines:
            remaining_lines[-1].tail = closing_tail

        # The first moved line marks the strophe/antistrophe boundary and is
        # intentionally omitted from the newly-created strophe.
        for line in moved_lines[1:]:
            new_strophe.append(line)

        strophe.tail = sibling_tail
        new_strophe.tail = original_tail
        parent.insert(parent.index(strophe) + 1, new_strophe)
        split_total += 1

    parents = {strophe.getparent() for strophe in root.iter() if local_name(strophe) == "strophe"}
    for parent in parents:
        if parent is not None:
            renumber_sibling_strophes(parent)

    return split_total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Split each TEI <strophe> by moving its last five <l> elements into "
            "a new following strophe, dropping the first moved line, and "
            "renumbering strophe/@n."
        )
    )
    parser.add_argument("input", type=Path, help="Source TEI XML file")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Output TEI XML file; defaults to INPUT stem plus '_split.xml'",
    )
    parser.add_argument(
        "--split-count",
        type=int,
        default=5,
        help="Number of trailing <l> elements to move before dropping the first one",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input
    output_path = args.output or input_path.with_name(f"{input_path.stem}_split.xml")

    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(input_path), parser)
    split_total = split_strophes(tree, split_count=args.split_count)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(
        str(output_path),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=False,
    )
    print(f"Split {split_total} strophes into {split_total * 2} strophes: {output_path}")


if __name__ == "__main__":
    main()
