#!/usr/bin/env python3

# Copyright © Albin Ruben Johannes Thörn Cleland 2025, Lunds universitet, albin.thorn_cleland@klass.lu.se
# https://orcid.org/0009-0003-3731-4038
# This file is part of aristophanis-cantica, licensed under the GNU General Public License v3.0.
# See the LICENSE file in the project root for full details.

"""
To cut to the chase, just use 

    barys_oxys_metric_canticum(responsion) 
    
to get a dict with the barys, oxys and barys + oxys metrics 
for all strophes with a given responsion attribute.

Sections:
- BARYS AND OXYS ACCENT DEFINITIONS
- COUNT BARYS AND OXYS ACCENTS (REGARDLESSS OF RESPONSION)
- BARYS RESPONSION
- OXYS RESPONSION
- HELPER FOR PRINTING BARYS / OXYS TEXT
- PER-LINE FUNCTION
- PER-STROPHE FUNCTION
- THE BARYS OXYS METRIC

"""

import argparse
from collections import defaultdict
from lxml import etree
import os
from pathlib import Path

from grc_utils import normalize_word

from .stats import (
    polystrophic,
    metrically_responding_lines_polystrophic,
    build_units_for_accent,
    is_heavy,
    has_acute,
    accents
)

# ------------------------------------------------------------------------
# BARYS AND OXYS ACCENT DEFINITIONS
# ------------------------------------------------------------------------


def has_circumflex(syll):
    """
    Returns True if the given syll element has a circumflex accent.
    """
    text = syll.text or ""
    norm = normalize_word(text)
    return any(ch in accents['circumflex'] for ch in norm)


def next_syll_is_light_or_none(curr_syll, all_sylls):
    """
    Returns True if 'curr_syll' is the last in its line
    OR the next syllable is weight="light".
    """
    try:
        idx = all_sylls.index(curr_syll)
    except ValueError:
        return False

    # If it's the last syllable in the line
    if idx == len(all_sylls) - 1:
        return True

    # Otherwise check if next is light
    nxt = all_sylls[idx + 1]
    return (nxt.get('weight') == 'light')


def barys_accent(syll, prev_syll):
    is_circumflex = has_circumflex(syll)
    is_heavy_with_prev_acute = (
        is_heavy(syll) and 
        prev_syll is not None and 
        has_acute(prev_syll)
    )

    return bool(is_circumflex or is_heavy_with_prev_acute)


def oxys_accent(syll, line_sylls):
    return bool(has_acute(syll) and next_syll_is_light_or_none(syll, line_sylls))


# ------------------------------------------------------------------------
# COUNT BARYS AND OXYS ACCENTS (REGARDLESSS OF RESPONSION)
# ------------------------------------------------------------------------


def count_all_barys_oxys(tree) -> dict:
    """
    Count all syllables that satisfy barys or oxys criteria, regardless of matching.
    """
    counts = {
        'barys': 0,
        'oxys': 0
    }
    
    all_sylls = tree.findall('.//syll')
    
    for i, syll in enumerate(all_sylls):

        line = syll.getparent()
        line_sylls = line.findall('.//syll')
        prev_syll = None if i == 0 else all_sylls[i-1]
        
        if barys_accent(syll, prev_syll):
            counts['barys'] += 1
            
        # Oxys accent
        if oxys_accent(syll, line_sylls):
            counts['oxys'] += 1
    
    return counts


def count_all_barys_oxys_canticum(tree, responsion=None) -> dict:
    counts = {
        'barys': 0,
        'oxys': 0
    }

    all_sylls = []
    if responsion:
        all_sylls = tree.xpath(f'(//strophe[@responsion="{responsion}"] | //antistrophe[@responsion="{responsion}"])//syll')
    else:
        all_sylls = tree.findall('.//syll')

    for i, syll in enumerate(all_sylls):

        line = syll.getparent()
        line_sylls = line.findall('.//syll')
        
        prev_syll = None if i == 0 else all_sylls[i-1]
        
        # Barys accent
        is_circumflex = has_circumflex(syll)
        is_heavy_with_prev_acute = (
            is_heavy(syll) and 
            prev_syll is not None and 
            has_acute(prev_syll)
        )
        if is_circumflex or is_heavy_with_prev_acute:
            counts['barys'] += 1
            
        # Oxys accent
        if has_acute(syll) and next_syll_is_light_or_none(syll, line_sylls):
            counts['oxys'] += 1
    
    return counts


# ------------------------------------------------------------------------
# BARYS RESPONSION
# ------------------------------------------------------------------------


def barys_responsion(syll1, syll2, prev_syll1=None, prev_syll2=None):
    """
    Returns True if these two single syllables respond "barys":
      (1) both have circumflex, OR
      (2) both are heavy & each's preceding syllable has an acute, OR
      (3) one has circumflex & the other meets #2
    """
    c1 = has_circumflex(syll1)
    c2 = has_circumflex(syll2)
    h1 = is_heavy(syll1)
    h2 = is_heavy(syll2)

    prev_acute_1 = (prev_syll1 is not None) and has_acute(prev_syll1)
    prev_acute_2 = (prev_syll2 is not None) and has_acute(prev_syll2)

    # (1) both circumflex
    if c1 and c2:
        return True

    # (2) both heavy & each's preceding syll has an acute
    if h1 and h2 and prev_acute_1 and prev_acute_2:
        return True

    # (3) one has circumflex, the other meets #2
    meets_2_for_syll1 = (h1 and prev_acute_1)
    meets_2_for_syll2 = (h2 and prev_acute_2)
    if (c1 and meets_2_for_syll2) or (c2 and meets_2_for_syll1):
        return True

    return False


# ------------------------------------------------------------------------
# OXYS RESPONSION
# ------------------------------------------------------------------------


def oxys_responsion_single_syllables(s_syll, a_syll, all_sylls_1, all_sylls_2):
    """
    Two single syllables respond "oxys" iff each:
      1) has an acute
      2) is last or followed by a light syllable
    """
    if not has_acute(s_syll):
        return False
    if not has_acute(a_syll):
        return False

    if not next_syll_is_light_or_none(s_syll, all_sylls_1):
        return False
    if not next_syll_is_light_or_none(a_syll, all_sylls_2):
        return False

    return True


# ------------------------------------------------------------------------
# HELPER FOR PRINTING BARYS / OXYS TEXT
# ------------------------------------------------------------------------


def get_barys_print_text(curr_syll, prev_syll):
    """
    For barys: if curr_syll has a circumflex, we just return it.
    If barys is from heavy+acute logic => prepend prev_syll's text.
    """
    if has_circumflex(curr_syll):
        return curr_syll.text or ""
    else:
        if prev_syll is not None:
            return (prev_syll.text or "") + (curr_syll.text or "")
        else:
            return curr_syll.text or ""


def get_oxys_print_text(curr_syll, next_syll):
    """
    For oxys: we want to append the next syllable's text if it exists.
    So e.g. "ἄξ" + "ε" => "ἄξε".
    """
    if curr_syll is None:
        return ""

    curr_text = curr_syll.text or ""
    if next_syll is None:
        return curr_text

    next_text = next_syll.text or ""
    return curr_text + next_text


# ------------------------------------------------------------------------
# PER-LINE RESPONSION
# ------------------------------------------------------------------------


def barys_accentually_responding_syllables_of_lines(*lines):
    """
    Processes barys and oxys responsion for any number of metrically responding lines.

    Parameters:
    *lines: Variable number of <l> elements (lines).

    Returns:
    list: [barys_list, oxys_list], or False if mismatch.
    """
    if not metrically_responding_lines_polystrophic(*lines):
        print(f"Lines {[line.get('n') for line in lines]} do not metrically respond.")
        return False

    # Build accent units for each line
    all_units = []
    for line in lines:
        line_units = build_units_for_accent(line)
        for unit in line_units:
            unit['line'] = line  # Attach the `line` key
        all_units.append(line_units)

    # Ensure all lines have the same number of units
    unit_counts = [len(units) for units in all_units]
    if len(set(unit_counts)) > 1:
        print(f"Unit count mismatch across lines {[line.get('n') for line in lines]}.")
        return False

    barys_list = []
    oxys_list = []

    # Process units at each index across all lines
    for unit_idx in range(unit_counts[0]):
        units = [units_list[unit_idx] for units_list in all_units]

        # Get full syllable lists for each line
        all_syll_lists = [unit['line'].findall('.//syll') for unit in units]

        # Retrieve syllables, previous syllables, and next syllables
        sylls = [u['syll'] if u['type'] == 'single' else u['syll2'] for u in units]
        prev_sylls = []
        next_sylls = []

        for u, syll_list, syll in zip(units, all_syll_lists, sylls):
            try:
                idx = syll_list.index(syll)
                prev_sylls.append(syll_list[idx - 1] if idx > 0 else None)
                next_sylls.append(syll_list[idx + 1] if idx < len(syll_list) - 1 else None)
            except ValueError:
                prev_sylls.append(None)
                next_sylls.append(None)

        # Check for barys responsion
        if all(barys_responsion(syll, sylls[0], prev_syll, prev_sylls[0]) for syll, prev_syll in zip(sylls, prev_sylls)):
            barys_list.append({
                (u['line_n'], u['unit_ord']): get_barys_print_text(syll, prev_syll)
                for u, syll, prev_syll in zip(units, sylls, prev_sylls)
            })

        # Check for oxys responsion
        if all(oxys_responsion_single_syllables(syll, sylls[0], u['line'].findall('.//syll'), units[0]['line'].findall('.//syll')) for syll, u in zip(sylls, units)):
            oxys_list.append({
                (u['line_n'], u['unit_ord']): get_oxys_print_text(syll, next_syll)
                for u, syll, next_syll in zip(units, sylls, next_sylls)
            })

    return [barys_list, oxys_list]


# ------------------------------------------------------------------------
# PER-STROPHE RESPONSION
# ------------------------------------------------------------------------


def barys_accentually_responding_syllables_of_strophes_polystrophic(*strophes):
    """
    Processes barys and oxys responsion for any number of strophes.

    Parameters:
    *strophes: Variable number of <strophe> elements.

    Returns:
    list: [barys_list, oxys_list], or False if mismatch.
    """
    # Ensure all strophes share the same responsion
    responsions = {strophe.get('responsion') for strophe in strophes}
    if len(responsions) != 1:
        print(f"Strophes have mismatched responsions: {responsions}")
        return False

    # Extract lines from each strophe
    strophe_lines = [strophe.findall('l') for strophe in strophes]

    # Ensure all strophes have the same number of lines
    line_counts = [len(lines) for lines in strophe_lines]
    if len(set(line_counts)) > 1:
        print(f"Line count mismatch across strophes: {line_counts}")
        return False

    combined_barys = []
    combined_oxys = []

    # Process each line group across all strophes
    for line_group in zip(*strophe_lines):  # Transpose the line matrix
        # Evaluate responsion for the current line group
        line_barys_oxys = barys_accentually_responding_syllables_of_lines(*line_group)
        if line_barys_oxys is False:
            print(f"Lines {[line.get('n') for line in line_group]} do not metrically respond.")
            return False

        combined_barys.extend(line_barys_oxys[0])
        combined_oxys.extend(line_barys_oxys[1])

    return [combined_barys, combined_oxys]


# ------------------------------------------------------------------------
# THE BARYS OXYS METRIC
# ------------------------------------------------------------------------

def barys_oxys_metric_canticum(responsion, baseline=False) -> dict:
    """
    Takes a canticum id and returns a dict with the barys and oxys metrics.
    """
    results = {}

    infix = responsion[:-2]

    if baseline:
        input_file = f"data/compiled/baseline/responsion_{infix}_compiled.xml"
    else:
        input_file = f"data/compiled/responsion_{infix}_compiled.xml"
    tree = etree.parse(input_file)
            
    all_barys_oxys_canticum_dict = count_all_barys_oxys_canticum(tree, responsion)

    sum_barys = all_barys_oxys_canticum_dict['barys']
    sum_oxys = all_barys_oxys_canticum_dict['oxys']
    sum_barys_oxys = sum_barys + sum_oxys

    strophes = tree.xpath(f'//strophe[@responsion="{responsion}"] | //antistrophe[@responsion="{responsion}"]') # bug fix (was only strophe)
    n = len(strophes)

    barys_oxys_results = barys_accentually_responding_syllables_of_strophes_polystrophic(*strophes)

    if not barys_oxys_results:
        print("No valid barys/oxys matches found.\n")

    barys_list, oxys_list = barys_oxys_results
    barys_matches = len(barys_list)
    oxys_matches = len(oxys_list)

    barys_metric = (n * barys_matches) / sum_barys if sum_barys > 0 else 0
    oxys_metric = (n * oxys_matches) / sum_oxys if sum_oxys > 0 else 0
    barys_oxys_metric = (n * (len(barys_list) + len(oxys_list))) / sum_barys_oxys if sum_barys_oxys > 0 else 0

    results = {
        'barys_metric': barys_metric,
        'oxys_metric': oxys_metric,
        'barys_oxys_metric': barys_oxys_metric,
    }
    return results

def barys_oxys_metric_play(responsion, debug=False, baseline=False) -> dict:
    """
    Takes an XML file and returns a dict with the barys and oxys metrics.
    """
    results = {}

    if baseline:
        input_file = f"data/compiled/baseline/responsion_{responsion}_compiled.xml"
    else:
        input_file = f"data/compiled/responsion_{responsion}_compiled.xml"
    tree = etree.parse(input_file)
    
    all_barys_oxys_dict = count_all_barys_oxys(tree)

    sum_barys = all_barys_oxys_dict['barys']
    sum_oxys = all_barys_oxys_dict['oxys']
    sum_barys_oxys = sum_barys + sum_oxys
    if debug:
        print(f"Total Barys: {sum_barys}, Total Oxys: {sum_oxys}, Total Barys+Oxys: {sum_barys_oxys}")

    strophes = tree.xpath(f'//strophe | //antistrophe')

    cantica = defaultdict(list)
    for s in strophes:
        key = s.get('responsion')
        if key:
            cantica[key].append(s)

    barys_matches = 0
    oxys_matches = 0

    for responsion_value, responding_strophes in cantica.items():
        
        n = len(responding_strophes)

        barys_oxys_results = barys_accentually_responding_syllables_of_strophes_polystrophic(*responding_strophes)
        barys_list, oxys_list = barys_oxys_results

        barys_matches += n * len(barys_list)
        oxys_matches += n * len(oxys_list)

    barys_metric = barys_matches / sum_barys if sum_barys > 0 else 0
    oxys_metric = oxys_matches / sum_oxys if sum_oxys > 0 else 0
    barys_oxys_metric = (barys_matches + oxys_matches) / sum_barys_oxys if sum_barys_oxys > 0 else 0

    results = {
        'barys_metric': barys_metric,
        'oxys_metric': oxys_metric,
        'barys_oxys_metric': barys_oxys_metric,
    }
    return results

def barys_oxys_metric_corpus(folder="data/compiled/", exclude_substr="baseline") -> dict:
    """
    Takes a folder of XML files and returns a dict with the barys, oxys and barys_oxys metrics.
    """
    results = {}

    sum_barys = 0
    sum_oxys = 0
    sum_barys_oxys = 0
    
    barys_matches = 0
    oxys_matches = 0

    for xml_file in os.listdir(folder):
        if not xml_file.endswith('.xml'):
            continue
        if exclude_substr and exclude_substr in xml_file:
            continue
        
        folder_path = Path(folder)
        filepath = folder_path / xml_file
        
        tree = etree.parse(filepath)
        strophes = tree.xpath('//strophe | //antistrophe')

        # Total for play

        all_barys_oxys_dict = count_all_barys_oxys(tree) # Total for the play

        sum_barys += all_barys_oxys_dict['barys']
        sum_oxys += all_barys_oxys_dict['oxys']
        sum_barys_oxys += all_barys_oxys_dict['barys'] + all_barys_oxys_dict['oxys']


        cantica = defaultdict(list)
        for s in strophes:
            key = s.get('responsion')
            if key:
                cantica[key].append(s)

        for responsion_value, responding_strophes in cantica.items():
            n = len(responding_strophes)

            barys_oxys_results = barys_accentually_responding_syllables_of_strophes_polystrophic(*responding_strophes)
            barys_list, oxys_list = barys_oxys_results

            barys_matches += n * len(barys_list)
            oxys_matches += n * len(oxys_list)

    barys_metric = barys_matches / sum_barys if sum_barys > 0 else 0
    oxys_metric = oxys_matches / sum_oxys if sum_oxys > 0 else 0
    barys_oxys_metric = (barys_matches + oxys_matches) / sum_barys_oxys if sum_barys_oxys > 0 else 0

    print(f"Total barys matches in corpus: {barys_matches}, Oxys matches: {oxys_matches}")

    results = {
        'barys_metric': barys_metric,
        'oxys_metric': oxys_metric,
        'barys_oxys_metric': barys_oxys_metric,
    }
    return results

# ------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------


if __name__ == "__main__":

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Analyze responsion statistics for a play.")
    parser.add_argument("infix", help="Infix of the play file (e.g., 'ach' for 'responsion_ach_compiled.xml').")
    args = parser.parse_args()

    input_file = f"data/compiled/responsion_{args.infix}_compiled.xml"

    # Parse the XML tree
    tree = etree.parse(input_file)

    # Get all unique responsion numbers
    responsion_numbers = set(
        strophe.get("responsion")
        for strophe in tree.xpath('//strophe[@type="strophe"]')
    )

    # Process each responsion
    for responsion in sorted(responsion_numbers):
        print(f"\nCanticum: {responsion}")

        # Determine if the canticum is polystrophic
        if polystrophic(tree, responsion):
            print("Polystrophic: Yes")

            # Get all strophes for the responsion
            strophes = tree.xpath(f'//strophe[@responsion="{responsion}"]')

            # Use updated polystrophic processing
            barys_oxys_results = barys_accentually_responding_syllables_of_strophes_polystrophic(*strophes)

            if not barys_oxys_results:
                print("No valid barys/oxys matches found.\n")
                continue  # Skip to next responsion if no results

            barys_list, oxys_list = barys_oxys_results

            print(f"Barys matches: {len(barys_list)}")
            print(f"Oxys matches:  {len(oxys_list)}\n")

            # Detailed printing for polystrophic matches
            if barys_list:
                print("--- BARYS MATCHES ---")
                for match_idx, match_set in enumerate(barys_list, start=1):
                    print(f"  Match #{match_idx}:")
                    for (line_id, unit_ord), text in match_set.items():
                        print(f"    (line {line_id}, ord={unit_ord}) => \"{text}\"")
                    print()

            if oxys_list:
                print("--- OXYS MATCHES ---")
                for match_idx, match_set in enumerate(oxys_list, start=1):
                    print(f"  Match #{match_idx}:")
                    for (line_id, unit_ord), text in match_set.items():
                        print(f"    (line {line_id}, ord={unit_ord}) => \"{text}\"")
                    print()

        else:
            print("Polystrophic: No")

            # Get the first strophe and antistrophe for non-polystrophic processing
            strophes = tree.xpath(f'//strophe[@type="strophe" and @responsion="{responsion}"]')
            antistrophes = tree.xpath(f'//strophe[@type="antistrophe" and @responsion="{responsion}"]')

            # Process the first strophe and antistrophe pair
            if strophes and antistrophes:
                barys_oxys_results = barys_accentually_responding_syllables_of_strophes_polystrophic(strophes[0], antistrophes[0])
            else:
                barys_oxys_results = [[], []]  # No valid pairs

            if not barys_oxys_results:
                print("No valid barys/oxys matches found.\n")
                continue  # Skip to next responsion if no results

            barys_list, oxys_list = barys_oxys_results

            print(f"Barys matches: {len(barys_list)}")
            print(f"Oxys matches:  {len(oxys_list)}\n")

            # Detailed printing for non-polystrophic
            if barys_list:
                print("--- BARYS MATCHES ---")
                for i, pair_dict in enumerate(barys_list, start=1):
                    print(f"  Pair #{i}:")
                    for (line_id, unit_ord), text in pair_dict.items():
                        print(f"    (line {line_id}, ord={unit_ord}) => \"{text}\"")
                    print()

            if oxys_list:
                print("--- OXYS MATCHES ---")
                for i, pair_dict in enumerate(oxys_list, start=1):
                    print(f"  Pair #{i}:")
                    for (line_id, unit_ord), text in pair_dict.items():
                        print(f"    (line {line_id}, ord={unit_ord}) => \"{text}\"")
                    print()