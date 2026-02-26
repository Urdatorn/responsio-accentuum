#!/usr/bin/env python3

# Copyright © Albin Ruben Johannes Thörn Cleland 2026, Lunds universitet, albin.thorn_cleland@klass.lu.se
# https://orcid.org/0009-0003-3731-4038
# This file is part of responsio-accentuum, licensed under the GNU General Public License v3.0.
# See the LICENSE file in the project root for full details.

'''
I include here some functionality generally useful for the inference scripts and notebooks.
''' 
from collections import Counter
from lxml import etree
import numpy as np
import re
from scipy.stats import chisquare
import xml.etree.ElementTree as ET
from pathlib import Path

from grc_utils import vowel

_ROOT = Path(__file__).resolve().parents[2]


def _resolve_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else _ROOT / path

#################################
### General utility functions ###
#################################

victory_odes = sorted([
    'is01', 'is02', 'is03', 'is04', 'is05', 'is06', 'is07', 'is08',
    'ne01', 'ne02', 'ne03', 'ne04', 'ne05', 'ne06', 'ne07', 'ne08', 'ne09', 'ne10', 'ne11',
    'ol01', 'ol02', 'ol03', 'ol04', 'ol05', 'ol06', 'ol07', 'ol08', 'ol09', 'ol10', 'ol11', 'ol12', 'ol13', 'ol14',
    'py01', 'py02', 'py03', 'py04', 'py05', 'py06', 'py07', 'py08', 'py09', 'py10', 'py11', 'py12',
])

victory_odes_not_triadic = sorted([
    'is03', 'ol04', 'ol11', 'ol12', 'py07'
])

def clean_tei_text(input_xml_file, output_xml_file):
    '''
    Cleans all the line text in an uncompiled TEI XML file.
    '''
    input_xml_file = _resolve_path(input_xml_file)
    output_xml_file = _resolve_path(output_xml_file)
    tree = etree.parse(input_xml_file)
    root = tree.getroot()
    text_elements = root.xpath("//l")
    cleaned_texts = [clean_text(syll.text or '') for syll in text_elements]
    
    for elem, cleaned in zip(text_elements, cleaned_texts):
        elem.text = cleaned

    tree.write(output_xml_file, encoding="utf-8", xml_declaration=True)

def clean_text(text: str) -> str:
    to_clean = r'[\u0387\u037e\u00b7\.,!?;:\"()\[\]{}<>«»⌞⌟\-—…|⏑⏓†×]' # NOTE hyphens must be escaped
    cleaned_text = re.sub(to_clean, '', text)
    return cleaned_text

def get_canticum_ids(file_path: str) -> list[str]:
    all_ids = []

    file_path = _resolve_path(file_path)
    tree = etree.parse(file_path)
    root = tree.getroot()
    strophe_elements = root.xpath("//strophe")
    all_ids.extend(strophe.get("responsion") for strophe in strophe_elements)

    seen = set()
    return [x for x in all_ids if x not in seen and not seen.add(x)]

# def get_syll_count(canticum_ids):
#     syll_count = {}
#     for abbreviation in abbreviations:
#         file_path = f'data/compiled/responsion_{abbreviation}_compiled.xml'
#         tree = etree.parse(file_path)
#         root = tree.getroot()
#         for strophe in root.xpath("//strophe"):
#             responsion_id = strophe.get("responsion")
#             if responsion_id in canticum_ids:
#                 syllables = strophe.xpath(".//syll")
#                 syll_count[responsion_id] = len(syllables)
#     return syll_count

def canticum_with_at_least_two_strophes(xml_file, responsion_attribute: str):
    xml_file = _resolve_path(xml_file)
    tree = etree.parse(xml_file)
    root = tree.getroot()

    strophes = root.findall(f".//strophe[@responsion='{responsion_attribute}']")

    return len(strophes) >= 2

def get_strophicity(abbreviations):
    responsion_counts = Counter()

    for abbreviation in abbreviations:
        file_path = _resolve_path(f"data/compiled/responsion_{abbreviation}_compiled.xml")
        tree = etree.parse(file_path)
        root = tree.getroot()

        elements = root.xpath("//strophe[@responsion]") + root.xpath("//antistrophe[@responsion]")
        for el in elements:
            rid = el.get("responsion")
            if rid:
                responsion_counts[rid] += 1

    more_than_two = [rid for rid, count in responsion_counts.items() if count > 2]
    exactly_two = [rid for rid, count in responsion_counts.items() if count == 2]

    return more_than_two, exactly_two

def get_text_matrix(xml_filepath: str, responsion_attribute: str, representative_strophe: int):
    '''
    Get a 2D list (matrix) representing the syllable structure 
    of the text of the first strophe in the given XML file,
    so it can be superpositioned over a heatmap.

    xml_filepath: path to the XML file
    responsion_attribute: the value of the responsion attribute of the song in question
    representative_strophe: 1-based index of the strophe whose text to use
    '''
    # Load XML
    xml_filepath = _resolve_path(xml_filepath)
    tree = etree.parse(xml_filepath)
    root = tree.getroot()

    desired_strophes = root.findall(f".//strophe[@responsion='{responsion_attribute}']")
    picked_strophe = desired_strophes[representative_strophe - 1] if desired_strophes else None

    text_matrix = []

    # Iterate over <l> children
    for l in picked_strophe.findall("l"):
        line_sylls = []
        buffer = ""
        prev_resolved = False
        
        for syll in l.findall("syll"):
            resolved = syll.get("resolution") == "True"
            content = syll.text or ""
            
            if prev_resolved and resolved: # and not prev_space # to accomodate the special handling of word-end between in resolved pairs in get_contours_line (in stats_comp.py)
                # join with previous
                buffer += content
            else:
                # flush previous buffer if any
                if buffer:
                    line_sylls.append(buffer)
                buffer = content
            
            #prev_space = content.endswith(" ")
            prev_resolved = resolved
        
        # Append any remaining buffer
        if buffer:
            line_sylls.append(buffer)
        
        text_matrix.append(line_sylls)

    row_lengths = [len(row) for row in text_matrix]
    return text_matrix, row_lengths

def flatten_recursive(data):
    """Recursively flatten nested structure"""
    for item in data:
        if hasattr(item, '__iter__') and not isinstance(item, (str, bytes)):
            yield from flatten_recursive(item)
        else:
            yield item

def count_nested_values(nested_data):
    """
    Recursively flattens a nested data structure and counts all values.
    
    Args:
        nested_data: A nested list/iterable structure of arbitrary depth
        
    Returns:
        Counter: Dictionary with value counts
    """
    from collections import Counter
    
    values = list(flatten_recursive(nested_data))
    count_dict = Counter(values)
    
    return count_dict

def cowsay(text, print_output=True):
    length = len(text)

    ascii = "\n".join(
        [" " + "_" * (length + 2),
         f"< {text} >",
         " " + "-" * (length + 2),
         r"        \   ^__^ ",
         r"         \  (oo)\_______",
         r"            (__)\       )\/\ ",
         "                ||----w | ",
         "                ||     || ",
         "\n"]
    )

    if print_output:
        print(ascii)

    return ascii

#################################
### Stats utility functions   ###
#################################

def make_chisquare_test(list_comp_scores, list_comp_baseline_scores):
    '''
    list_comp_scores and list_comp_baseline_scores: Handle any nestedness, from compatibility_corpus to compatibility_canticum
    '''

    count_dict = count_nested_values(list_comp_scores)
    count_dict_baselines = count_nested_values(list_comp_baseline_scores)

    # ------------------------------ #
    # Synchronize dictionaries       #
    # ------------------------------ #

    # Get union of all keys from both dictionaries
    all_keys = set(count_dict.keys()) | set(count_dict_baselines.keys())

    # Create aligned dictionaries with zeros for missing keys
    aligned_count_dict = {key: count_dict.get(key, 0) for key in all_keys}
    aligned_count_dict_baselines = {key: count_dict_baselines.get(key, 0) for key in all_keys}

    # Convert to lists with consistent ordering
    sorted_keys = sorted(all_keys)
    count_list = [aligned_count_dict[key] for key in sorted_keys]
    count_list_baselines = [aligned_count_dict_baselines[key] for key in sorted_keys]

    # ------------------------------ #
    # Calculate expected counts      #
    # ------------------------------ #

    # 1) Observed counts
    obs_counts = np.array(count_list)
    obs_total = obs_counts.sum()

    # 2) Null counts
    null_counts = np.array(count_list_baselines)
    null_total = null_counts.sum()

    # 3) Null probabilities
    null_probs = null_counts / null_total

    # Expected counts
    exp_counts = null_probs * obs_total

    # ------------------------------ #
    # Chi-square test                #
    # ------------------------------ #

    chi2_stat, p_value = chisquare(f_obs=obs_counts, f_exp=exp_counts)

    degrees_of_freedom = len(obs_counts) - 1

    return chi2_stat, degrees_of_freedom, p_value, sorted_keys, obs_counts, obs_total, exp_counts

######################
### Word utilities ###
######################

def space_before(syll):
    """Returns True if there is a space before the first vowel in the syllable's text."""
    text = syll.text if syll.text else ""
    for i, char in enumerate(text):
        if vowel(char):  # Find the first vowel
            return i > 0 and text[i - 1] == " "
    return False


def space_after(syll):
    """Returns True if there is a space after the last vowel in the syllable's text."""
    text = syll.text if syll.text else ""
    last_vowel_index = -1

    for i, char in enumerate(text):
        if vowel(char):
            last_vowel_index = i  # Keep track of the last vowel position

    return last_vowel_index != -1 and last_vowel_index < len(text) - 1 and text[last_vowel_index + 1] == " "

def get_words_xml(l_element):
    '''
    Doesn't support resolution yet
    '''
    words = []
    current_word = []

    syllables = [child for child in l_element if child.tag == "syll"]

    for i, syll in enumerate(syllables):
        syll_xml = ET.tostring(syll, encoding='unicode', method='xml')
        current_word.append(syll_xml)
        next_syll = syllables[i + 1] if i + 1 < len(syllables) else None

        if space_after(syll):
            #print()
            #print(f'SPACE AFTER CASE: |{syll}|')
            words.append("".join(current_word))  # Store current word
            current_word = []  # Start a new word
        elif syll.tail and " " in syll.tail:
            #print()
            #print(f'TAIL CASE: |{syll.tail}|')
            words.append("".join(current_word))
            current_word = []
        elif next_syll is not None and space_before(next_syll):
            #print()
            #print(f'SPACE BEFORE NEXT CASE: |{next_syll}|')
            words.append("".join(current_word))
            current_word = []

    if current_word:
        words.append("".join(current_word))

    cleaned_words = []
    for word in words:
        root = ET.fromstring(f"<wrapper>{word}</wrapper>")
        for syll in root.iter("syll"):  
            syll.tail = None

        cleaned_words.append("".join(ET.tostring(syll, encoding="unicode", method="xml") for syll in root))
    words = cleaned_words

    return words
