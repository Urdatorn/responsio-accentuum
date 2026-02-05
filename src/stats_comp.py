#!/usr/bin/env python3
# Copyright (parly, see below) © Albin Ruben Johannes Thörn Cleland 2026, Lunds universitet, albin.thorn_cleland@klass.lu.se
# https://orcid.org/0009-0003-3731-4038
# This file is part of responsio-accentuum, licensed under the GNU General Public License v3.0, but see below.
# See the LICENSE file in the project root for full details.

'''
A substantial part of this file is adapted from the Greek-Poetry code by Anna Conser,
subject to the following MIT license:

    Copyright (c) 2022 Anna Conser

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
'''

from fractions import Fraction as F
from lxml import etree
import os
from statistics import mean
from tqdm import tqdm

from grc_utils import is_enclitic, is_proclitic
from stats import accents, metrically_responding_lines_polystrophic
from utils.utils import space_after, space_before


def get_contours_line(l_element) -> list[str]:
        """
        Adapted from a method in class_stanza
        Iterates through an <l> of <syll> elements and creates a list of melodic contours.
        - DN-A = Melody falls after *main* acute or circumflex.
        - DN = Melody falls after non-main accent.
        - UP: Melody rises before the accent.

        - UP-G: Melody rises before the grave.
        - N: No restrictions on the contour.

        Note that 'N' is a contour that will not contradict any following contour. 
        It's a feature and not a bug that e.g. a circumflex at word end will have 'N' contour.
        """

        contours = []
        pre_accent = True # means we're either on the accented syll or earlier in a word, e.g. 'κε' and 'λεύ' in κελεύῃς.
        last_contour = ''

        syllables = [child for child in l_element if child.tag == "syll"]
        for i, s in enumerate(syllables):
            contour = ''

            is_first_res = False
            if i + 1 < len(syllables):
                next_syll = syllables[i + 1]
                is_first_res = next_syll.get('resolution') == 'True'

            word_end = space_after(s) or (s.tail and " " in s.tail) or (next_syll is not None and space_before(next_syll))

            # Check for word-end in middle of resolved syllable [CHECK]
            if is_first_res and word_end: # = first of two resolution syllables with a word end in between
                pre_accent = True # cf. later below
            
            # Check for ENCLITICS (excluding τοῦ), and correct previous syllable [CHECK]
            if s.text and is_enclitic(s.text) and not is_proclitic(s.text):
                if contours and contours[-1] == 'N':
                    contours[-1] = last_contour
                    pre_accent = False

            # MAIN ACCENT followed by characteristic fall [CHECK]
            if s.text and any(ch in accents['acute'] or ch in accents['circumflex'] for ch in s.text):
                if pre_accent:
                    contour = 'DN-A' # = βαρύς, e.g. the second position in 'λο πήδα' and 'κελεύῃς'
                    pre_accent = False
                else:  # unless a second accent caused by an enclitic
                    contour = 'DN'
            # BEFORE ACCENT, the melody rises
            elif pre_accent:
                contour = 'UP'
            # AFTER ACCENT, the melody falls 
            else: # no accent and not pre accent
                contour = 'DN'

            # WORD END can be followed by any note [CHECK]
            if word_end:
                last_contour = contour  # copy contour in case of subsequent enclitic
                contour = 'N'
                pre_accent = True

            # Except PROCLITICS and GRAVES followed by a very small rise or a repetition
            if (s.text and is_proclitic(s.text)) or any(ch in accents['grave'] for ch in s.text):
                contour = 'UP-G'

            contours.append(contour)

        return contours


def all_contours_line(*xml_lines) -> list[list[str]]:
    """
    Intermediary between get_contours(l_element) and position-based compatibility stats of set of responding lines.

    Takes multiple XML <l> elements, applies get_contours to each, and returns
    lists where each inner list contains the contours for a given syllabic position
    across all lines, while merging resolved syllables.

    - Ensures all input lines metrically respond.
    - Merges two <syll> elements with resolution="True" into a sublist.
    
    Example:
        all_contours_line(line1, line2, line3) 
        returns [
            [contour1_line1, contour1_line2, contour1_line3],
            [contour2_line1, contour2_line2, contour2_line3],
            ...
        ]
    """

    if not metrically_responding_lines_polystrophic(*xml_lines):
        for xml_line in xml_lines:
            text = etree.tostring(xml_line, encoding="unicode", method="xml")
            print(text, "\n")
        raise ValueError(f"all_contours_line: Lines {[line.get('n', 'unknown') for line in xml_lines]} do not metrically respond.")

    contours_per_line = [get_contours_line(line) for line in xml_lines]

    merged_syllables_per_line = []
    for line in xml_lines:
        syllables = [child for child in line if child.tag == "syll"]
        merged_syllables = []
        i = 0
        while i < len(syllables):
            current = syllables[i]
            is_res = current.get("resolution") == "True"

            if is_res and i + 1 < len(syllables) and syllables[i + 1].get("resolution") == "True":
                # Merge two consecutive resolved syllables into a sublist
                merged_syllables.append([current, syllables[i + 1]])
                i += 2  # Skip next syllable
            else:
                merged_syllables.append(current)
                i += 1

        merged_syllables_per_line.append(merged_syllables)

    # Ensure all lines have the same number of syllables after merging resolution
    num_syllables = len(merged_syllables_per_line[0])
    mismatched_lines = []
    for i, ms in enumerate(merged_syllables_per_line):
        if len(ms) != num_syllables:
            mismatched_lines.append(xml_lines[i].get('n', 'unknown'))
    if mismatched_lines:
        raise ValueError(f"all_contours_line: Mismatch in syllable counts across lines {mismatched_lines} after merging resolution.")

    # Transpose the lists: group contours by syllable position
    grouped_contours = list(map(list, zip(*contours_per_line)))

    return grouped_contours


def _compatibility_line(*xml_lines, fractional=True) -> list[F | float]:
    '''
    Computes the contour of a line from a set of responding strophes,
    evaluates matches and repetitions, 
    and returns a list of float ratios indicating the degree of compatibility at each position.

    For every position, the ratio of the largest subset of internally matching strophes to the total amount of strophes is computed.
    - "Matching" means being in [UP, UP-G, N] or [DN, DN-A, N].
    - E.g: given 5 strophes, where 1 and 2 match, and 3, 4 and 5 match, the second group is the largest and the ratio returned would be 3/5 = 0.6.
    - Unambiguous matches thus yield 1. No position yields less than 1 / n, where n is the number of strophes.
    - NB resolved sylls are in sublists
    
    Returns a list of Fractions (or floats if fractional=False), one for each position.
    - To "re-binarize" the results later, simply interpret 1 as MATCH and everything else as REPEAT.

    NOTE: NOT NORMALIZED, HENCE USE WITH CAUTION!
    Normalization takes place at the canticum level.
    '''

    compatibility_ratios = []

    position_lists = all_contours_line(*xml_lines)
    for position in position_lists: # position K = [contourK_line1, contourK_line2, ..., contourK_lineN], where N is number of resp. strophes
        
        all_resolved = True
        for strophe in position:
            if isinstance(strophe, list): # only resolved positions are lists
                continue
            else:
                all_resolved = False
                break

        up = []
        down = []

        for strophe in position: # this is in an invididual syllable's contour
            if isinstance(strophe, list): # checking sublists of two resolved syllable contours
                if all_resolved == True: # proceed as normal if all strophes resolve
                    print('\033[31mComparing resolved positions...\033[0m')
                    for resolved_syll in strophe:
                        if resolved_syll in ['UP', 'UP-G', 'N']:
                            up.append(resolved_syll)
                        elif resolved_syll in ['DN', 'DN-A', 'N']:
                            down.append(resolved_syll)
                        else:
                            raise ValueError(f"Unknown contour {resolved_syll} in _compatibility_line.")
                
                # special logic to compare resolved and unresolved syllables
                #
                # Out of 9 combinations, 7 are unproblematic:
                # 0. N and N = N
                # 1. UP(-G) and UP(-G) = UP
                # 2. DN(-A) and DN(-A) = DN
                # 3-4. UP(-G) and N (and vice versa) = UP
                # 5-6. DN(-A) and N (and vice versa) = DN 
                #
                # these two are less obvious, since the sum interval could be up or down:
                # 7. UP and DN(-A), which means second syll accented.
                # 8. DN(-A) and UP(-G), which means first syll accented. 
                # It could contradict both preaccentual rise and post-accentual fall, and only compatible with N.
                # Thus it would need its own class. But methodologically, we should rather skip such syllables, and they are probably very rare (let's do a debug count!).
                # Summing up there are four distinct cases:
                # - Append to both up and down if 0.
                # - Append to up if 1, 3 or 4.
                # - Append to down if 2, 5 or 6.
                # - 'continue' strophe in position loop if 7 or 8. 

                else: # if all_resolved = False
                    print(f'\033[31mComparing resolved and unresolved positions...\033[0m')
                    resolved_1, resolved_2 = strophe
                    resolved_position = resolved_1 + resolved_2
                    if resolved_1 == resolved_2 == 'N': # CASE 1
                        up.append(resolved_position)
                        down.append(resolved_position)
                    elif all(x in ['UP', 'UP-G', 'N'] for x in [resolved_1, resolved_2]): # CASE 2
                        up.append(resolved_position)
                    elif all(x in ['DN', 'DN-A', 'N'] for x in [resolved_1, resolved_2]): # CASE 3
                        down.append(resolved_position)
                    else: # CASE 4 - the problematic case of mixed contours => skip whole position in analysis (at least I find this safest for now)
                        continue # goes back to "for strophe in position" loop

            elif strophe in ['UP', 'UP-G', 'N']:
                up.append(strophe)

            elif strophe in ['DN', 'DN-A', 'N']:

                down.append(strophe)
            else:
                raise ValueError(f"Unknown contour {strophe} in _compatibility_line.")

        max_len = max(len(up), len(down)) # for even N, N/2 <= max_len <= N, otherwise N/2 < max_len < N
        if fractional:
            position_compatibility_ratio = F(max_len, len(position))
        else:
            position_compatibility_ratio = max_len / len(position)
        compatibility_ratios.append(position_compatibility_ratio)

    return compatibility_ratios


def compatibility_canticum(xml_file_path, canticum_ID, fractional=True) -> list:
    """
    Compute compatibility ratios for each line position across all strophes in a canticum.
    
    Args:
        xml_file_path: Path to XML file
        canticum_ID: ID to match against strophe[@responsion]
        fractional: If True, return Fractions; otherwise return floats
    
    Returns:
        List of lists, where each inner list contains compatibility ratios for one line
    """
    tree = etree.parse(xml_file_path)
    root = tree.getroot()

    strophes = root.xpath(f'//strophe[@responsion="{canticum_ID}"]')
    if not strophes:
        raise ValueError(f"No strophes found with responsion={canticum_ID}")
    
    num_lines = len([el for el in strophes[0] if el.tag == 'l']) # same for all, since they respond
    
    canticum_list_of_line_compatibility_ratio_lists = []
    
    for line_pos in range(num_lines):
        responding_lines = []
        for strophe in strophes:
            lines = [el for el in strophe if el.tag == 'l']
            if line_pos < len(lines):
                responding_lines.append(lines[line_pos])
        
        # Get compatibility ratios for this set of responding lines
        compatibility_ratios = _compatibility_line(*responding_lines, fractional=fractional)
        canticum_list_of_line_compatibility_ratio_lists.append(compatibility_ratios)
    
    def normalize(line_scores):
        # Minimum possible ratio is the smallest majority share: ceil(n/2) / n
        n = len(strophes)
        min_ratio = F((n // 2) + (n % 2), n)

        span = F(1, 1) - min_ratio
        normalized = []
        for score in line_scores:
            score_f = score if isinstance(score, F) else F(score)
            normalized.append((score_f - min_ratio) / span)
        return normalized

    normalized_canticum = [normalize(line) for line in canticum_list_of_line_compatibility_ratio_lists]

    return normalized_canticum


def compatibility_play(xml_file_path, fractional=True):
    tree = etree.parse(xml_file_path)
    root = tree.getroot()

    cantica = set()
    for strophe in root.xpath('//strophe[@responsion]'):
        cantica.add(strophe.get('responsion'))

    list_of_lists_of_compatibility_per_position_lists = [] # for every canticum, compiling a list of one compatibility-per-position float list for every line

    for canticum in cantica:
        result = compatibility_canticum(xml_file_path, canticum, fractional=fractional)
        list_of_lists_of_compatibility_per_position_lists.append(result)
    
    return list_of_lists_of_compatibility_per_position_lists


def compatibility_corpus(dir_path, fractional=True):
    corpus_compatibility_lists = []
    
    # Get all XML files in directory
    xml_files = [f for f in os.listdir(dir_path) if f.endswith('.xml')]
    
    # Process each XML file
    for xml_file in tqdm(xml_files, initial=1):
        file_path = os.path.join(dir_path, xml_file)
        try:
            play_results = compatibility_play(file_path, fractional=fractional)
            corpus_compatibility_lists.append(play_results)
        except Exception as e:
            print(f"Error processing {xml_file}: {e}")
            continue
            
    return corpus_compatibility_lists


def compatibility_strophicity(dir_path="compiled", mode="antistrophic", id="", fractional=True):
    """
    Compute compatibility ratios for all XML files in a directory,
    filtered by number of responding strophes and optional ID prefix.

    Args:
        dir_path: Path to directory containing XML files
        mode: "polystrophic" (3+ strophes), "antistrophic" (exactly 2),
              "three-strophic" (exactly 3), or "four-strophic" (exactly 4)
        id: String prefix to filter canticum IDs (e.g. "ach" for Acharnians)
        fractional: If True, return Fractions; otherwise return floats

    Returns:
        List of compatibility ratio lists from filtered cantica (Fraction if fractional=True)
    """
    valid_modes = ["polystrophic", "antistrophic", "three-strophic", "four-strophic"]
    if mode not in valid_modes:
        raise ValueError(f"Mode must be one of {valid_modes}")

    corpus_compatibility_lists = []
    xml_files = [f for f in os.listdir(dir_path) if f.endswith('.xml')]

    for xml_file in xml_files:
        file_path = os.path.join(dir_path, xml_file)
        try:
            tree = etree.parse(file_path)
            root = tree.getroot()

            # Count strophes per canticum
            canticum_counts = {}
            for strophe in root.xpath('//strophe[@responsion]'):
                resp_id = strophe.get('responsion')
                if id and not resp_id.startswith(id):
                    continue
                canticum_counts[resp_id] = canticum_counts.get(resp_id, 0) + 1

            # Filter based on mode
            if mode == "polystrophic":
                filtered_cantica = [cid for cid, count in canticum_counts.items() if count >= 3]
            elif mode == "antistrophic":
                filtered_cantica = [cid for cid, count in canticum_counts.items() if count == 2]
            elif mode == "three-strophic":
                filtered_cantica = [cid for cid, count in canticum_counts.items() if count == 3]
            elif mode == "four-strophic":
                filtered_cantica = [cid for cid, count in canticum_counts.items() if count == 4]

            # Process filtered cantica
            play_results = []
            for canticum_id in filtered_cantica:
                result = compatibility_canticum(file_path, canticum_id, fractional=fractional)
                play_results.append(result)

            if play_results:
                corpus_compatibility_lists.append(play_results)

        except Exception as e:
            print(f"Error processing {xml_file}: {e}")
            continue

    return corpus_compatibility_lists


def compatibility_ratios_to_stats(list_in, binary=False) -> F:
    """
    Convert nested compatibility ratios to a single stat, optionally binarizing values as Conser.
    The default is to *normalize* the fractions to [0, 1] before averaging.
    
    Args:
        list_in: Nested list of compatibility ratios
        binary: If True, convert all non-1 values to 0
        
    Returns:
        Fraction: Mean compatibility ratio
    """
    def get_nesting_depth(lst) -> int:
        if not isinstance(lst, list):
            return 0
        if not lst:
            return 1
        return 1 + max((get_nesting_depth(item) for item in lst), default=0)
    
    depth = get_nesting_depth(list_in)
    merged_list = []

    if depth == 1:  # single line
        merged_list = list_in
    elif depth == 2:  # canticum
        for line in list_in:
            merged_list.extend(line)
    elif depth == 3:  # whole play
        for canticum in list_in:
            for line in canticum:
                merged_list.extend(line)
    elif depth == 4:  # all plays
        for play in list_in:
            for canticum in play:
                for line in canticum:
                    merged_list.extend(line)

    # Binarize if requested
    if binary:
        merged_list = [0 if x != 1 else 1 for x in merged_list]

    # Cast early to Fraction to keep exact arithmetic during normalization
    merged_list = [x if isinstance(x, F) else F(x) for x in merged_list]

    return mean(merged_list)

    