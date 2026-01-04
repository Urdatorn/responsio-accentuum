#!/usr/bin/env python3

# Copyright © Albin Ruben Johannes Thörn Cleland 2025, Lunds universitet, albin.thorn_cleland@klass.lu.se
# https://orcid.org/0009-0003-3731-4038
# This file is part of responsio-accentuum, licensed under the GNU General Public License v3.0.
# See the LICENSE file in the project root for full details.

'''
Once 
    1) the first strophe of a scansion 
has been manually checked and corrected, and
    2) all resolutions have been marked-up, 
this script applies the same scansion to all other strophes,
given that their lines now (hopefully) have the same number of syllables.
'''

from lxml import etree
import os
import re
from tqdm import tqdm

from grc_utils import vowel

from .scan import muta, liquida, to_clean, heavy_syll

def fix_scansion(text):
    '''
    Assumes the first strophe in each responsion group is correct,
    and changes the weight of all dichronic syllables in other strophes to match it.
    '''
    sylls = re.split(r'(\[.+?\]|\{.+?\})', text)

    # iterate through sylls and next_sylls: if syll 1) does not contain U+02C8 (ˈ), MODIFIER LETTER VERTICAL LINE, and 2) syll[-1] in muta and 3) next_syll[1] in liquida too, then move syll[-1] to the beginning of next_syll.
    for idx, syll in enumerate(sylls):
        next_syll = sylls[idx + 1] if idx + 1 < len(sylls) else ""
        if "ˈ" not in syll and syll[-1] in muta and next_syll[0] in liquida:
            sylls[idx] = syll[:-1]
            sylls[idx + 1] = syll[-1] + next_syll

    line = ""

    for idx, syll in enumerate(sylls):

        syll_clean = re.sub(to_clean, "", syll.strip())
        next_syll = sylls[idx + 1] if idx + 1 < len(sylls) else ""

        # preempt vowel hiatus and correption
        if vowel(syll[-1]) and next_syll.startswith(" ") and vowel(next_syll[1]):
            line = line + "{" + f"{syll}" + "}"

        elif any("_" in char for char in syll):
            line = line + "[" + f"{syll}" + "]"
        elif syll_clean[-1] == "^":
            line = line + "{" + f"{syll}" + "}"
        elif heavy_syll(syll):
            line = line + "[" + f"{syll}" + "]"
        else:
            line = line + "{" + f"{syll}" + "}"

    return line

def fix_xml(input_file, output_file, debug=False):

    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(input_file, parser)
    root = tree.getroot()

    #################################################
    # 1) Get "gold" scansion from the first strophe #
    #################################################
    
    # Find the first <strophe> element
    first_strophe = root.find(".//strophe[1]")  # XPath index is 1-based

    # Iterate over its <l> children
    gold_strophe = []
    for idx, l in enumerate(first_strophe.findall("./l")):
        gold_line = []
        text = l.xpath("string()").strip()
        if debug:
            print(f"Line {idx+1}: {text}")
        sylls = re.split(r'(\[.+?\]|\{.+?\})', text)
        sylls = [syll for syll in sylls if syll]  # Remove empty matches
        for syll in sylls:
            if "[" in syll:
                gold_line.append("-")
            else:
                gold_line.append("u")
        assert len(gold_line) == len(sylls)
        gold_strophe.append(gold_line)
        if debug:
            print(gold_line)
    print(f"Gold strophe with {len(gold_strophe)} lines")

    #################################################
    # 2) Apply to all other strophes                #
    #################################################

    for strophe in root.findall(".//strophe")[1:]:  # Skip the first strophe
        for idx, l in enumerate(strophe.findall("./l")):
            text = l.xpath("string()").strip()
            if debug:
                print(f"Line {idx+1}: {text}")
            sylls = re.split(r'(\[.+?\]|\{.+?\})', text)
            sylls = [syll for syll in sylls if syll]  # Remove empty matches
            assert len(gold_strophe[idx]) == len(sylls), f"Line {text} with len {len(sylls)} in strophe does not match gold length {len(gold_strophe[idx])} of {gold_strophe[idx]}."
            new_line = ""
            for syll, weight in zip(sylls, gold_strophe[idx]):
                new_syll = re.sub(r'[\[\]\{\}]', '', syll)  # Remove existing brackets
                if weight == "-":
                    new_line += "[" + f"{syll}" + "]"
                else:
                    new_line += "{" + f"{syll}" + "}"
            if debug:
                print(new_line)
            l.clear()
            l.text = new_line

        scanned = fix_scansion(text)

        if scanned is None:
            continue

        # Remove all children and replace with scanned text
        l.clear()
        l.text = scanned

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    tree.write(
        output_file,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True
    )

