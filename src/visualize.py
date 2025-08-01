import re
import sys
from lxml import etree

from src.stats import (
    accentually_responding_syllables_of_line_pair,
    build_units_for_accent,
    canonical_sylls,
    count_all_syllables,
    has_acute
)

def extract_strophe_accent_positions(strophe_line, antistrophe_line):
    accent_map = accentually_responding_syllables_of_line_pair(strophe_line, antistrophe_line)
    if not accent_map:
        return set(), set()

    acutes_list, _, circ_list = accent_map
    strophe_n = strophe_line.get('n')

    acutes_set = set()
    for dct in acutes_list:
        for (line_id, unit_ord) in dct.keys():
            if line_id == strophe_n:
                acutes_set.add(unit_ord)

    circ_set = set()
    for dct in circ_list:
        for (line_id, unit_ord) in dct.keys():
            if line_id == strophe_n:
                circ_set.add(unit_ord)

    print(f"Acutes: {acutes_set}")
    return acutes_set, circ_set

def metre_line_with_accents(s_line, acutes_set, circ_set):
    syll_weights = canonical_sylls(s_line)
    units = build_units_for_accent(s_line)
    
    line_pattern = []

    for i, u in enumerate(units):
        ord_ = u['unit_ord']

        if u['type'] == 'single':
            syll = u['syll']
            weight = syll_weights[i]
            
            if weight == 'anceps':
                pattern = 'x'
            elif weight == 'heavy':
                if ord_ in circ_set:
                    pattern = '-^'
                elif ord_ in acutes_set:
                    pattern = "-'"
                else:
                    is_brevis_in_longo = (
                        syll.get('weight') == 'light' and i == len(units) - 1
                        and syll.get('resolution') != 'True'
                    )
                    pattern = 'U' if is_brevis_in_longo else '-'
            else:
                pattern = "u'" if ord_ in acutes_set else 'u'

            line_pattern.append(pattern)

        elif u['type'] == 'double':
            s1 = u['syll1']
            s2 = u['syll2']
            if ord_ in acutes_set:
                if has_acute(s1):
                    line_pattern.append("(u'u)")
                elif has_acute(s2):
                    line_pattern.append("(uu')")
                else:
                    line_pattern.append("(uu)")
            else:
                line_pattern.append("(uu)")
    
    return ''.join(line_pattern)

def restore_text(l_element):
    text_fragments = []
    
    for child in l_element:
        if child.tag == 'label':
            continue
        if child.tag == 'syll' and child.text:
            text_fragments.append(child.text)
        if child.tail:
            text_fragments.append(child.tail)

    return ' '.join(''.join(text_fragments).split())

def metre_strophe_with_accents(strophe, antistrophe):
    s_lines = strophe.findall('l')
    a_lines = antistrophe.findall('l')
    if len(s_lines) != len(a_lines):
        return "Line-count mismatch!"

    lines_output = []
    for s_line, a_line in zip(s_lines, a_lines):
        acutes_set, circ_set = extract_strophe_accent_positions(s_line, a_line)
        pattern_str = metre_line_with_accents(s_line, acutes_set, circ_set)
        line_n = s_line.get('n', '???')
        original_text = restore_text(s_line)
        lines_output.append(f"{line_n}: {pattern_str}")
        lines_output.append(original_text)
    return "\n".join(lines_output)

def visualize_responsion(responsion, xml):
    tree = etree.parse(xml)
    strophes = tree.xpath(f'//strophe[@type="strophe" and @responsion="{responsion}"]')
    antistrophes = tree.xpath(f'//strophe[@type="antistrophe" and @responsion="{responsion}"]')
    if len(strophes) != len(antistrophes):
        print(f"Mismatch in strophe and antistrophe counts for responsion {responsion}.")
        return

    RED = '\033[31m'
    GREEN = '\033[32m'
    RESET = '\033[0m'
    colored_char_count = 0

    def color_accents(text):
        nonlocal colored_char_count
        lines = text.split('\n')
        colored_lines = []
        for line in lines:
            if re.match(r'^\d+[a-zA-Z]?(?:-\d+[a-zA-Z]?)?:', line.strip()):
                colored_char_count += line.count('^') + line.count("'")
                line = line.replace('^', f"{RED}^{RESET}").replace("'", f"{GREEN}'{RESET}")
            colored_lines.append(line)
        return '\n'.join(colored_lines)

    for strophe, antistrophe in zip(strophes, antistrophes):
        print(f"\nResponsion: {responsion}")
        print("\nStrophe:")
        strophe_text = metre_strophe_with_accents(strophe, antistrophe)
        print(color_accents(strophe_text))
        print("\nAntistrophe:")
        antistrophe_text = metre_strophe_with_accents(antistrophe, strophe)
        print(color_accents(antistrophe_text))
    
    print(f"\nTotal responding accents colored: \033[36m{colored_char_count}\033[0m")
    print(f"Total canonical syllables: \033[36m{count_all_syllables(strophe)}\033[0m")

if __name__ == "__main__":
    pattern = r"^[A-Za-z]+"
    match = re.match(pattern, sys.argv[1])
    if match:
        infix = match.group()
        input_file = f"responsion_{infix}_compiled.xml"
        responsion_number = sys.argv[1]
        visualize_responsion(responsion_number, xml=input_file)
    else:
        print(f"Error: Could not extract an infix from '{sys.argv[1]}'", file=sys.stderr)
