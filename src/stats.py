#!/usr/bin/env python3

# Copyright © Albin Ruben Johannes Thörn Cleland 2025, Lunds universitet, albin.thorn_cleland@klass.lu.se
# https://orcid.org/0009-0003-3731-4038
# This file is part of aristophanis-cantica, licensed under the GNU General Public License v3.0.
# See the LICENSE file in the project root for full details.

from collections import defaultdict
import logging
import os
from lxml import etree
from pathlib import Path

from grc_utils import ACUTES, normalize_word
from grc_utils import (
    UPPER_SMOOTH_ACUTE, UPPER_ROUGH_ACUTE, LOWER_ACUTE, LOWER_SMOOTH_ACUTE, LOWER_ROUGH_ACUTE, LOWER_DIAERESIS_ACUTE,
    UPPER_SMOOTH_GRAVE, UPPER_ROUGH_GRAVE, LOWER_GRAVE, LOWER_SMOOTH_GRAVE, LOWER_ROUGH_GRAVE, LOWER_DIAERESIS_GRAVE,
    UPPER_SMOOTH_CIRCUMFLEX, UPPER_ROUGH_CIRCUMFLEX, LOWER_CIRCUMFLEX, LOWER_SMOOTH_CIRCUMFLEX, LOWER_ROUGH_CIRCUMFLEX, LOWER_DIAERESIS_CIRCUMFLEX
)

from src.utils.utils import abbreviations, get_canticum_ids

logging.basicConfig(
    filename='logs/debug.log',           # Save logs here
    level=logging.DEBUG,            # Log all messages from DEBUG and up
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'                    # Overwrite each run; use 'a' to append
)

###############################################################################
# ACCENT CHARACTERS
###############################################################################
accents = {
    'acute': set(
        UPPER_SMOOTH_ACUTE + UPPER_ROUGH_ACUTE + LOWER_ACUTE
        + LOWER_SMOOTH_ACUTE + LOWER_ROUGH_ACUTE + LOWER_DIAERESIS_ACUTE
    ),
    'grave': set(
        UPPER_SMOOTH_GRAVE + UPPER_ROUGH_GRAVE + LOWER_GRAVE
        + LOWER_SMOOTH_GRAVE + LOWER_ROUGH_GRAVE + LOWER_DIAERESIS_GRAVE
    ),
    'circumflex': set(
        UPPER_SMOOTH_CIRCUMFLEX + UPPER_ROUGH_CIRCUMFLEX + LOWER_CIRCUMFLEX
        + LOWER_SMOOTH_CIRCUMFLEX + LOWER_ROUGH_CIRCUMFLEX + LOWER_DIAERESIS_CIRCUMFLEX
    )
}

###############################################################################
# 0) UTILITY FUNCTIONS
###############################################################################


def polystrophic(tree, responsion):
    strophes = tree.xpath(f'//strophe[@responsion="{responsion}"]')
    return len(strophes) > 2


#
# SYLLABLE COUNT
#


def count_all_syllables(tree):
    """
    Returns the total count of canonical syllables across all lines in the XML tree.
    Uses the canonical_sylls function to process each line according to the special rules
    for resolution, anceps, and brevis in longo.
    
    Parameters:
    tree (etree._ElementTree): The parsed XML tree containing lines of text
    
    Returns:
    int: Total count of canonical syllables
    """
    total_count = 0
    
    # Find all line elements in the tree
    lines = tree.findall('.//l')
    
    # For each line, get its canonical syllables and add their count
    for line in lines:
        syllable_list = canonical_sylls(line)
        total_count += len(syllable_list)
        
    return total_count


def count_all_syllables_canticum(tree, responsion):

    canticum_count = 0
    lines = tree.xpath(f'(//strophe[@responsion="{responsion}"] | //antistrophe[@responsion="{responsion}"])//l')

    for line in lines:
        syllable_list = canonical_sylls(line)
        canticum_count += len(syllable_list)
    return canticum_count


#
# ACCENT COUNT
#

def count_all_accents_line(l):
    """
    Counts all occurrences of acute, grave, and circumflex accents
    within all <syll> elements inside the given <l> XML element.
    """
    counts = {'acute': 0, 'grave': 0, 'circumflex': 0}

    # Select all syllables inside the given <l> element
    all_sylls = l.xpath('.//syll')

    for syll in all_sylls:
        text = syll.text or ""
        norm_text = normalize_word(text)

        for accent_type, accent_chars in accents.items():
            if any(char in norm_text for char in accent_chars):
                counts[accent_type] += 1

    return counts


def count_all_accents_canticum(tree, responsion):
    """
    Counts all occurrences of acute, grave, and circumflex accents across
    all strophes and antistrophes in the XML tree for a specific canticum.
    """
    counts = {'acute': 0, 'grave': 0, 'circumflex': 0}

    # XPath to select syllables within strophes and antistrophes for the given responsion
    all_sylls = tree.xpath(f'//strophe[@responsion="{responsion}"]//syll | //antistrophe[@responsion="{responsion}"]//syll')

    for syll in all_sylls:
        text = syll.text or ""
        norm_text = normalize_word(text)

        for accent_type, accent_chars in accents.items():
            if any(char in norm_text for char in accent_chars):
                counts[accent_type] += 1

    return counts


def count_all_accents(tree):
    """
    Counts all occurrences of acute, grave, and circumflex accents across all
    strophes and antistrophes in the entire XML tree by summing results
    from count_all_accents_canticum for all cantica.
    """
    total_counts = {'acute': 0, 'grave': 0, 'circumflex': 0}

    # Get all unique responsion IDs in the tree
    responsion_ids = {strophe.get('responsion') for strophe in tree.xpath('//strophe[@responsion]')}

    # Accumulate counts from each responsion
    for responsion in responsion_ids:
        canticum_counts = count_all_accents_canticum(tree, responsion)
        for accent_type, count in canticum_counts.items():
            total_counts[accent_type] += count

    return total_counts


def count_all_accents_corpus(folder, exclude_substr=None, include_substr=None):
    """
    Run with exclude_substr="baseline" to include only the plays!
    Run with include_substr="baseline" to include only the baselines!
    """
    master_counts = {'acute': 0, 'grave': 0, 'circumflex': 0}

    for filename in os.listdir(folder):
        if not filename.endswith('.xml'):
            continue
        if exclude_substr and exclude_substr in filename:
            continue
        if include_substr and include_substr not in filename:
            continue

        filepath = os.path.join(folder, filename)
        try:
            tree = etree.parse(filepath)
            file_counts = count_all_accents(tree)
            for accent_type, count in file_counts.items():
                master_counts[accent_type] += count
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    return master_counts


###############################################################################
# 1) METRICAL RESPONSION
###############################################################################


def canonical_sylls(xml_line):
    """
    Transforms a scanned line into an abstract metre representation.

    Returns a list of 'weights' for the line, with the following rules:
      - Contraction: For simplicity's sake I'm treating contr. as an inverse resolution with no special logic
      - Resolution: Two consecutive syllables both with resolution="True" count as one 'heavy'.
      - Anceps: A syllable with anceps="True" becomes 'anceps', ignoring weight.
      - Brevis in longo: A syllable with brevis_in_longo="True" is treated as 'heavy'.
      - Otherwise, use 'heavy' or 'light' from the <syll weight="..."> attribute.
    """
    syllables = xml_line.findall('.//syll')
    result = []
    i = 0

    while i < len(syllables):
        current = syllables[i]
        is_anceps = current.get('anceps') == 'True'
        is_res = current.get('resolution') == 'True'
        is_brevis_in_longo = current.get('brevis_in_longo') == 'True'
        current_weight = current.get('weight', '')

        # (a) Two consecutive resolution => treat as one 'heavy'
        if is_res and (i + 1 < len(syllables)) and (syllables[i + 1].get('resolution') == 'True'):
            result.append('heavy')
            i += 2
            continue

        # (b) If anceps => 'anceps'
        if is_anceps:
            result.append('anceps')
            i += 1
            continue

        # (d) brevis_in_longo logic: brevis_in_longo="True" => 'heavy'
        if is_brevis_in_longo:
            result.append('heavy')
            i += 1
            continue

        # (e) Default behavior: use 'weight' if valid, otherwise 'light'
        result.append(current_weight if current_weight in ('heavy', 'light') else 'light')
        i += 1

    return result


def metrically_responding_lines(strophe_line, antistrophe_line):
    """
    Returns True if the two lines share the same 'canonical' sequence of syllables.
    Considers:
      - Consecutive resolution="True" => 'heavy'.
      - 'anceps' matches anything.
      - Light syll with brevis_in_longo="True" is treated as 'heavy'.
    """
    c1 = canonical_sylls(strophe_line)
    c2 = canonical_sylls(antistrophe_line)

    if len(c1) != len(c2):
        logging.debug(f"metrically_responding_lines: Line {strophe_line.get('n')} and {antistrophe_line.get('n')} have different syllable counts.")
        return False

    for s1, s2 in zip(c1, c2):
        if s1 == 'anceps' or s2 == 'anceps':
            continue
        if s1 != s2:
            return False

    return True


def metrically_responding_lines_polystrophic(*strophes):
    """
    Returns True if all the input strophes metrically respond to each other.
    Considers (partly inherited from canonical_sylls):
      - Consecutive resolution="True" => 'heavy'.
      - 'anceps' matches anything.
      - Light syllable with brevis_in_longo="True" is treated as 'heavy'.

    NB: Used very widely in the codebase!
    NB: Philosophy should be that the burden of asserting and printing errors is on the caller. This function should be lean. 
    """
    strophe_lines = [canonical_sylls(strophe) for strophe in strophes]
    all_checks_pass = True

    # Check 1: Line lengths
    line_lengths = [len(line) for line in strophe_lines]
    if len(set(line_lengths)) != 1: # note smart use of set() to check for canonical-syll uniformity!
        all_checks_pass = False
    
    # Check 2: Position by position comparisons
    for position, syllables in enumerate(zip(*strophe_lines), 1): # a cool way of describing zip is that it is matrix transposition ("T" operator, changes columns to rows)
        non_anceps = [s for s in syllables if s != 'anceps']
        if non_anceps and len(set(non_anceps)) != 1:
            all_checks_pass = False
    return all_checks_pass


###############################################################################
# 2) ACCENTUAL RESPONSION
###############################################################################


def build_units_for_accent(line):
    """
    Convert a <l> element into a list of 'units' for accent comparison:
      - single -> {'type': 'single', 'syll': sElem, 'unit_ord': #, 'line_n': line_n}
      - double -> {'type': 'double', 'syll1': s1, 'syll2': s2, 'unit_ord': #, 'line_n': line_n}

    'unit_ord' increments by 1 for each single/double block, so that
    consecutive resolution="True" lights become one 'double' unit.
    """
    sylls = line.findall('.//syll')
    units = []
    i = 0
    line_n = line.get('n') or "???"
    unit_ordinal = 1

    while i < len(sylls):
        s = sylls[i]
        is_res = s.get('resolution') == 'True'

        if is_res and (i + 1 < len(sylls)) and (sylls[i + 1].get('resolution') == 'True'):
            # double unit
            units.append({
                'type': 'double',
                'syll1': sylls[i],
                'syll2': sylls[i + 1],
                'unit_ord': unit_ordinal,
                'line_n': line_n
            })
            i += 2
        else:
            # single
            units.append({
                'type': 'single',
                'syll': s,
                'unit_ord': unit_ordinal,
                'line_n': line_n
            })
            i += 1

        unit_ordinal += 1

    return units


def has_acute(syll):
    """
    Returns True if the given syll element has an acute accent.
    """
    text = syll.text or ""
    norm = normalize_word(text)
    return any(ch in ACUTES for ch in norm)


def is_heavy(syll):
    """Helper to check if a single syllable is heavy (per @weight)."""
    return (syll.get('weight') == 'heavy')


def do_single_vs_single(u1, u2, accent_lists):
    """
    Normal single-syllable vs single-syllable check.
    We do check for all accent categories (acute, grave, circumflex).
    """
    s_syll = u1['syll']
    a_syll = u2['syll']
    text_s = s_syll.text or ""
    text_a = a_syll.text or ""
    norm_s = normalize_word(text_s)
    norm_a = normalize_word(text_a)

    for i, (accent_name, accent_chars) in enumerate(accents.items()):
        # If both have *some* char from accent_chars => record a match
        if any(ch in accent_chars for ch in norm_s) and any(ch in accent_chars for ch in norm_a):
            accent_lists[i].append({
                (u1['line_n'], u1['unit_ord']): text_s,
                (u2['line_n'], u2['unit_ord']): text_a
            })


def do_single_vs_single_polystrophic(units, accent_lists):
    """
    Check for accentual matches among single syllables across multiple strophes.
    We do check for all accent categories (acute, grave, circumflex).
    """
    texts = [(u['line_n'], u['unit_ord'], u['syll'].text or "") for u in units]
    normalized = [(n, ord_, normalize_word(text)) for n, ord_, text in texts]

    for i, (accent_name, accent_chars) in enumerate(accents.items()):
        # Check if all syllables in this unit set have the same accent
        if all(any(ch in accent_chars for ch in norm) for _, _, norm in normalized):
            accent_lists[i].append({(n, ord_): text for n, ord_, text in texts})


def do_double_vs_double(u1, u2, accent_lists):
    """
    Special resolution vs resolution logic (both are 'double').
    
    The user wants them to match (and only for acutes) if:
      - EITHER both pairs have the acute on their first sub-syllable,
      - OR both pairs have the acute on their second sub-syllable.

    We assume “both sub-syllables cannot have accent at once,” 
    so no need to check the corner case. 
    """
    s1 = u1['syll1']
    s2 = u1['syll2']
    a1 = u2['syll1']
    a2 = u2['syll2']

    strophe_first_acute  = has_acute(s1)
    strophe_second_acute = has_acute(s2)
    anti_first_acute     = has_acute(a1)
    anti_second_acute    = has_acute(a2)

    # Case (a): Both have acute on the first sub-syllable
    if strophe_first_acute and anti_first_acute:
        accent_lists[0].append({
            (u1['line_n'], u1['unit_ord']): s1.text or "",
            (u2['line_n'], u2['unit_ord']): a1.text or ""
        })

    # Case (b): Both have acute on the second sub-syllable
    if strophe_second_acute and anti_second_acute:
        accent_lists[0].append({
            (u1['line_n'], u1['unit_ord']): s2.text or "",
            (u2['line_n'], u2['unit_ord']): a2.text or ""
        })


def do_double_vs_double_polystrophic(units, accent_lists):
    """
    Check for accentual matches among double syllables across multiple strophes.
    Matches for acute accents if:
      - All first sub-syllables have acute
      - OR all second sub-syllables have acute
    """
    first_acutes = all(has_acute(u['syll1']) for u in units)
    second_acutes = all(has_acute(u['syll2']) for u in units)

    # Case (a): All first sub-syllables have acute
    if first_acutes:
        logging.debug(f"DOUBLE RESPONSION: {units[0]['unit_ord']}.")
        accent_lists[0].append({
            (u['line_n'], u['unit_ord']): u['syll1'].text or "" for u in units
        })

    # Case (b): All second sub-syllables have acute
    if second_acutes:
        logging.debug(f"DOUBLE RESPONSION: {units[0]['unit_ord']}.")
        accent_lists[0].append({
            (u['line_n'], u['unit_ord']): u['syll2'].text or "" for u in units
        })


def do_double_vs_single(u_double, u_single, accent_lists):
    """
    Rule: "They respond if and only if the second syll in the pair 
    has the acute, *and* the single (heavy) has acute."

    So we check:
      1) The single must be 'heavy' 
      2) The double's second sub-syllable must have an acute
      3) The single must have an acute
      4) We record in accent_lists[0] (the 'acute' list)
    """
    d1 = u_double['syll1']
    d2 = u_double['syll2']
    s_syll = u_single['syll']

    if not is_heavy(s_syll):
        return  # no match

    if has_acute(d2) and has_acute(s_syll):
        accent_lists[0].append({
            (u_double['line_n'], u_double['unit_ord']): d2.text or "",
            (u_single['line_n'], u_single['unit_ord']): s_syll.text or ""
        })


def do_mixed_single_double_polystrophic(units, accent_lists):
    """
    Handle accentual matches when some units are 'single' and others are 'double'.
    Rule: Respond if:
      - The single syllable is 'heavy'
      - The double's second sub-syllable has an acute
      - The single syllable has an acute
    """
    single_units = [u for u in units if u['type'] == 'single']
    double_units = [u for u in units if u['type'] == 'double']

    # Ensure all singles are heavy and have acute
    if not all(is_heavy(u['syll']) and has_acute(u['syll']) for u in single_units):
        return

    # Ensure all doubles have acute on the second sub-syllable
    if not all(has_acute(u['syll2']) for u in double_units):
        return

    # If conditions are satisfied, record matches
    logging.debug(f"MIXED RESPONSION: {units[0]['unit_ord']}.") 
    for u in single_units:
        for d in double_units:
            accent_lists[0].append({
                (d['line_n'], d['unit_ord']): d['syll2'].text or "",
                (u['line_n'], u['unit_ord']): u['syll'].text or ""
            })


def accentually_responding_syllables_of_line_pair(strophe_line, antistrophe_line):
    """
    Returns a triple-list [ [dict, ...], [dict, ...], [dict, ...] ]
    for [acute_matches, grave_matches, circumflex_matches].
    
    If lines are not metrically responding => return False.
    
    We only consider units that share the same ordinal index:
      - single vs single => normal check for all accents
      - double vs double => special rule for acute
      - double vs single => special rule for acute
      - single vs double => same logic, reversed

    """
    strophe_id = strophe_line.get('responsion')
    
    if not metrically_responding_lines(strophe_line, antistrophe_line):
        logging.debug(f"accentually_responding_syllables_of_line_pair: Lines {strophe_line.get('n')} and {antistrophe_line.get('n')} in {strophe_id} do not metrically respond.")
        return False

    units1 = build_units_for_accent(strophe_line)
    units2 = build_units_for_accent(antistrophe_line)

    if len(units1) != len(units2):
        return False

    accent_lists = [[], [], []]  # [acutes, graves, circumflexes]

    for u1, u2 in zip(units1, units2):
        # same ordinal check
        if u1['unit_ord'] != u2['unit_ord']:
            continue

        # (A) single vs single
        if u1['type'] == 'single' and u2['type'] == 'single':
            do_single_vs_single(u1, u2, accent_lists)

        # (B) double vs double
        elif u1['type'] == 'double' and u2['type'] == 'double':
            do_double_vs_double(u1, u2, accent_lists)

        # (C) double vs single
        elif u1['type'] == 'double' and u2['type'] == 'single':
            do_double_vs_single(u1, u2, accent_lists)

        # (D) single vs double
        elif u1['type'] == 'single' and u2['type'] == 'double':
            # just reverse the order
            do_double_vs_single(u2, u1, accent_lists)

    return accent_lists


def accentually_responding_syllables_of_lines_polystrophic(*strophe_lines):
    """
    Returns a triple-list [ [dict, ...], [dict, ...], [dict, ...] ]
    for [acute_matches, grave_matches, circumflex_matches], 
    across an arbitrary number of strophe lines.

    If lines are not metrically responding => return False.

    We only consider units that share the same ordinal index:
      - single vs single => normal check for all accents
      - double vs double => special rule for acute
      - double vs single => special rule for acute
      - single vs double => same logic, reversed
    """
    strophe_ids = [line.get('responsion') for line in strophe_lines]
    line_numbers = [line.get('n') for line in strophe_lines]

    # Check for metric responsion
    if not metrically_responding_lines_polystrophic(*strophe_lines):
        logging.debug(
            f"accentually_responding_syllables_of_lines_polystrophic: "
            f"Lines {line_numbers} in {strophe_ids} do not metrically respond."
        )
        return False

    # Build accent units for all input lines
    units_list = [build_units_for_accent(line) for line in strophe_lines]

    # Ensure all lines have the same number of units
    if not all(len(units) == len(units_list[0]) for units in units_list):
        print(
            f"accentually_responding_syllables_of_lines_polystrophic: "
            f"Lines {line_numbers} in {strophe_ids} have mismatched unit counts."
        )
        return False

    accent_lists = [[], [], []]  # [acutes, graves, circumflexes]

    # Compare units at the same ordinal index across all lines
    for units in zip(*units_list):
        ordinals = {u['unit_ord'] for u in units}
        if len(ordinals) > 1:
            # Skip if units don't share the same ordinal index
            continue

        # Handle specific pairings
        types = [u['type'] for u in units]
        if all(t == 'single' for t in types):
            # All lines have single syllables at this index
            do_single_vs_single_polystrophic(units, accent_lists)

        elif all(t == 'double' for t in types):
            # All lines have double syllables at this index
            do_double_vs_double_polystrophic(units, accent_lists)
            logging.debug(
                f"\naccentually_responding_syllables_of_lines_polystrophic:"
                f"\n\tAll double types at ordinal {units[0]['unit_ord']} in lines {line_numbers}."
            )

        else:
            # Mixed single/double cases
            do_mixed_single_double_polystrophic(units, accent_lists)
            logging.debug(
                f"\naccentually_responding_syllables_of_lines_polystrophic: "
                f"\n\tMixed types at ordinal {units[0]['unit_ord']} in lines {line_numbers}."
            )

    return accent_lists


def accentually_responding_syllables_of_strophe_pair(strophe, antistrophe):
    """
    Takes a <strophe type="strophe" responsion="XXXX"> and
    a <strophe type="antistrophe" responsion="XXXX"> with the same @responsion.

    For each pair of lines, checks if they are metrically & accentually responding.
    Accumulates all accent matches (acute, grave, circumflex) in a triple-list:
    
      [
         [ { (s_line, s_ord): '...', (a_line, a_ord): '...' }, ... ],  # acute
         [ ... ],                                                     # grave
         [ ... ]                                                      # circumflex
      ]

    Returns False if mismatch in responsion or line counts.
    """
    strophe_id = strophe.get('responsion')
    antistrophe_id = strophe.get('responsion')

    if strophe_id != antistrophe_id:
        return False

    s_lines = strophe.findall('l')
    a_lines = antistrophe.findall('l')
    if len(s_lines) != len(a_lines):
        return False

    combined_accent_lists = [[], [], []]  # [acutes, graves, circumflexes]

    for s_line, a_line in zip(s_lines, a_lines):
        if not metrically_responding_lines(s_line, a_line):
            print(f"Lines {s_line.get('n')} and {a_line.get('n')} in {strophe_id} do not metrically respond.")
            return False

        line_accent_lists = accentually_responding_syllables_of_line_pair(s_line, a_line)
        if line_accent_lists is False:
            return False

        for i in range(3):
            combined_accent_lists[i].extend(line_accent_lists[i])

    return combined_accent_lists


def accentually_responding_syllables_of_strophes_polystrophic(*strophes):
    """
    Takes multiple <strophe> elements (e.g., strophe, antistrophe, etc.) with the same @responsion.

    For each set of corresponding lines across the strophes:
      - Checks if they are metrically and accentually responding.
      - Accumulates all accent matches (acute, grave, circumflex) in a triple-list:
      
        [
           [ { (line, ord): '...', ... }, ... ],  # acute
           [ ... ],                              # grave
           [ ... ]                               # circumflex
        ]

    Returns False if:
      - Strophes do not share the same @responsion
      - Strophes have differing line counts
      - Lines do not metrically respond
    """
    if len(strophes) < 2:
        raise ValueError("At least two strophes are required for comparison.")

    # Ensure all strophes share the same responsion
    responsion_id = strophes[0].get('responsion')
    if any(strophe.get('responsion') != responsion_id for strophe in strophes):
        print(f"Mismatch in responsion across strophes: {responsion_id}")
        return False

    # Get all lines from each strophe
    strophe_lines = [strophe.findall('l') for strophe in strophes]
    num_lines = len(strophe_lines[0])

    # Ensure all strophes have the same number of lines
    if any(len(lines) != num_lines for lines in strophe_lines):
        print(f"Mismatch in line counts across strophes for responsion {responsion_id}.")
        return False

    combined_accent_lists = [[], [], []]  # [acutes, graves, circumflexes]

    # Process each corresponding line across the strophes
    for line_group in zip(*strophe_lines):
        if not metrically_responding_lines_polystrophic(*line_group):
            print(f"Lines {', '.join(line.get('n') for line in line_group)} in {responsion_id} do not metrically respond.")
            return False

        line_accent_lists = accentually_responding_syllables_of_lines_polystrophic(*line_group)
        if line_accent_lists is False:
            return False

        # Accumulate results
        for i in range(3):
            combined_accent_lists[i].extend(line_accent_lists[i])

    return combined_accent_lists

###############################################################################
# 3) THE ACCENTUAL RESPONSION METRIC
###############################################################################


def accentual_responsion_metric_canticum(xml_file, canticum) -> dict:
    """
    The strophicity-agnostic accentual responsion metric is defined as 
        n(number of groups of responding ACCENT sylls) / total number of sylls with ACCENT in the canticum,
    where n is the number of strophes and ACCENT is a subset of [acute, grave, circumflex].
    Practically in this function though, the n is "baked in" by summing over the lenghts of the dictionaries of match groups.

    Arguably, the most important is the acute-circumflex ratio, and unless otherwise specified,
    "accentual responsion metric" refers to the acute-circumflex ratio.

    Returns a dictionary with canticum-wide metric stats for the three accent types:

        stat_dictionary = {
        'acute': acute_stat,
        'grave': grave_stat,
        'circumflex': circumflex_stat,
        'acute_circumflex': acute_circumflex_stat,
        }
    """

    tree = etree.parse(xml_file)

    strophes = tree.xpath(f'//strophe[@responsion="{canticum}"] | //antistrophe[@responsion="{canticum}"]')

    accent_maps = accentually_responding_syllables_of_strophes_polystrophic(*strophes)

    total_accent_sums = count_all_accents_canticum(tree, canticum)
    accent_responsion_counts = {
        'acute': sum(len(dict) for dict in accent_maps[0]), # each dict looks like: {('205', 7): 'πάν', ('220', 7): 'τεί'}
        'grave': sum(len(dict) for dict in accent_maps[1]),
        'circumflex': sum(len(dict) for dict in accent_maps[2])
    }

    acute_total = total_accent_sums['acute']
    grave_total = total_accent_sums['grave']
    circumflex_total = total_accent_sums['circumflex']

    # Defining the four stats of the metric

    acute_stat = accent_responsion_counts['acute'] / acute_total if acute_total > 0 else 0
    grave_stat = accent_responsion_counts['grave'] / grave_total if grave_total > 0 else 0
    circumflex_stat = accent_responsion_counts['circumflex'] / circumflex_total if circumflex_total > 0 else 0

    acute_circumflex_numerator = accent_responsion_counts['acute'] + accent_responsion_counts['circumflex']
    acute_circumflex_denominator = acute_total + circumflex_total
    acute_circumflex_stat = acute_circumflex_numerator / acute_circumflex_denominator if acute_circumflex_denominator > 0 else 0

    stat_dictionary = {
        'acute': acute_stat,
        'grave': grave_stat,
        'circumflex': circumflex_stat,
        'acute_circumflex': acute_circumflex_stat,
    }

    return stat_dictionary

def accentual_responsion_metric_play(xml_file) -> dict:
    """
    The strophicity-agnostic accentual responsion metric is defined as 
        n(number of groups of responding ACCENT sylls) / total number of sylls with ACCENT in the canticum,
    where n is the number of strophes and ACCENT is a subset of [acute, grave, circumflex].
    Practically in this function though, the n is "baked in" by summing over the lenghts of the dictionaries of match groups.

    Arguably, the most important is the acute-circumflex ratio, and unless otherwise specified,
    "accentual responsion metric" refers to the acute-circumflex ratio.

    Returns a dictionary with play-wide metric stats for the three accent types:

        stat_dictionary = {
        'acute': acute_stat,
        'grave': grave_stat,
        'circumflex': circumflex_stat,
        'acute_circumflex': acute_circumflex_stat,
        }
    """

    stat_dictionary = {
        'acute': 0.0,
        'grave': 0.0,
        'circumflex': 0.0,
        'acute_circumflex': 0.0,
    }

    tree = etree.parse(xml_file)
    strophes = tree.xpath('//strophe | //antistrophe') # union is more readable XPath than [self::foo or self::bar] predicates

    cantica = defaultdict(list)
    for s in strophes:
        key = s.get('responsion')
        if key:
            cantica[key].append(s)

    # Count responding accents by iterating

    accent_responsion_counts = {
        'acute': 0.0,
        'grave': 0.0,
        'circumflex': 0.0,
    }

    for responsion_value, responding_strophes in cantica.items():
        accent_maps = accentually_responding_syllables_of_strophes_polystrophic(*responding_strophes)

        accent_responsion_counts['acute'] += sum(len(dict) for dict in accent_maps[0]) # each dict looks like: {('205', 7): 'πάν', ('220', 7): 'τεί'}
        accent_responsion_counts['grave'] += sum(len(dict) for dict in accent_maps[1])
        accent_responsion_counts['circumflex'] += sum(len(dict) for dict in accent_maps[2])

    # Count total accents in the play

    total_accent_sums = count_all_accents(tree)
    acute_total = total_accent_sums['acute']
    grave_total = total_accent_sums['grave']
    circumflex_total = total_accent_sums['circumflex']
    
    # Defining the four stats of the metric

    acute_stat = accent_responsion_counts['acute'] / acute_total if acute_total > 0 else 0
    grave_stat = accent_responsion_counts['grave'] / grave_total if grave_total > 0 else 0
    circumflex_stat = accent_responsion_counts['circumflex'] / circumflex_total if circumflex_total > 0 else 0

    acute_circumflex_numerator = accent_responsion_counts['acute'] + accent_responsion_counts['circumflex']
    acute_circumflex_denominator = acute_total + circumflex_total
    acute_circumflex_stat = acute_circumflex_numerator / acute_circumflex_denominator if acute_circumflex_denominator > 0 else 0

    stat_dictionary['acute'] += acute_stat
    stat_dictionary['grave'] += grave_stat
    stat_dictionary['circumflex'] += circumflex_stat
    stat_dictionary['acute_circumflex'] += acute_circumflex_stat

    return stat_dictionary

def accentual_responsion_metric_corpus(folder="data/compiled/", exclude_substr="baseline") -> dict:

    accent_responsion_counts = {
        'acute': 0.0,
        'grave': 0.0,
        'circumflex': 0.0,
    }

    for xml_file in os.listdir(folder):
        if not xml_file.endswith('.xml'):
            continue
        if exclude_substr and exclude_substr in xml_file:
            continue
        
        folder_path = Path(folder)
        filepath = folder_path / xml_file
        tree = etree.parse(filepath)
        strophes = tree.xpath('//strophe | //antistrophe')

        cantica = defaultdict(list)
        for s in strophes:
            key = s.get('responsion')
            if key:
                cantica[key].append(s)

        # Count responding accents by iterating
        for responsion_value, responding_strophes in cantica.items():
            accent_maps = accentually_responding_syllables_of_strophes_polystrophic(*responding_strophes)

            accent_responsion_counts['acute'] += sum(len(dict) for dict in accent_maps[0]) # each dict looks like: {('205', 7): 'πάν', ('220', 7): 'τεί'}
            accent_responsion_counts['grave'] += sum(len(dict) for dict in accent_maps[1])
            accent_responsion_counts['circumflex'] += sum(len(dict) for dict in accent_maps[2])

    # Count total accents in the corpus

    total_accent_sums = count_all_accents_corpus(folder, exclude_substr=exclude_substr)
    acute_total = total_accent_sums['acute']
    grave_total = total_accent_sums['grave']
    circumflex_total = total_accent_sums['circumflex']
    
    # Defining the four stats of the metric

    acute_stat = accent_responsion_counts['acute'] / acute_total if acute_total > 0 else 0
    grave_stat = accent_responsion_counts['grave'] / grave_total if grave_total > 0 else 0
    circumflex_stat = accent_responsion_counts['circumflex'] / circumflex_total if circumflex_total > 0 else 0

    acute_circumflex_numerator = accent_responsion_counts['acute'] + accent_responsion_counts['circumflex']
    acute_circumflex_denominator = acute_total + circumflex_total
    acute_circumflex_stat = acute_circumflex_numerator / acute_circumflex_denominator if acute_circumflex_denominator > 0 else 0

    stat_dictionary = {
        'acute': acute_stat,
        'grave': grave_stat,
        'circumflex': circumflex_stat,
        'acute_circumflex': acute_circumflex_stat,
    }

    return stat_dictionary

###############################################################################
# MAIN
###############################################################################

if __name__ == "__main__":

    tree = etree.parse("data/compiled/responsion_ach_compiled.xml")

    # Specify the responsion numbers to process
    responsion_numbers = {"ach01"}

    # Print ASCII logo at the start
    print(r"""
                                     _             
 _ __ ___  ___ _ __   ___  _ __  ___(_) ___  _ __  
| '__/ _ \/ __| '_ \ / _ \| '_ \/ __| |/ _ \| '_ \ 
| | |  __/\__ \ |_) | (_) | | | \__ \ | (_) | | | |
|_|  \___||___/ .__/ \___/|_| |_|___/_|\___/|_| |_|
              |_|                                  
    """)

    # Initialize counters for overall summary
    overall_counts = {
        'acute': 0,
        'grave': 0,
        'circumflex': 0
    }

    # Store individual responsion results
    responsion_summaries = {}

    # Collect and process all strophes and antistrophes matching the responsion numbers
    for responsion in responsion_numbers:
        strophes = tree.xpath(f'//strophe[@type="strophe" and @responsion="{responsion}"]')
        antistrophes = tree.xpath(f'//strophe[@type="antistrophe" and @responsion="{responsion}"]')

        # Ensure we only process matching pairs
        if len(strophes) != len(antistrophes):
            print(f"Mismatch in line count for responsion {responsion}: "
                  f"{len(strophes)} strophes, {len(antistrophes)} antistrophes.\n")
            continue

        # Initialize responsion-specific counts
        counts = {
            'acute': 0,
            'grave': 0,
            'circumflex': 0
        }

        for strophe, antistrophe in zip(strophes, antistrophes):
            accent_maps = accentually_responding_syllables_of_strophe_pair(strophe, antistrophe)

            if accent_maps:
                counts['acute'] += len(accent_maps[0])
                counts['grave'] += len(accent_maps[1])
                counts['circumflex'] += len(accent_maps[2])

        # Store summary for the current responsion
        responsion_summaries[responsion] = counts

        # Accumulate totals for overall summary
        overall_counts['acute'] += counts['acute']
        overall_counts['grave'] += counts['grave']
        overall_counts['circumflex'] += counts['circumflex']

    # Print summary section
    print("### SUMMARY: ###")
    responsion_range = '-'.join(sorted(responsion_numbers))
    print(f"Responsion: {responsion_range}")
    print(f"Acute matches:      {overall_counts['acute']}")
    print(f"Grave matches:      {overall_counts['grave']}")
    print(f"Circumflex matches: {overall_counts['circumflex']}")
    print("################\n")

    # Proceed with detailed printouts for each responsion (original logic preserved)
    for responsion, counts in responsion_summaries.items():
        strophes = tree.xpath(f'//strophe[@type="strophe" and @responsion="{responsion}"]')
        antistrophes = tree.xpath(f'//strophe[@type="antistrophe" and @responsion="{responsion}"]')

        print(f"\nResponsion: {responsion}")
        print(f"Acute matches:      {counts['acute']}")
        print(f"Grave matches:      {counts['grave']}")
        print(f"Circumflex matches: {counts['circumflex']}")
        print("\nDetailed accent pairs (prettified):\n")

        for strophe, antistrophe in zip(strophes, antistrophes):
            accent_maps = accentually_responding_syllables_of_strophe_pair(strophe, antistrophe)
            
            if accent_maps:
                labels = ["ACUTE", "GRAVE", "CIRCUMFLEX"]
                for i, label in enumerate(labels):
                    print(f"--- {label} MATCHES ({len(accent_maps[i])}) ---")
                    for idx, pair_dict in enumerate(accent_maps[i], start=1):
                        print(f"  Pair #{idx}:")
                        for (line_id, unit_ord), text in pair_dict.items():
                            print(f"    ({line_id}, ordinal={unit_ord}) => \"{text}\"")
                        print()
            else:
                print(f"No accentual responsion found for responsion {responsion}.")