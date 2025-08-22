# b_compile.py
'''
Second step of the XML processing pipeline for the accentual responsion project, Urdatorn/aristophanis-cantica.

Compiles metrical pseudo-markup into proper XML <syll> tags,
with attributes for weight, anceps, resolution, brevis in longo and closed-syllable vowel length.

NB: if information contained in input <conjecture> tags is needed, for example for a born-digital edition,
the line "xml_content = remove_conjecture_tags(xml_content)" should be commented out.
Since extra nested elements are bug prone, <conjecture> elements are otherwise removed.

NB: self-closing placeholder <l skip="True"/> elements are supported, but not recommended. If skipped placeholder lines are needed, use <l skip="True"></l> instead.

@author: Albin Thörn Cleland, Lunds universitet, albin.thorn_cleland@klass.lu.se
@license: GPL-3.0 (GNU General Public License v3.0)
'''

import argparse
from lxml import etree
import re

from src.stats import metrically_responding_lines_polystrophic

# Mapping of brackets to <syll> tags
# ***Important: single chars must come after multi-chars!***
bracket_map = {
    "(_": '<macron>',
    "_)": '</macron>',
    "[#": '<syll weight="heavy" anceps="True">',
    "{#": '<syll weight="light" anceps="True">',
    "[€": '<syll weight="heavy" contraction="True">', # I don't use this attribute; it simplifies things to rather implicitly mark contraction by pseudo-resolution in the uncontracted strophes
    "{€": '<syll weight="light" resolution="True">',
    "[": '<syll weight="heavy">',
    "]": '</syll>',
    "{": '<syll weight="light">',
    "}": '</syll>'
}


def remove_skipped_lines(xml_text):
    """
    Remove <l> elements with skip="True".
    Handles both regular and self-closing <l> tags.
    """
    def clean_line(match):
        line = match.group(0)
        return "" if line.strip() else line

    regular_l = r"^[ \t]*<l[^>]*\bskip=['\"]True['\"][^>]*>.*?</l>[ \t]*\n?" # \b is a word boundary anchor which matches a position between a word char (\w) and a non-word char (\W).
    selfclose_l = r"^[ \t]*<l[^>]*\bskip=['\"]True['\"][^>]*/>[ \t]*\n?" # NB: without the "\n?"" there are empty lines left in the output
    
    text = re.sub(regular_l, clean_line, xml_text, flags=re.MULTILINE) # the flag MULTILINE makes ^ and $ match the start and end of *each* line, instead of of the entire string.
    text = re.sub(selfclose_l, clean_line, text, flags=re.MULTILINE)
    
    return text


def remove_skipped_parts(xml_text):
    """Remove content inside <skip>...</skip> tags."""
    skip_pattern = re.compile(r"<skip>.*?</skip>", re.DOTALL)
    return skip_pattern.sub("", xml_text)


def remove_conjecture_tags(xml_text):
    """
    Remove <conjecture> tags while preserving their content.
    Relevant regex tips:
    - Inside character classes [], ^ means "any character but", so [^>] means "any character but >".
    - ? means "non-greedily", so .*? means "any character, zero or more times, but stop when reaching whatever next character comes after the ? in the regex", which here is <conjecture/>.
    - r'...' (raw) makes backslash / in a string literal and not an escape character.
    - In r.sub, the second argument is what substitutes for whatever is matched by the regex in the first argument.
    - And remeber: regex should *always* be clearly understood in detail! You will introduce bugs if you don't understand what you're doing (I wrote this after linting one...).
    """
    # Debug print
    # matches = re.findall(r'<conjecture[^>]*>(.*?)</conjecture>', xml_text)
    # print(f"Found {len(matches)} conjecture matches.")
    
    xml_text = re.sub(r'<conjecture[^>]*>(.*?)</conjecture>', r'\1', xml_text) # r'\1' refers to the group captured by (.*?), the first (1) group in the regex
    xml_text = re.sub(r'<conjecture[^>]*/>', '', xml_text)
    return xml_text


def compile_scan(xml_text):
    """Compile bracket patterns inside <l> elements into <syll> tags."""
    l_pattern = re.compile(r"(<l[^>]*>)(.*?)(</l>)", re.DOTALL)

    def replace_brackets(match):
        opening, content, closing = match.groups()
        for key, value in bracket_map.items():
            content = content.replace(key, value)
        return f"{opening}{content}{closing}"

    return l_pattern.sub(replace_brackets, xml_text)


def apply_brevis_in_longo(xml_text):
    """Mark the last light non-resolution <syll> of each <l> with brevis_in_longo='True',
    except when metre ends in 'da' (lyric non-stichic dactylic), unless the penultimate syllable is heavy.
    """
    l_pattern = re.compile(r"(<l[^>]*>)(.*?)(</l>)", re.DOTALL)

    def mark_final_syllable(match):
        opening, content, closing = match.groups()
        metre_match = re.search(r'metre="([^"]+)"', opening)
        metre_value = metre_match.group(1) if metre_match else ""
        syll_matches = list(re.finditer(r'<syll[^>]*>', content))

        if not syll_matches:
            return f"{opening}{content}{closing}"

        if metre_value.endswith("da"):
            if len(syll_matches) >= 2:
                penultimate_syll_match = syll_matches[-2]
                if 'weight="heavy"' not in penultimate_syll_match.group():
                    return f"{opening}{content}{closing}"

        last_syll_match = syll_matches[-1]
        last_syll = last_syll_match.group()

        if 'weight="light"' in last_syll and 'resolution="True"' not in last_syll:
            updated_syll = re.sub(r'(>)', r' brevis_in_longo="True"\1', last_syll, count=1)
            content = content[:last_syll_match.start()] + updated_syll + content[last_syll_match.end():]

        return f"{opening}{content}{closing}"

    return l_pattern.sub(mark_final_syllable, xml_text)


def order_l_attributes(xml_text):
    """Ensure 'n' appears first, 'metre' second, and other attributes follow."""
    l_pattern = re.compile(r'<l([^>]*)>', re.DOTALL)

    def reorder_attributes(match):
        raw_attributes = match.group(1)
        attrib_dict = dict(re.findall(r'(\S+?)="(.*?)"', raw_attributes))
        n = attrib_dict.pop("n", "")
        metre = attrib_dict.pop("metre", "")
        special = {k: v for k, v in attrib_dict.items() if "brevis_in_longo" in k or "resolution" in k}
        ordered_attribs = [f'n="{n}"', f'metre="{metre}"'] if n else [f'metre="{metre}"']
        for k, v in attrib_dict.items():
            if k not in special:
                ordered_attribs.append(f'{k}="{v}"')
        for k, v in special.items():
            ordered_attribs.append(f'{k}="{v}"')
        return f'<l {" ".join(ordered_attribs)}>'

    return l_pattern.sub(reorder_attributes, xml_text)


def remove_empty_cantica(xml_text):
    """
    Remove cantica yet to be scanned. 
    Useful to debug while in the midst of scanning.

    NB: Since cantica span multiple lines, we need the regex flag "re.DOTALL".
    """
    canticum_pattern = re.compile(r'\s*<canticum[^>]*>.*?</canticum>\s*', re.DOTALL)
    
    def filter_cantica(match):
        cantica = match.group(0)
        has_sylls = bool(re.search(r'<syll[^>]*>', cantica))
        return cantica if has_sylls else ''
    
    return canticum_pattern.sub(filter_cantica, xml_text) # function-based replacement is pretty cool


def validator(text):
    """Validate for misplaced characters, unbalanced tags, and empty <l> elements."""
    lines = text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if '#' in line:
            raise ValueError(f"Misplaced # at line {line_number}!")
        if '€' in line:
            raise ValueError(f"Misplaced € at line {line_number}!")
        lt_count = line.count('<')
        gt_count = line.count('>')
        if lt_count > gt_count:
            raise ValueError(f"Lonely < at line {line_number}!")
        elif gt_count > lt_count:
            raise ValueError(f"Lonely > at line {line_number}!")
        # Check for empty <l> elements
        if re.match(r"<l[^>]*>\s*</l>", line):
            raise ValueError(f"Empty <l> element at line {line_number}!")


def assert_responsion(xml_text):
    """
    Assert that all corresponding lines in strophes with the same responsion attribute metrically respond.
    """
    root = etree.fromstring(xml_text.encode())
    responsion_groups = {}
    
    # Group strophes by responsion attribute using XPath
    for strophe in root.xpath('//strophe[@responsion]'):
        responsion_id = strophe.get('responsion')
        if responsion_id not in responsion_groups:
            responsion_groups[responsion_id] = []
        responsion_groups[responsion_id].append(strophe)
    
    # For each responsion group, check corresponding lines
    for responsion_id, strophes in responsion_groups.items():
        # Get lines from each strophe
        strophe_lines = [strophe.findall('.//l') for strophe in strophes]
        
        # Compare corresponding lines
        for line_index, lines in enumerate(zip(*strophe_lines)):
            line_numbers = [l.get('n', 'unknown') for l in lines]
            assert metrically_responding_lines_polystrophic(*lines), \
                f"Lines {', '.join(line_numbers)} in responsion group '{responsion_id}' do not respond metrically"


def process_file(input_file, output_file):
    """Process the XML file and save the output."""
    with open(input_file, "r", encoding="utf-8") as f:
        xml_content = f.read()

    xml_content = remove_skipped_lines(xml_content)
    xml_content = remove_skipped_parts(xml_content)
    xml_content = remove_conjecture_tags(xml_content)
    xml_content = compile_scan(xml_content)
    xml_content = apply_brevis_in_longo(xml_content)
    xml_content = order_l_attributes(xml_content)
    xml_content = remove_empty_cantica(xml_content)
    validator(xml_content) # validate XML syntax
    assert_responsion(xml_content) # validate scansion

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"Processed XML saved to {output_file}")


def main():
    """Main function to parse arguments and process the input file."""
    parser = argparse.ArgumentParser(description="Compile a scanned play into <syll> XML.")
    parser.add_argument("infix", help="Abbreviation for the play (e.g., 'eq').")
    args = parser.parse_args()

    input_file = f"data/scan/responsion_{args.infix}_scan.xml"
    output_file = f"data/compiled/responsion_{args.infix}_compiled.xml"

    process_file(input_file, output_file)


if __name__ == "__main__":
    main()