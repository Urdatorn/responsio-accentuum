#!/usr/bin/env python3

# Copyright © Albin Ruben Johannes Thörn Cleland 2026, Lunds universitet, albin.thorn_cleland@klass.lu.se
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

from grc_utils import syllabifier, vowel

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
    # 1) Collect skip information from ALL strophes #
    #################################################
    
    skip_lines = set()  # Track which line positions should be skipped
    all_strophes = root.findall(".//strophe")
    
    # First pass: collect all lines marked with skip="True" from any strophe
    for strophe in all_strophes:
        for idx, l in enumerate(strophe.findall("./l")):
            if l.get("skip") == "True":
                skip_lines.add(idx)
    
    if debug and skip_lines:
        print(f"Lines to skip (found across all strophes): {sorted(skip_lines)}")
    
    #################################################
    # 2) Get "gold" scansion from the first strophe #
    #################################################
    
    # Find the first <strophe> element
    first_strophe = root.find(".//strophe[1]")  # XPath index is 1-based

    # Iterate over its <l> children
    gold_strophe = []
    for idx, l in enumerate(first_strophe.findall("./l")):
        # Check if this line should be skipped
        if idx in skip_lines:
            gold_strophe.append(None)  # Placeholder for skipped lines
            if debug:
                print(f"Line {idx+1}: SKIPPED")
            continue
        
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
    print(f"Gold strophe with {len(gold_strophe)} lines ({len(skip_lines)} lines marked to skip)")

    #################################################
    # 3) Syllabify all strophes except the first    #
    #################################################

    for strophe in root.findall(".//strophe")[1:]:  # Skip the first strophe
        for idx, l in enumerate(strophe.findall("./l")):
            # Skip this line if it was marked as skip
            if idx in skip_lines:
                if debug:
                    print(f"Skipping syllabification for line {idx+1} in strophe")
                continue
            
            # Get the raw text content without any markup
            text = l.xpath("string()").strip()
            # Remove brackets and braces to get clean text
            clean_text = re.sub(r'[\[\]\{\}]', '', text)
            
            # Syllabify the clean text
            syllables = syllabifier(clean_text)
            
            # Format as [syll1][syll2]...
            syllabified_text = "".join(f"[{syll}]" for syll in syllables)
            
            if debug:
                print(f"Line {idx+1} syllabified: {syllabified_text}")
            
            # Replace the line content with syllabified version
            l.clear()
            l.text = syllabified_text
    
    #################################################
    # 4) Apply gold scansion to all other strophes  #
    #################################################

    for strophe in root.findall(".//strophe")[1:]:  # Skip the first strophe
        for idx, l in enumerate(strophe.findall("./l")):
            # Skip this line if it was marked as skip in the gold strophe
            if idx in skip_lines:
                if debug:
                    print(f"Skipping line {idx+1} in strophe")
                continue
            
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

