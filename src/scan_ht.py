'''
Making scanned XML files from Hypotactic data, to be compiled.
'''

from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom

def extract_syllables_from_div(div_element, debug=False):
    """
    Extract syllable content from a div element and format with brackets.
    
    Args:
        div_element: BeautifulSoup div element or HTML string
        debug: If True, print debug information
        
    Returns:
        str: Formatted string with syllables in brackets
    """
    # If div_element is a string, parse it
    if isinstance(div_element, str):
        soup = BeautifulSoup(div_element, 'html.parser')
        div_element = soup.find('div')
    
    result = ""
    
    # Find all word spans to preserve word boundaries
    word_spans = div_element.find_all('span', class_='word')
    if debug:
        print(f"      Found {len(word_spans)} word spans")
    
    for word_index, word_span in enumerate(word_spans):
        # Find all syll spans within this word
        syll_spans = word_span.find_all('span', class_=lambda x: x and 'syll' in x)
        if debug:
            print(f"        Word {word_index + 1}: {len(syll_spans)} sylls")
        
        for syll_index, span in enumerate(syll_spans):
            classes = span.get('class', [])
            content = span.get_text()
            if debug:
                print(f"          Span: classes={classes}, content='{content}'")
            
            # Check for special modifiers
            prefix = ""
            if 'resolved' in classes:
                prefix = "€"
            elif 'anceps' in classes:
                prefix = "#"
            
            # Check if this is the last syllable of the word and not the last word
            is_last_syll_of_word = (syll_index == len(syll_spans) - 1)
            is_not_last_word = (word_index < len(word_spans) - 1)
            add_space = is_last_syll_of_word and is_not_last_word
            
            # Determine bracket type based on short/long
            if 'short' in classes:
                result += "{" + prefix + content + (" " if add_space else "") + "}"
            elif 'long' in classes:
                result += "[" + prefix + content + (" " if add_space else "") + "]"
    
    if debug:
        print(f"      Final result: '{result}'")
    return result

def extract_strophic_syllables_from_html(file_path, debug=False):
    """
    Extract syllables from HTML file organized by strophic structure.
    
    Args:
        file_path: Path to HTML file
        debug: If True, print debug information
        
    Returns:
        dict: Nested dictionary where top-level keys are poem indices (1, 2, 3, etc.)
              and values are dictionaries with strophic element keys like "strophe_1", 
              "antistrophe_1", "epode_1" etc. Each strophic element contains a list 
              of syllable strings from the lines in that section.
    """
    if debug:
        print(f"Processing file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')
    
    result = {}
    
    # Find all div elements with class="poem"
    poem_divs = soup.find_all('div', class_='poem')
    if debug:
        print(f"Found {len(poem_divs)} poem divs")
    
    for poem_index, poem_div in enumerate(poem_divs, 1):
        if debug:
            print(f"\nProcessing poem {poem_index}")
        
        # Initialize poem dictionary
        result[poem_index] = {}
        
        # Find all div elements that have data-strophe attribute within this poem
        strophe_divs = poem_div.find_all('div', attrs={'data-strophe': True})
        if debug:
            print(f"Found {len(strophe_divs)} strophe divs in poem {poem_index}")
        
        for i, strophe_div in enumerate(strophe_divs):
            # Get the data-strophe attribute to determine type
            strophe_type = strophe_div.get('data-strophe', '')
            strophe_num = strophe_div.get('data-strophenum', '1')
            if debug:
                print(f"  Strophe {i+1}: type='{strophe_type}', num='{strophe_num}'")
                print(f"  Classes: {strophe_div.get('class', [])}")
            
            # Create the key based on strophe type and number
            if strophe_type == 'Strophe':
                strophe_key = f"strophe_{strophe_num}"
            elif strophe_type == 'Antistrophe':
                strophe_key = f"antistrophe_{strophe_num}"
            elif strophe_type == 'Epode':
                strophe_key = f"epode_{strophe_num}"
            else:
                # Skip if we can't determine the type
                if debug:
                    print(f"    Skipping unknown strophe type: '{strophe_type}'")
                continue
            
            if debug:
                print(f"    Processing as key: {strophe_key}")
            
            # Find all child div elements with "line" in class
            line_syllables = []
            
            # Look for line divs that are direct children
            all_child_divs = strophe_div.find_all('div', recursive=True)
            if debug:
                print(f"    Found {len(all_child_divs)} total child divs")
            
            # Filter for line divs
            child_line_divs = []
            for div in all_child_divs:
                div_classes = div.get('class', [])
                if debug:
                    print(f"      Checking div with classes: {div_classes}")
                if any('line' in str(cls) for cls in div_classes):
                    child_line_divs.append(div)
                    if debug:
                        print(f"        -> This is a line div!")
            
            if debug:
                print(f"    Found {len(child_line_divs)} child line divs")
            
            for j, line_div in enumerate(child_line_divs):
                if debug:
                    print(f"      Child line {j+1}: classes {line_div.get('class', [])}")
                syllables = extract_syllables_from_div(line_div, debug=debug)
                if debug:
                    print(f"      Extracted syllables: '{syllables}'")
                if syllables:
                    line_syllables.append(syllables)
            
            if debug:
                print(f"    Total lines collected: {len(line_syllables)}")
            if line_syllables:
                result[poem_index][strophe_key] = line_syllables
    
    return result

def create_tei_xml(poems_dict, title, prefix, output_file, author="Pindar", debug=False):
    """
    Create TEI XML from the poems dictionary in three versions.
    
    Args:
        poems_dict: Nested dictionary from extract_strophic_syllables_from_html()
        title: Title for the TEI document
        author: Author name
        output_file: Optional base path to save the XML files (will create 3 versions)
        debug: If True, print debug information
        
    Returns:
        tuple: (triads_xml, epodes_xml, strophes_xml) - Pretty-printed XML strings
    """
    
    def create_base_structure():
        """Create base TEI structure"""
        tei = ET.Element('TEI')
        tei_header = ET.SubElement(tei, 'teiHeader')
        file_desc = ET.SubElement(tei_header, 'fileDesc')
        title_stmt = ET.SubElement(file_desc, 'titleStmt')
        title_elem = ET.SubElement(title_stmt, 'title')
        title_elem.text = title
        author_elem = ET.SubElement(title_stmt, 'author')
        author_elem.text = author
        text = ET.SubElement(tei, 'text')
        body = ET.SubElement(text, 'body')
        return tei, body
    
    def get_strophe_type(strophe_key):
        """Determine strophe type from key"""
        if strophe_key.startswith('strophe_'):
            return 'strophe'
        elif strophe_key.startswith('antistrophe_'):
            return 'antistrophe'
        elif strophe_key.startswith('epode_'):
            return 'epode'
        return 'strophe'
    
    def sort_strophes(strophe_keys):
        """Sort strophes in triadic order"""
        return sorted(strophe_keys, key=lambda x: (
            int(x.split('_')[-1]),
            0 if 'strophe_' in x and 'anti' not in x else (1 if 'antistrophe' in x else 2)
        ))
    
    def add_lines(parent_elem, lines, start_line_num, section_type=None):
        """Add line elements to parent"""
        line_num = start_line_num
        for i, line_content in enumerate(lines):
            l_elem = ET.SubElement(parent_elem, 'l')
            l_elem.set('n', str(line_num))
            # Mark first line of antistrophe or epode sections
            if i == 0 and section_type in ['antistrophe', 'epode']:
                l_elem.set('metre', section_type)
            else:
                l_elem.set('metre', '')
            l_elem.text = line_content
            line_num += 1
        return line_num
    
    def add_lines_with_absolute_numbering(parent_elem, lines, start_line_num, section_type=None):
        """Add line elements to parent with absolute line numbering"""
        line_num = start_line_num
        for i, line_content in enumerate(lines):
            l_elem = ET.SubElement(parent_elem, 'l')
            l_elem.set('n', str(line_num))
            # Mark first line of antistrophe or epode sections
            if i == 0 and section_type in ['antistrophe', 'epode']:
                l_elem.set('metre', section_type)
            else:
                l_elem.set('metre', '')
            l_elem.text = line_content
            line_num += 1
        return line_num
    
    def prettify_xml(tei):
        """Convert to pretty-printed XML string"""
        xml_str = ET.tostring(tei, encoding='unicode')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ')
        return '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
    
    # VERSION 1: Merged triads (strophe + antistrophe + epode = one strophe element)
    tei_triads, body_triads = create_base_structure()
    
    # VERSION 2: Epodes only
    tei_epodes, body_epodes = create_base_structure()
    
    # VERSION 3: Strophes and antistrophes as separate elements (no epodes)
    tei_strophes, body_strophes = create_base_structure()
    
    for poem_num in sorted(poems_dict.keys()):
        poem_data = poems_dict[poem_num]
        
        # Create cantica for each version
        canticum_triads = ET.SubElement(body_triads, 'canticum')
        canticum_epodes = ET.SubElement(body_epodes, 'canticum')
        
        # Check if this poem has at least one strophe AND one antistrophe
        has_strophe = any(key.startswith('strophe_') for key in poem_data.keys())
        has_antistrophe = any(key.startswith('antistrophe_') for key in poem_data.keys())
        include_in_version3 = has_strophe and has_antistrophe
        
        # Only create canticum for version 3 if it has both strophes and antistrophes
        canticum_strophes = ET.SubElement(body_strophes, 'canticum') if include_in_version3 else None
        
        # Sort strophes
        strophe_keys = sort_strophes(list(poem_data.keys()))
        
        # Group by triad number
        triads = {}
        for key in strophe_keys:
            num = int(key.split('_')[-1])
            if num not in triads:
                triads[num] = {}
            strophe_type = get_strophe_type(key)
            triads[num][strophe_type] = poem_data[key]
        
        # Process each triad
        line_num_global = 1  # Global line number counter for absolute numbering
        
        for triad_num in sorted(triads.keys()):
            triad = triads[triad_num]
            
            # Calculate line numbers for each section in this triad
            strophe_start = line_num_global
            strophe_lines = len(triad.get('strophe', []))
            
            antistrophe_start = strophe_start + strophe_lines
            antistrophe_lines = len(triad.get('antistrophe', []))
            
            epode_start = antistrophe_start + antistrophe_lines
            epode_lines = len(triad.get('epode', []))
            
            # VERSION 1: Merged triad
            strophe_elem_triads = ET.SubElement(canticum_triads, 'strophe')
            strophe_elem_triads.set('type', 'strophe')
            strophe_elem_triads.set('responsion', f'{prefix}{poem_num:02d}')
            
            current_line = line_num_global
            # Add strophe lines (no special marking for first line)
            if 'strophe' in triad:
                current_line = add_lines(strophe_elem_triads, triad['strophe'], current_line)
            
            # Add antistrophe lines (mark first line)
            if 'antistrophe' in triad:
                current_line = add_lines(strophe_elem_triads, triad['antistrophe'], current_line, 'antistrophe')
            
            # Add epode lines (mark first line)
            if 'epode' in triad:
                current_line = add_lines(strophe_elem_triads, triad['epode'], current_line, 'epode')
            
            # VERSION 2: Epodes only (with absolute line numbering)
            if 'epode' in triad:
                strophe_elem_epodes = ET.SubElement(canticum_epodes, 'strophe')
                strophe_elem_epodes.set('type', 'strophe')
                strophe_elem_epodes.set('responsion', f'{prefix}{poem_num:02d}')
                add_lines_with_absolute_numbering(strophe_elem_epodes, triad['epode'], epode_start)
            
            # VERSION 3: Strophes and antistrophes as separate elements (with absolute line numbering)
            # Only add if this poem qualifies for version 3
            if include_in_version3:
                if 'strophe' in triad:
                    strophe_elem_strophes = ET.SubElement(canticum_strophes, 'strophe')
                    strophe_elem_strophes.set('type', 'strophe')
                    strophe_elem_strophes.set('responsion', f'{prefix}{poem_num:02d}')
                    add_lines_with_absolute_numbering(strophe_elem_strophes, triad['strophe'], strophe_start)
                
                if 'antistrophe' in triad:
                    antistrophe_elem = ET.SubElement(canticum_strophes, 'strophe')
                    antistrophe_elem.set('type', 'strophe')
                    antistrophe_elem.set('responsion', f'{prefix}{poem_num:02d}')
                    add_lines_with_absolute_numbering(antistrophe_elem, triad['antistrophe'], antistrophe_start)
            
            # Update global line counter for next triad
            line_num_global = current_line
    
    # Prettify all versions
    xml_triads = prettify_xml(tei_triads)
    xml_epodes = prettify_xml(tei_epodes)
    xml_strophes = prettify_xml(tei_strophes)
    
    # Save to files if requested
    if output_file:
        # Remove extension if present
        base_path = output_file.rsplit('.', 1)[0] if '.' in output_file else output_file
        
        # Save version 1: merged triads (with starts of antistrophes and epodes marked)
        with open(f"{base_path}_triads.xml", 'w', encoding='utf-8') as f:
            f.write(xml_triads)
        if debug:
            print(f"TEI XML (merged triads) saved to: {base_path}_triads.xml")
        
        # Save version 2: epodes only
        with open(f"{base_path}_epodes.xml", 'w', encoding='utf-8') as f:
            f.write(xml_epodes)
        if debug:
            print(f"TEI XML (epodes only) saved to: {base_path}_epodes.xml")
        
        # Save version 3: strophes and antistrophes as separate elements
        with open(f"{base_path}_strophes.xml", 'w', encoding='utf-8') as f:
            f.write(xml_strophes)
        if debug:
            print(f"TEI XML (strophes/antistrophes as separate elements) saved to: {base_path}_strophes.xml")
    
    return xml_triads, xml_epodes, xml_strophes

