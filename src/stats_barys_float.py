#!/usr/bin/env python3

# Copyright © Albin Ruben Johannes Thörn Cleland 2025, Lunds universitet, albin.thorn_cleland@klass.lu.se
# https://orcid.org/0009-0003-3731-4038
# This file is part of responsio-accentuum, licensed under the GNU General Public License v3.0.
# See the LICENSE file in the project root for full details.

"""
This is a generalization of stats_barys.py 
which returns float ratios instead of binary True/False values.

"""

from collections import defaultdict
from itertools import combinations
from lxml import etree
import os
from pathlib import Path

from .stats import metrically_responding_lines_polystrophic
from .stats_barys import barys_accentually_responding_syllables_of_lines

def _float_barys_lines(*lines):
    """
    Returns non-binary responsion stats for any number of metrically responding lines,
    indicating the fraction of lines that barys-respond for each canonical syllable position.

    Parameters:
    *lines: Variable number of xml <l> elements ("lines").

    Returns:
    list of floats 1/s ≤ f ≤ 1, one float per canonical syll, where s is nr of resp. lines : [], or False if mismatch.
    """

    if not metrically_responding_lines_polystrophic(*lines):
        print(f"Lines {[line.get('n') for line in lines]} do not metrically respond.")
        return False

    # the below barys_list contains one dict (of length = number of strophes) per barys match, with the key being a tuple of n attribute of the l element, and the ordinal (counting from 1) of the second (or only) syll of the barys accent that is the value.
    # E.g [{('2', 5): 'ίππου ', ('25', 5): 'νάντω', ('48', 5): 'κείνα^ν '}] is interpreted as
    # Match #1 (out of 1):
    # (line 2, 5th syll) => "ίππου "
    # (line 25, 5th syll) => "νάντω"
    # (line 48, 5th syll) => "κείνα^ν "

    list_pairs = []
    for line1, line2 in combinations(lines, 2):
        barys_list_pair = barys_accentually_responding_syllables_of_lines(line1, line2)[0]
        list_pairs.append(barys_list_pair)

    # fill in the list of match ratios for every position of the canonical line (i.e. ignoring line n attributes)
    # where dict_ratios[syll_ord] = ratio of lines that barys-respond at this position = number of pairs that barys-respond at this position / len(lines)
    dict_ratios = defaultdict(int)
    for barys_list_pair in list_pairs:
        for match in barys_list_pair:
            for (line_n, syll_ord) in match.keys():
                dict_ratios[syll_ord] += 1
    
    # turn the dict into a list of floats, filling in 0.0 for positions with no matches
    max_syll_ord = max(dict_ratios.keys())
    list_ratios = [dict_ratios.get(i, 0.0) for i in range(1, max_syll_ord + 1)]

    # Normalize to get float values
    s = len(lines)
    list_ratios = [count / s for count in list_ratios]

    return list_ratios

def _float_barys_strophes(*strophes):
    '''
    Uses float_barys_lines(*lines) to fill in a matrix of barys match ratios 
    for all positions of all lines of any number of strophes.

    Parameters:
    *strophes: Variable number of xml <strophe> elements.

    Returns:
    list of lists of floats (1/s ≤ f ≤ 1, where s = len(lists)), 
    where each inner list corresponds to a line in the strophe.
    '''

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

    # Process each line group across all strophes
    float_strophe_list = []
    for line_group in zip(*strophe_lines):
        float_barys_line = _float_barys_lines(*line_group)
        float_strophe_list.append(float_barys_line)

    return float_strophe_list

def float_barys_canticum(input_file, responsion):
    '''
    Parameters:
    input_file: Path to the XML file.
    responsion: The responsion id string (e.g. "py04").
    '''

    tree = etree.parse(input_file)
    strophes = tree.xpath(f'//strophe[@responsion="{responsion}"] | //antistrophe[@responsion="{responsion}"]')

    float_barys_strophe_list = _float_barys_strophes(*strophes)

    return float_barys_strophe_list

def float_barys_collection(input_file):
    '''
    Analyses all the responsion_ids of a single file.
    '''

    tree = etree.parse(input_file)
    strophes = tree.xpath(f'//strophe | //antistrophe')

    cantica = defaultdict(list)
    for s in strophes:
        key = s.get('responsion')
        if key:
            cantica[key].append(s)

    float_barys_collection_list = []
    for responsion_id, responding_strophes in cantica.items():
        float_barys_strophe = _float_barys_strophes(*responding_strophes)
        float_barys_collection_list.append(float_barys_strophe)

    return float_barys_collection_list

def float_barys_corpus(folder="data/compiled/", exclude_substr="baseline"):
    '''
    Analyses all the responsion_ids of all files in a folder.
    '''

    float_barys_corpus_list = []

    for xml_file in os.listdir(folder):
        if not xml_file.endswith('.xml'):
            continue
        if exclude_substr and exclude_substr in xml_file:
            continue
        
        folder_path = Path(folder)
        filepath = os.path.join(folder_path, xml_file)

        float_barys_collection_list = float_barys_collection(filepath)
        float_barys_corpus_list.append(float_barys_collection_list)
    
    return float_barys_corpus_list
