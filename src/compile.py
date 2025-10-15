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

from lxml import etree
import re

from .stats import canonical_sylls, metrically_responding_lines_polystrophic

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
        
################################################################
################# Responsion checks and fixes ##################
################################################################

def autofix_responsion(xml_text, responsion_id, line_numbers, diff_indices_list, lines):
    """
    Attempt to automatically fix responsion issues by adding anceps="True" attribute
    to syll elements at problematic positions.
    
    Returns: (success: bool, fixed_xml: str)
    """
    # Check if all strophes have same length
    lengths = [len(canonical_sylls(line)) for line in lines]
    if len(set(lengths)) > 1:
        print(f"Cannot autofix: strophes have different lengths {lengths}")
        return False, xml_text
    
    # Find ALL positions that differ in ANY comparison
    # Use union instead of intersection to get all problematic positions
    all_diffs = set()
    for diff_list in diff_indices_list:
        if diff_list:  # Only consider non-empty diff lists
            all_diffs = all_diffs.union(set(diff_list))
    
    if not all_diffs:
        print(f"Cannot autofix: no problematic positions found")
        return False, xml_text
    
    problem_positions = sorted(list(all_diffs))
    print(f"Attempting autofix at {len(problem_positions)} position(s): {[p + 1 for p in problem_positions]} (0-indexed: {problem_positions})")
    
    # Parse the XML and find the lines by their line numbers
    root = etree.fromstring(xml_text.encode())
    
    # Get the responsion group strophes
    group_strophes = [s for s in root.xpath('//strophe[@responsion]') if s.get('responsion') == responsion_id]
    
    updated_sylls = []  # For debugging
    
    # For each strophe in the group, find the corresponding line and fix it
    for strophe in group_strophes:
        strophe_lines = strophe.findall('.//l')
        
        # Find the line that matches one of our line numbers
        for line in strophe_lines:
            if line.get('n') in line_numbers:
                sylls = line.findall('.//syll')
                
                # Map positions to syll elements, accounting for resolution pairs
                position_to_syll = []
                i = 0
                while i < len(sylls):
                    # Check if this is a resolution pair (two consecutive sylls with resolution="True")
                    if (i < len(sylls) - 1 and 
                        sylls[i].get('resolution') == 'True' and 
                        sylls[i+1].get('resolution') == 'True'):
                        # Two consecutive resolution sylls count as single position
                        position_to_syll.append((sylls[i], sylls[i+1]))
                        i += 2
                    else:
                        position_to_syll.append(sylls[i])
                        i += 1
                
                # Fix the sylls at all problem positions
                for problem_position in problem_positions:
                    if problem_position < len(position_to_syll):
                        target = position_to_syll[problem_position]
                        
                        if isinstance(target, tuple):
                            # It's a resolution pair - add anceps to both
                            for syll in target:
                                syll.set('anceps', 'True')
                                updated_sylls.append(f"Line {line.get('n')}, pos {problem_position + 1}: <syll {' '.join([f'{k}=\"{v}\"' for k, v in syll.attrib.items()])}>{syll.text}</syll>")
                        else:
                            # Single syll - add anceps
                            target.set('anceps', 'True')
                            updated_sylls.append(f"Line {line.get('n')}, pos {problem_position + 1}: <syll {' '.join([f'{k}=\"{v}\"' for k, v in target.attrib.items()])}>{target.text}</syll>")
    
    # Print updated sylls for debugging
    if updated_sylls:
        print(f"\n\033[36mUpdated {len(updated_sylls)} syll element(s):\033[0m")
        for syll_info in updated_sylls:
            print(f"  {syll_info}")
        print()
    
    # Convert back to string
    fixed_xml = etree.tostring(root, encoding='unicode')
    return True, fixed_xml

def check_line_responsion(lines):
    """
    Check if a set of corresponding lines from different strophes respond metrically.
    Returns: (responds: bool, diff_indices_list: list)
    """
    if not lines or len(lines) < 2:
        return True, []
    
    first_metre = canonical_sylls(lines[0])
    first_metre = ["u" if syll == "light" else "–" for syll in first_metre]
    
    diff_indices_list = []
    for i in range(1, len(lines)):
        other_metre = canonical_sylls(lines[i])
        other_metre = ["u" if syll == "light" else "–" for syll in other_metre]
        
        if len(first_metre) != len(other_metre):
            diff_indices = list(range(max(len(first_metre), len(other_metre))))
        else:
            diff_indices = [j for j, (s1, s2) in enumerate(zip(first_metre, other_metre)) if s1 != s2]
        
        diff_indices_list.append(diff_indices)
    
    responds = metrically_responding_lines_polystrophic(*lines)
    return responds, diff_indices_list


def assert_responsion(xml_text, attempt_autofix=True):
    """
    Assert that all corresponding lines in strophes with the same responsion attribute metrically respond.
    Attempts to autofix simple cases where all strophes have the same length and differ at a single position.
    Returns: (perfect_responsion: bool, xml_text: str)
    """
    root = etree.fromstring(xml_text.encode())
    responsion_groups = {}
    
    # Group strophes by responsion attribute using XPath
    for strophe in root.xpath('//strophe[@responsion]'):
        responsion_id = strophe.get('responsion')
        if responsion_id not in responsion_groups:
            responsion_groups[responsion_id] = []
        responsion_groups[responsion_id].append(strophe)
    
    # Global counter for all buggy lines
    total_buggy_lines = 0
    
    # For each responsion group, check corresponding lines
    for responsion_id, strophes in responsion_groups.items():
        # Get lines from each strophe
        strophe_lines = [strophe.findall('.//l') for strophe in strophes]
        
        # Compare corresponding lines
        buggy_lines = 0
        for line_index, lines in enumerate(zip(*strophe_lines)):
            line_numbers = [l.get('n', 'unknown') for l in lines]
            
            # Process first strophe
            first_strophe_metre = canonical_sylls(lines[0])
            first_strophe_metre = ["u" if syll == "light" else "–" for syll in first_strophe_metre]
            first_strophe_metre_str = " ".join(first_strophe_metre)

            # Process all other strophes
            strophe_data = []
            diff_indices_list = []

            for i in range(1, len(lines)):
                strophe_metre = canonical_sylls(lines[i])
                strophe_metre = ["u" if syll == "light" else "–" for syll in strophe_metre]
                strophe_metre_str = " ".join(strophe_metre)
                
                # Calculate differences
                diff_indices = [j for j, (s1, s2) in enumerate(zip(first_strophe_metre, strophe_metre)) if s1 != s2]
                diff_indices_list.append(diff_indices)
                human_readable_diffs = [j + 1 for j in diff_indices]
                
                # Highlight syllables
                strophe_sylls = lines[i].findall('.//syll')
                highlighted_text = "".join([
                    f"\033[31m{syll.text}\033[0m" if idx in diff_indices else syll.text 
                    for idx, syll in enumerate(strophe_sylls)
                ])
                
                # Highlight metre
                highlighted_metre = " ".join([
                    f"\033[31m{syll}\033[0m" if idx in diff_indices else syll 
                    for idx, syll in enumerate(strophe_metre)
                ])
                
                strophe_data.append({
                    'metre': highlighted_metre,
                    'text': highlighted_text,
                    'diff_indices': diff_indices,
                    'human_readable_diffs': human_readable_diffs
                })

            # Check if lines respond metrically
            if not metrically_responding_lines_polystrophic(*lines):
                buggy_lines += 1
                
                # Build output string
                print_output = f"\n\033[33mLines {', '.join(line_numbers)} in responsion group '{responsion_id}' do not respond metrically.\033[0m\n" \
                    f"Str 1:\t {first_strophe_metre_str}\n"
                
                # Add all other strophes
                for i, data in enumerate(strophe_data, start=2):
                    print_output += f"\nStr {i}:\t {data['metre']}\n" \
                                   f"Text {i}:\t {data['text']}\n" \
                                   f"Diffs {i}: {len(data['diff_indices'])} at positions: {data['human_readable_diffs']}\n"
                
                print(print_output)
                
                # Attempt autofix only if enabled
                if attempt_autofix:
                    print("\nAttempting autofix...")
                    success, fixed_xml = autofix_responsion(xml_text, responsion_id, line_numbers, diff_indices_list, lines)
                    
                    if success:
                        print("Autofix applied. Rechecking...")
                        # Get the updated lines from fixed XML
                        fixed_root = etree.fromstring(fixed_xml.encode())
                        fixed_strophes = [s for s in fixed_root.xpath('//strophe[@responsion]') if s.get('responsion') == responsion_id]
                        fixed_strophe_lines = [strophe.findall('.//l') for strophe in fixed_strophes]
                        fixed_lines = list(zip(*fixed_strophe_lines))[line_index]
                        
                        # Check just these lines
                        responds, _ = check_line_responsion(fixed_lines)
                        
                        if responds:
                            print("\033[32m✓ Autofix successful! Responsion now works.\033[0m\n")
                            xml_text = fixed_xml  # Update xml_text with the fixed version
                            # Re-parse to update references for remaining checks
                            root = etree.fromstring(xml_text.encode())
                            responsion_groups[responsion_id] = [s for s in root.xpath('//strophe[@responsion]') if s.get('responsion') == responsion_id]
                            strophe_lines = [strophe.findall('.//l') for strophe in responsion_groups[responsion_id]]
                            buggy_lines -= 1  # Don't count this as a buggy line since it was fixed
                        else:
                            print("\033[31m✗ Autofix applied but responsion still fails.\033[0m\n")
                    else:
                        print("Autofix not applicable.\n")
                
        if buggy_lines > 0:
            print(f"\nBuggy lines: \033[31m{buggy_lines}\033[0m out of {len(strophe_lines[0])} lines in responsion group '{responsion_id}'.\n")
            total_buggy_lines += buggy_lines

    # Print total summary
    if total_buggy_lines > 0:
        print(f"\n{'='*60}")
        print(f"TOTAL BUGGY LINES ACROSS ALL RESPONSION GROUPS: \033[31m{total_buggy_lines}\033[0m")
        print(f"{'='*60}\n")
    
    return total_buggy_lines == 0, xml_text

################################################################
################################################################
################################################################

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
    validator(xml_content)
    
    # Get both return values from assert_responsion
    perfect_responsion, xml_content = assert_responsion(xml_content)

    if perfect_responsion:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(xml_content)

        print(f"Processed XML saved to {output_file}")