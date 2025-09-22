from lxml import etree
import os
import re
from tqdm import tqdm

from grc_utils import count_ambiguous_dichrona_in_open_syllables, is_diphthong, vowel, short_vowel, syllabifier

muta = r'βγδθκπτφχΒΓΔΘΚΠΤΦΧ' # stops
liquida = r'[λΛμΜνΝρῤῥῬ]' # liquids and nasals

to_clean = r'[\u0387\u037e\u00b7\.,!?;:\"()\[\]{}<>«»\-—…|⏑⏓†×]'

def heavy_syll(syll):
    """Check if a syllable is heavy (either ends on a consonant or contains a long vowel/diphthong)."""

    cleaned = re.sub(to_clean, "", syll.strip())

    closed = not vowel(cleaned[-1])

    substrings = [cleaned[i:i+2] for i in range(len(cleaned) - 1)]
    has_diphthong = any(is_diphthong(substring) for substring in substrings)

    has_long = not short_vowel(syll) and count_ambiguous_dichrona_in_open_syllables(syll) == 0 # short_vowel does not include short dichrona
    
    return closed or has_diphthong or has_long

def rule_scansion(input):
    '''
    Scans vowel-length annotated text (^ and _), putting [] around heavy and {} around light sylls.
    '''
    sylls = syllabifier(input)

    # iterate through sylls and next_sylls: if syll 1) does not contain U+02C8 (ˈ), MODIFIER LETTER VERTICAL LINE, and 2) syll[-1] in muta and 3) next_syll[1] in liquida too, then move syll[-1] to the beginning of next_syll.
    for idx, syll in enumerate(sylls):
        next_syll = sylls[idx + 1] if idx + 1 < len(sylls) else ""
        if "ˈ" not in syll and syll[-1] in muta and next_syll[0] in liquida:
            sylls[idx] = syll[:-1]
            sylls[idx + 1] = syll[-1] + next_syll

    line = ""

    for idx, syll in enumerate(sylls):
        next_syll = sylls[idx + 1] if idx + 1 < len(sylls) else ""

        syll_clean = re.sub(to_clean, "", syll.strip())
        next_syll_clean = re.sub(to_clean, "", next_syll.strip())

        # preempt vowel hiatus and correption
        if vowel(syll_clean[-1]) and vowel(next_syll_clean[0]) and (syll.endswith(" ") or next_syll.startswith(" ")):
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

def scan_xml(input_file, output_file, debug=False):
    '''
    Adds [] and {} syllable boundaries to a macronized TEI XML file.
    '''
    # 🔽 Use parser with remove_blank_text=True
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(input_file, parser)
    root = tree.getroot()

    for idx, l in tqdm(enumerate(root.findall(".//l"))):
        text = l.xpath("string()").strip()
        if debug:
            print(f"Line {idx+1}: {text}")
        scanned = rule_scansion(text)

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

